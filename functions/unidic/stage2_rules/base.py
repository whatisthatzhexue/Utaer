"""阶段二规则引擎核心：Rule 基类、形态素工作状态（MorphState）与规则上下文（MorphList）。

契约（``AGENT.md`` 3.2/3.3、《本项目配置教程.md》3.8.2）：

- 规则为纯函数式条件判断（``match`` → ``apply``），**确定性**：同一输入必得同一输出；
  禁止随机、统计或机器学习推断；
- 每条规则必须携带 ``rule_id`` / ``name`` / ``source_ref``（资料编号 + 节号，如
  ``NHK Ⅲ-1 1.1``、``UniDic 表10 C2``），保证可追溯；
- ``priority`` 数值越大越先匹配（遍内）；``phase`` 区分「推导型」与「后处理校验型」，
  校验型（核合法性）永远在推导之后执行——见 :func:`stage2_rules.run_engine`；
- ``match(self, morphs, i)`` / ``apply(self, morphs, i)`` 的签名与《本项目配置教程.md》
  3.8.2 的自定义规则示例完全兼容（``morphs`` 即 :class:`MorphList`，``morphs[i]`` 为
  :class:`MorphState`，可直接读写 ``pos`` / ``accent_raw`` / ``accent`` 等属性）。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

import mora_util

logger = logging.getLogger(__name__)


class RulePhase(Enum):
    """规则执行阶段：推导型 / 后处理校验型。"""

    DERIVATION = "derivation"
    VALIDATION = "validation"


def parse_accent_value(accent_raw: str) -> tuple[int | None, list[int]]:
    """解析词典调型字符串 → ``(主值, 变体列表)``。

    - ``"0"`` → ``(0, [])``；``"2"`` → ``(2, [])``；
    - ``"0,1"`` → ``(0, [1])``（NHK：先示者为第 1 アクセント，其余为变体）；
    - ``""`` / ``"@"`` / 非法格式 → ``(None, [])``。
    """
    if not accent_raw or accent_raw == "@":
        return None, []
    numbers: list[int] = []
    for part in accent_raw.split(","):
        part = part.strip()
        if not part.isdigit():
            logger.warning("无法解析的调型值：%r（按未收录处理）", accent_raw)
            return None, []
        numbers.append(int(part))
    if not numbers:
        return None, []
    return numbers[0], numbers[1:]


#: 文末記号（句点類）——文境界の表層形による判定（pos に ``句点`` を含むものと併用）
SENTENCE_END_SYMBOLS: frozenset[str] = frozenset({"。", "．", "！", "？", "!", "?"})


@dataclass
class Unit:
    """アクセント単位（韵律单位）：一组连续形态素，至多一个下降核（NHK Ⅲ全般 4.）。"""

    unit_id: int
    start: int   # 起始形态素 idx（闭区间）
    end: int     # 结束形态素 idx（闭区间）


@dataclass
class MorphState:
    """阶段二工作状态：阶段一「资料一」形态素的可变副本 + 推导结果。

    阶段一字段同名同义（见 ``stage1_analyzer.Morph``）；推导状态字段：

    - ``accent``：``None``=未推导；``0``=平板；``N``=第 N 拍后下降（东京式核位置）；
    - ``variants``：词典多调型中的其余值（依 NHK：首个为主值）；
    - ``derived_by``：写入 ``accent`` 的规则 rule_id（冲突裁定与报告溯源用）；
    - ``claimed``：已被更高优先级规则整段占用（如复合词合并的后部要素），后续规则跳过；
    - ``join_next``：与下一形态素同属一个アクセント単位（复合词/接辞合并标记）；
    - ``new_unit``：强制在本形态素处开启新的アクセント単位（起伏式付属語核作第 2 単位等）；
    - ``unit_id``：所属アクセント単位（由 R-MULTI-UNIT 分配）；
    - ``notes``：附加说明（如「词典未收录」）。
    """

    # —— 阶段一字段（不可变语义）——
    idx: int
    morph: str
    lemma: str
    reading: str
    pron: str
    pos: str
    conj_type: str
    conj_form: str
    accent_raw: str
    mora_count: int
    is_unknown: bool
    accent_source: str
    goshu: str = ""
    a_con_type: str = ""
    a_mod_type: str = ""
    pron_raw: str = ""
    # —— 推导状态 ——
    accent: int | None = None
    variants: list[int] = field(default_factory=list)
    derived_by: str | None = None
    claimed: bool = False
    join_next: bool = False          # 与下一形态素同属一个アクセント単位（复合词/接辞）
    new_unit: bool = False           # 强制开启新アクセント単位（起伏式付属語第2単位等）
    unit_id: int | None = None
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_morph(cls, morph: Any) -> "MorphState":
        """由阶段一 ``stage1_analyzer.Morph`` 拷贝构造（鸭子类型，避免模块环依赖）。"""
        return cls(
            idx=morph.idx,
            morph=morph.morph,
            lemma=morph.lemma,
            reading=morph.reading,
            pron=morph.pron,
            pos=morph.pos,
            conj_type=morph.conj_type,
            conj_form=morph.conj_form,
            accent_raw=morph.accent_raw,
            mora_count=morph.mora_count,
            is_unknown=morph.is_unknown,
            accent_source=morph.accent_source,
            goshu=getattr(morph, "goshu", ""),
            a_con_type=getattr(morph, "a_con_type", ""),
            a_mod_type=getattr(morph, "a_mod_type", ""),
            pron_raw=getattr(morph, "pron_raw", morph.pron),
        )

    @property
    def pos_head(self) -> str:
        """品詞第一层（如 ``名詞`` / ``助詞`` / ``動詞``）。"""
        return self.pos.split("-")[0] if self.pos else ""

    @property
    def is_particle_like(self) -> bool:
        """付属語判定（助詞/助動詞/接尾辞）——「付属語不干渉」相关规则的适用对象。"""
        return self.pos_head in ("助詞", "助動詞", "接尾辞")

    @property
    def is_symbol(self) -> bool:
        """记号类（补助记号/记号/空白）判定。"""
        return self.pos_head in ("補助記号", "記号", "空白")

    @property
    def is_sentence_end(self) -> bool:
        """文末记号（句点类）判定——**文境界**：其后形态素开启新アクセント単位。

        アクセント単位は文をまたがない（NHK Ⅲ全般 4.）。読点「、」は文境界では
        ないため対象外（单位切分仍按付属語/复合规则）。记事号自身仍并入前单位。
        """
        if not self.is_symbol:
            return False
        return self.morph in SENTENCE_END_SYMBOLS or "句点" in self.pos

    @property
    def is_nominal(self) -> bool:
        """名词性（名词/代名词）判定——NHK Ⅲ-1（名词接付属語）的适用对象。"""
        return self.pos_head in ("名詞", "代名詞")

    @property
    def is_verb_like(self) -> bool:
        """用言性（动词/形容词/形状詞）判定。"""
        return self.pos_head in ("動詞", "形容詞", "形状詞")


class MorphList(list):
    """规则上下文：形态素工作序列 + アクセント単位 + 规则报告收集。

    即《本项目配置教程.md》3.8.2 中自定义规则 ``match(self, morphs, i)`` 的 ``morphs``。
    """

    def __init__(self, morphs: Iterable[MorphState], input_text: str = "") -> None:
        super().__init__(morphs)
        self.input: str = input_text
        self.units: list[Unit] = []
        self.report: list[dict[str, Any]] = []

    # —— 报告收集 ——

    def add_report(
        self,
        rule: "Rule",
        target: tuple[int, int] | list[int],
        logic: str,
        result: str,
    ) -> None:
        """登记一条命中规则（六字段：rule_id/name/source_ref/target/logic/result）。"""
        targets = list(target)
        self.report.append({
            "rule_id": rule.rule_id,
            "name": rule.name,
            "source_ref": rule.source_ref,
            "target": [int(targets[0]), int(targets[-1])],
            "logic": logic,
            "result": result,
        })

    # —— 渲染（＼=下降核位置，━=平板；多単位用 ・ 分隔，NHK 记号）——

    def surface_text(self, start: int, end: int) -> str:
        """拼接 [start, end] 区间形态素的表層形。"""
        return "".join(self[i].morph for i in range(start, end + 1))

    def render_range(self, start: int, end: int) -> str:
        """渲染 [start, end] 区间为 ＼/━ 记法。

        规则：逐形态素追加発音（きれいな拍串）；对 ``accent > 0`` 的形态素，
        在其第 ``accent`` 拍之后插入 ``＼``（``accent >= 拍数`` 即尾高，位于词末）；
        若区间内无任何下降核 → 末尾追加 ``━``（平板）。
        """
        out: list[str] = []
        has_fall = False
        for i in range(start, end + 1):
            morph = self[i]
            kana = morph.pron
            if not kana:
                continue
            accent = morph.accent
            if accent is not None and accent > 0:
                spans = mora_util.mora_spans(kana)
                if spans:
                    has_fall = True
                    if accent >= len(spans):
                        out.append(kana + "＼")
                    else:
                        cut = spans[accent - 1][1]
                        out.append(kana[:cut] + "＼" + kana[cut:])
                    continue
            out.append(kana)
        text = "".join(out)
        if not has_fall:
            text += "━"
        return text

    def render_units(self) -> str:
        """按 アクセント単位 渲染整句（单位间以 ``・`` 分隔，NHK 记号）。"""
        return "・".join(
            self.render_range(unit.start, unit.end) for unit in self.units
        )


class Rule(ABC):
    """规则基类（接口契约见《本项目配置教程.md》3.8.2）。"""

    rule_id: str = ""
    name: str = ""
    source_ref: str = ""
    priority: int = 0                     # 数值越大越先匹配（遍内排序）
    phase: RulePhase = RulePhase.DERIVATION
    whole_sequence: bool = False          # True：整句规则，在逐 idx 扫描后执行
    config_section: str = ""              # 非空时由注册表注入同名配置节到 self.options
    options: dict[str, Any] = {}          # 由注册表注入（不要在此默认值上原地修改）

    @abstractmethod
    def match(self, morphs: MorphList, i: int) -> bool:
        """确定性条件判断；返回 True 才触发。禁止推测/随机。"""

    @abstractmethod
    def apply(self, morphs: MorphList, i: int) -> None:
        """改写调型（``morphs[i].accent`` 等）并登记规则报告（``morphs.add_report``）。"""

    def describe(self) -> str:
        """单行描述（供注册表调试打印）。"""
        return f"{self.rule_id} (priority={self.priority}, phase={self.phase.value})"
