"""双阶段管线编排：stage1 → （同形語修正） → stage2 → 组装双产物。

契约（``AGENT.md`` 3.2 /《本项目 unidic_and_f0 部分启动教程.md》3.4）：

- 对外 Python API：``run_pipeline(text) -> (accent_json, rule_report)``；
- 阶段一（``stage1_analyzer``）产出「资料一」；
  阶段二（``stage2_rules``）以四合一确定性规则引擎推导东京式调型；
- 产物一 ``audio_accent.json``：总 AGENTS.md §7.4 简化格式
  （``idx`` / ``morph`` / ``lemma`` / ``morph_reading`` / ``pos`` / ``accent`` /
  ``variants`` / ``ruby_pairs``；未收录词附可选 ``notes``）；
- 产物二 ``rule_report.json``：六字段规则概要报告
  （``rule_id`` / ``name`` / ``source_ref`` / ``target`` / ``logic`` / ``result``）；
- 保存路径一律由 ``env_util.build_save_dir``（test.env 三值拼接）决定，禁止硬编码；
  :func:`run_pipeline` 不写盘（纯 API），CLI（``init.py``）负责写盘。
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import compound_verb
import env_util
import mora_util
import numeral
import resegment
import ruby_util
import stage1_analyzer
from stage2_rules import load_registry, run_engine
from stage2_rules.base import MorphList, MorphState

logger = logging.getLogger(__name__)

#: 产物文件名（总 AGENTS.md §8 Storage 布局）
ACCENT_FILENAME = "audio_accent.json"
REPORT_FILENAME = "rule_report.json"


@dataclass
class PipelineResult:
    """完整管线结果：双产物 + 阶段一展示行（供 CLI 三段打印）。"""

    accent_json: dict[str, Any]
    rule_report: dict[str, Any] | None
    raw_lines: tuple[str, ...]


def run_pipeline(
    text: str,
    *,
    config: dict[str, Any] | None = None,
    save_dir: str | Path | None = None,
    write_report: bool = True,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """契约 API（启动教程 3.4）：返回 ``(accent_json, rule_report)``。

    ``save_dir`` 提供时同时写盘两个产物；``write_report=False`` 时
    ``rule_report`` 为 None 且不写报告文件（CLI ``--no-report``）。
    """
    result = run_pipeline_full(
        text, config=config, save_dir=save_dir, write_report=write_report
    )
    return result.accent_json, result.rule_report


#: 分析锁：MeCab Tagger 为进程内共享实例（C++ 层非线程安全），
#: 服务化部署（多线程/协程并发调用 analyze_text）时须串行化解析；
#: 单请求耗时毫秒级，对吞吐影响可忽略。
_ANALYZE_LOCK = threading.Lock()


def _run_context(
    text: str, config: dict[str, Any] | None = None
) -> tuple[MorphList, Any, dict[str, Any]]:
    """内部：运行双阶段管线，返回 ``(规则上下文, 阶段一结果, 生效配置)``。"""
    if not text or not text.strip():
        raise ValueError("输入文本为空，无法运行双阶段管线")
    config = config if config is not None else env_util.load_rules_config()

    with _ANALYZE_LOCK:
        # 阶段一：词典确切匹配（禁止调型推测）
        tagger = stage1_analyzer.build_tagger()
        stage1_result = stage1_analyzer.analyze(
            text, tagger, config.get("homograph_overrides", {})
        )

        # 阶段二：确定性规则引擎（两遍执行）
        ctx = MorphList(
            (MorphState.from_morph(m) for m in stage1_result.morphs),
            input_text=text,
        )
        # 预处理：真未收录整词的确定性词典再切分（rules_config.json 的 resegment.enabled 开关）
        if bool((config.get("resegment") or {}).get("enabled", True)):
            resegment.resegment_unknowns(ctx, tagger, config.get("homograph_overrides", {}))
        # 预处理：阿拉伯数字链＋助数詞 → NHK Ⅱ 合成读法（numeral.enabled 开关）
        if bool((config.get("numeral") or {}).get("enabled", True)):
            numeral.merge_numerals(ctx)
        # 预处理：多调型複合動詞 → 首位動詞规则裁定（compound_verb.enabled 开关）
        if bool((config.get("compound_verb") or {}).get("enabled", True)):
            compound_verb.apply_compound_verb_rule(
                ctx, tagger, config.get("homograph_overrides", {})
            )
        rules = load_registry(config)
        run_engine(ctx, rules)
    return ctx, stage1_result, config


def run_pipeline_full(
    text: str,
    *,
    config: dict[str, Any] | None = None,
    save_dir: str | Path | None = None,
    write_report: bool = True,
) -> PipelineResult:
    """完整入口：额外返回阶段一展示行（``PipelineResult.raw_lines``）。

    :raises ValueError: 文本为空或全空白。
    :raises stage1_analyzer.Stage1Error: 词典缺失或 MeCab 初始化失败。
    """
    ctx, stage1_result, _config = _run_context(text, config)

    accent_json = assemble_accent_json(ctx)
    rule_report = assemble_rule_report(ctx) if write_report else None

    if save_dir is not None:
        write_artifacts(Path(save_dir), accent_json, rule_report)

    return PipelineResult(
        accent_json=accent_json,
        rule_report=rule_report,
        raw_lines=stage1_result.raw_lines,
    )


#: ``analyze_text`` 输出结构的契约版本（字段增删/语义变更时升版，见 ENGINE_USAGE.md）
SERVICE_API_VERSION = "1.0"


def analyze_text(text: str, *, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """【服务层唯一入口】分析原始日语文本，返回含 ``text`` + ``tokens`` 的 dict。

    - 输入：原始日语文本（可含标点与换行；换行按「行=句」处理，逐行分析后合并）；
    - 输出：``{"version": ..., "text": <原文本>, "tokens": [...]}``——
      每个 token 含表記/读音/词性/声调核位置（``accent``）/变体/振假名，
      以及**音拍级 H/L 展开**（``moras`` + ``pitch``）与所属アクセント単位（``unit``）；
    - 内部完成：MeCab 分词 → UniDic 调型 → 规则引擎推导 → 音拍级 H/L 展开；
    - 确定性：同一输入必得同一输出；不做任何调型推测（禁用 s2ya/sy2a）。

    字段级契约与 H/L 展开规则见 ``docs/ENGINE_USAGE.md``（服务层只允许调用本函数）。

    :raises ValueError: 文本为空或全空白行。
    :raises stage1_analyzer.Stage1Error: 词典缺失或 MeCab 初始化失败。
    """
    lines = [line for line in text.splitlines() if line.strip()] if text else []
    if not lines:
        raise ValueError("输入文本为空，无法分析")

    tokens: list[dict[str, Any]] = []
    idx_offset = 0
    unit_offset = 0
    for line in lines:
        ctx, _stage1_result, _config = _run_context(line, config)
        tokens.extend(assemble_service_tokens(ctx, idx_offset=idx_offset, unit_offset=unit_offset))
        idx_offset += len(ctx)
        unit_offset += (ctx.units[-1].unit_id + 1) if ctx.units else 0
    return {"version": SERVICE_API_VERSION, "text": text, "tokens": tokens}


def _unit_h_l(ctx: MorphList, unit: Any) -> list[list[str]]:
    """计算一个アクセント単位的音拍级 H/L 序列，并按形态素切分返回。

    规则（东京式，単位内重置）：

    - 无下降核（平板型）→ 第1拍 L、其余 H；
    - 核在第 1 拍（頭高型）→ 第1拍 H、其余 L；
    - 核在第 F 拍（2≤F≤拍数）→ 前 F 拍「L H…H」、其后全 L；
    标点等无读音形态素返回空列表。
    """
    moras_per: list[list[str]] = [
        mora_util.split_moras(ctx[k].pron) for k in range(unit.start, unit.end + 1)
    ]
    total = sum(len(m) for m in moras_per)
    if total == 0:
        return [[] for _ in moras_per]

    fall = 0
    offset = 0
    for k in range(unit.start, unit.end + 1):
        morph = ctx[k]
        if fall == 0 and morph.accent is not None and morph.accent > 0:
            fall = offset + int(morph.accent)
        offset += len(mora_util.split_moras(morph.pron))

    if fall <= 0:
        hl = ["L"] + ["H"] * (total - 1)
    elif fall == 1:
        hl = ["H"] + ["L"] * (total - 1)
    else:
        f = min(fall, total)
        hl = ["L"] + ["H"] * (f - 1) + ["L"] * (total - f)

    result: list[list[str]] = []
    pos = 0
    for moras in moras_per:
        result.append(hl[pos:pos + len(moras)])
        pos += len(moras)
    return result


def assemble_service_tokens(
    ctx: MorphList, idx_offset: int = 0, unit_offset: int = 0
) -> list[dict[str, Any]]:
    """组装服务契约的 ``tokens`` 列表（字段与 ``audio_accent.json`` 对齐并扩展）。"""
    tokens: list[dict[str, Any]] = []
    for morph in ctx:
        accent = int(morph.accent) if morph.accent is not None else 0
        item: dict[str, Any] = {
            "idx": idx_offset + morph.idx,
            "morph": morph.morph,
            "lemma": morph.lemma,
            "morph_reading": morph.pron,
            "pos": morph.pos.replace("-", "*"),
            "accent": accent,
            "variants": list(morph.variants),
            "ruby_pairs": ruby_util.align_ruby_pairs(morph.morph, morph.reading or morph.pron),
            "moras": mora_util.split_moras(morph.pron),
            "pitch": [],
            "unit": unit_offset + (morph.unit_id if morph.unit_id is not None else 0),
        }
        if morph.notes:
            item["notes"] = list(morph.notes)
        tokens.append(item)

    for unit in ctx.units:
        contours = _unit_h_l(ctx, unit)
        for k, hl in zip(range(unit.start, unit.end + 1), contours):
            tokens[k]["pitch"] = hl
    return tokens


def _render_multi_fall(kana: str, falls: list[int]) -> str:
    """在假名串的指定拍（1 起，可多个）之后插入 ＼；无核则末尾 ━（平板型）。"""
    spans = mora_util.mora_spans(kana)
    if not spans:
        return kana + "━"
    if not falls:
        return kana + "━"
    cuts = sorted({spans[min(f, len(spans)) - 1][1] for f in falls}, reverse=True)
    out = kana
    for cut in cuts:
        out = out[:cut] + "＼" + out[cut:]
    return out


def show_accent(data: dict[str, Any]) -> str:
    """将 :func:`analyze_text` 的返回 JSON 转换为直观的 NHK 音调标注文本。

    输出格式（确定性、可直接展示）::

        【输入】米を盛る
        【NHK】コメ＼オ・モル━
          [単位0] 米を：コメ＼オ（L H L）
          [単位1] 盛る：モル━（L H）

    记号说明：``＼``=下降核位置（其后下降；位于词末即尾高）；``━``=平板型；
    ``・``=アクセント単位分界。由 tokens 的 ``accent``/``moras``/``pitch``/``unit``
    重建，与引擎内部 NHK 记号渲染（rule_report 的 result）同源与同规则；
    标点等无读音形態素并入其所属単位（不占音拍、不参与记号）。

    :raises ValueError: ``data`` 非 :func:`analyze_text` 的返回结构（缺 text/tokens 或 tokens 为空）。
    """
    tokens = data.get("tokens") if isinstance(data, dict) else None
    if not isinstance(tokens, list) or not tokens:
        raise ValueError("show_accent 需要 analyze_text 的返回 JSON（dict，含非空 tokens）")

    # 按 unit 值分组（tokens 有序且 unit 单调不减，此处按「连续相同」分组）
    units: list[list[dict[str, Any]]] = []
    for token in tokens:
        if not units or token.get("unit") != units[-1][0].get("unit"):
            units.append([token])
        else:
            units[-1].append(token)

    notations: list[str] = []
    details: list[str] = []
    for group in units:
        unit_id = group[0].get("unit", 0)
        surface = "".join(str(t.get("morph", "")) for t in group)
        moras = [m for t in group for m in (t.get("moras") or [])]
        h_l = [p for t in group for p in (t.get("pitch") or [])]

        # 收集単位内全部下降核（付属語決定型等可出现 2 个下降——如 ハレ＼ルデショ＼ー），
        # 与引擎内部 render_range 的渲染语义一致（不使用仅首核的简化）
        falls: list[int] = []
        offset = 0
        for token in group:
            count = len(token.get("moras") or [])
            accent = int(token.get("accent", 0) or 0)
            if accent > 0:
                falls.append(offset + accent)
            offset += count

        if not moras:
            notation = surface              # 标点等无读音单位：直接以表記呈现
        else:
            notation = _render_multi_fall("".join(moras), falls)
        notations.append(notation)

        hl_text = f"（{' '.join(h_l)}）" if h_l else ""
        details.append(f"  [単位{unit_id}] {surface}：{notation}{hl_text}")

    return "\n".join([
        f"【输入】{data.get('text', '')}",
        f"【NHK】{'・'.join(notations)}",
        *details,
    ])


def assemble_accent_json(ctx: MorphList) -> dict[str, Any]:
    """组装 ``audio_accent.json``（总 AGENTS.md §7.4 简化格式）。

    - ``morph_reading`` 取**発音**（与验收样例「を→オ」「米→コメ」一致）；
    - ``pos`` 的 ``-`` 分隔符按契约转换为 ``*``（如 ``名詞*普通名詞*一般``）；
    - ``ruby_pairs`` 由 :func:`ruby_util.align_ruby_pairs` 对齐（かな取**読み**）；
    - 未收录/补偿说明写入可选 ``notes`` 字段。
    """
    json_data: list[dict[str, Any]] = []
    for morph in ctx:
        accent = int(morph.accent) if morph.accent is not None else 0
        item: dict[str, Any] = {
            "idx": morph.idx,
            "morph": morph.morph,
            "lemma": morph.lemma,
            "morph_reading": morph.pron,
            "pos": morph.pos.replace("-", "*"),
            "accent": accent,
            "variants": list(morph.variants),
            "ruby_pairs": ruby_util.align_ruby_pairs(morph.morph, morph.reading or morph.pron),
        }
        if morph.notes:
            item["notes"] = list(morph.notes)
        json_data.append(item)
    return {"input": ctx.input, "json_data": json_data}


def assemble_rule_report(ctx: MorphList) -> dict[str, Any]:
    """组装 ``rule_report.json``（六字段命中规则清单，按触发顺序）。"""
    return {"input": ctx.input, "matched_rules": list(ctx.report)}


def write_artifacts(
    save_dir: Path,
    accent_json: dict[str, Any],
    rule_report: dict[str, Any] | None,
) -> None:
    """写出双产物（UTF-8 / ensure_ascii=False / indent=2）。"""
    save_dir.mkdir(parents=True, exist_ok=True)
    (save_dir / ACCENT_FILENAME).write_text(
        json.dumps(accent_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if rule_report is not None:
        (save_dir / REPORT_FILENAME).write_text(
            json.dumps(rule_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
