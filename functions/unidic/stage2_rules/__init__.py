"""阶段二规则引擎：注册表（registry）与两遍执行引擎（run_engine）。

契约（``AGENT.md`` 3.4、《本项目配置教程.md》3.8）：

- 规则注册表按优先级加载全部规则：内建六模块（compound / conjugation / particles /
  nucleus_legality / multi_unit / fallback）→ ``rules_config.json`` 的 ``rule_overrides``
  （改优先级 / 禁用）→ ``custom_rules_dir`` 自定义规则目录自动加载；
- 排序键 ``(-priority, rule_id)``，保证平局时结果确定；
- 默认优先级（数值越大越先匹配）：核合法性（后处理校验）> 活用形 > 复合词 > 付属語 >
  数詞 > 多单位 > 語種倾向兜底 > 默认平板；
- **两遍执行机制**：``nucleus_legality`` 是「后处理校验型」但优先级最高——
  实现上用 ``Rule.phase`` 把执行分为两遍：第一遍按优先级执行推导型规则（DERIVATION，
  含整句规则），第二遍由校验型规则（VALIDATION）做最终扫掠校验，
  保证「核不允许落在 ン・ッ・ー・二重母音副音・无声化拍之后」的修正始终生效。

注册表验证（教程 4.3）::

    python3 -c "from stage2_rules import registry; print([r.rule_id for r in registry])"
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# —— 路径保护：保证模块目录（functions/unidic/）在 sys.path 上，可导入 env_util / mora_util ——
_PKG_DIR = Path(__file__).resolve().parent          # stage2_rules/
_MODULE_DIR = _PKG_DIR.parent                        # functions/unidic/
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

from env_util import load_rules_config  # noqa: E402  (路径保护之后导入)
from stage2_rules.base import (  # noqa: E402
    MorphList,
    MorphState,
    Rule,
    RulePhase,
    Unit,
    parse_accent_value,
)

#: 内建规则模块（加载顺序仅影响平局时的采集顺序；最终以 (-priority, rule_id) 稳定排序）
BUILTIN_RULE_MODULES: tuple[str, ...] = (
    "compound",
    "conjugation",
    "particles",
    "nucleus_legality",
    "multi_unit",
    "fallback",
)

__all__ = [
    "BUILTIN_RULE_MODULES",
    "MorphList",
    "MorphState",
    "Rule",
    "RulePhase",
    "Unit",
    "load_registry",
    "load_custom_rules",
    "parse_accent_value",
    "registry",
    "run_engine",
]


def _collect_rules_from_module(module: Any) -> list[Rule]:
    """实例化模块内定义的 :class:`Rule` 子类（仅收集本模块定义的类，跳过导入的基类）。"""
    rules: list[Rule] = []
    for name in dir(module):
        obj = getattr(module, name)
        if (
            inspect.isclass(obj)
            and issubclass(obj, Rule)
            and obj is not Rule
            and obj.__module__ == module.__name__
            and not inspect.isabstract(obj)
        ):
            try:
                rules.append(obj())
            except TypeError as exc:  # 构造签名不符
                logger.warning("规则类 %s.%s 实例化失败：%s", module.__name__, name, exc)
    return rules


def load_custom_rules(custom_dir: Path) -> list[Rule]:
    """加载 ``custom_rules_dir`` 下的自定义规则（``*.py``，逐文件容错）。

    文件以 ``importlib.util.spec_from_file_location`` 加载为
    ``_unidic_custom_<stem>`` 命名空间模块，其中 ``Rule`` 子类被实例化注册；
    单个文件加载失败仅告警，不阻断管线（教程 3.8.2 的扩展点）。
    """
    rules: list[Rule] = []
    if not custom_dir.is_dir():
        return rules
    for py_file in sorted(custom_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        mod_name = f"_unidic_custom_{py_file.stem}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, py_file)
            if spec is None or spec.loader is None:
                logger.warning("自定义规则文件无法加载：%s", py_file)
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            file_rules = _collect_rules_from_module(module)
            rules.extend(file_rules)
            logger.info("自定义规则已加载：%s（%d 条）", py_file.name, len(file_rules))
        except Exception as exc:  # 自定义代码可能抛出任意异常；逐文件容错
            logger.warning("自定义规则文件 %s 加载失败：%s", py_file, exc)
    return rules


def load_registry(config: dict | None = None) -> list[Rule]:
    """按配置构建规则列表（不污染模块级 :data:`registry`）。

    - 加载内建六模块与自定义规则目录；
    - 应用 ``rule_overrides``（``priority`` 覆盖 / ``enabled: false`` 禁用）；
    - 校验 ``rule_id`` 唯一性与 ``source_ref`` 非空（契约「规则可追溯」）；
    - 注入 ``config_section`` 配置节到 ``rule.options``；
    - 稳定排序 ``(-priority, rule_id)``。
    """
    config = config if config is not None else load_rules_config()

    candidates: list[Rule] = []
    for mod_name in BUILTIN_RULE_MODULES:
        try:
            module = importlib.import_module(f"stage2_rules.{mod_name}")
        except Exception as exc:  # 单模块异常不阻断整体注册
            logger.warning("内建规则模块 %s 加载失败：%s", mod_name, exc)
            continue
        candidates.extend(_collect_rules_from_module(module))

    custom_dir_cfg = str(config.get("custom_rules_dir", "stage2_rules/custom"))
    custom_dir = _MODULE_DIR / custom_dir_cfg
    candidates.extend(load_custom_rules(custom_dir))

    overrides = config.get("rule_overrides", {}) or {}
    if not isinstance(overrides, dict):
        logger.warning("rule_overrides 应为对象，已忽略")
        overrides = {}

    rules: list[Rule] = []
    seen: set[str] = set()
    for rule in candidates:
        if not rule.rule_id:
            logger.warning("规则 %s 缺少 rule_id，已跳过", type(rule).__name__)
            continue
        override = overrides.get(rule.rule_id, {})
        if isinstance(override, dict):
            if override.get("enabled") is False:
                continue
            if "priority" in override:
                try:
                    rule.priority = int(override["priority"])
                except (TypeError, ValueError):
                    logger.warning("%s 的 priority 覆盖值非法：%r", rule.rule_id, override["priority"])
        if rule.rule_id in seen:
            logger.warning("规则 rule_id 重复：%s（后者已跳过）", rule.rule_id)
            continue
        if not rule.source_ref:
            logger.warning("规则 %s 缺少 source_ref（契约要求可追溯）", rule.rule_id)
        if rule.config_section:
            section = config.get(rule.config_section, {})
            rule.options = dict(section) if isinstance(section, dict) else {}
        seen.add(rule.rule_id)
        rules.append(rule)

    for rule_id in overrides:
        if rule_id not in seen:
            logger.warning("rule_overrides 引用了不存在的规则：%s", rule_id)

    rules.sort(key=lambda r: (-r.priority, r.rule_id))
    return rules


def run_engine(ctx: MorphList, rules: list[Rule] | None = None) -> None:
    """两遍执行引擎（确定性；同输入必得同输出）。

    第一遍（DERIVATION，逐 idx 扫描）：按 ``(-priority, rule_id)`` 顺序询问规则，
    首个 ``match`` 且未占用者 ``apply``；已推导（``accent is not None``）或已
    被占用（``claimed``）的形态素跳过。
    第二遍（DERIVATION 中的整句规则，如 R-MULTI-UNIT）：在扫描后按序执行。
    第三遍（VALIDATION）：校验型规则对每个形态素循环 ``match``/``apply`` 直至合法
    （核移位修正始终在全部推导之后生效，见模块 docstring）。
    """
    if rules is None:
        rules = registry

    derivation = [r for r in rules if r.phase is RulePhase.DERIVATION and not r.whole_sequence]
    sequence = [r for r in rules if r.phase is RulePhase.DERIVATION and r.whole_sequence]
    validation = [r for r in rules if r.phase is RulePhase.VALIDATION]

    # 第一遍：推导（逐形态素）
    for i in range(len(ctx)):
        morph = ctx[i]
        if morph.claimed or morph.accent is not None:
            continue
        for rule in derivation:
            if rule.match(ctx, i):
                rule.apply(ctx, i)
                break

    # 第二遍：整句规则（単位切分等）
    for rule in sequence:
        try:
            rule.apply(ctx, 0)
        except Exception as exc:  # 规则异常不应阻断管线，但需可见
            logger.error("整句规则 %s 执行失败：%s", rule.rule_id, exc)

    # 第三遍：后处理校验（如核合法性；可多轮修正至合法）
    for rule in validation:
        for i in range(len(ctx)):
            guard = 0
            while rule.match(ctx, i) and guard < 16:
                rule.apply(ctx, i)
                guard += 1


#: 模块级注册表：导入时按默认配置构建一次（教程 4.3 的验证命令直接引用）
registry: list[Rule] = load_registry()
