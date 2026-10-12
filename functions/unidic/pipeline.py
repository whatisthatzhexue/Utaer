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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import env_util
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
    if not text or not text.strip():
        raise ValueError("输入文本为空，无法运行双阶段管线")
    config = config if config is not None else env_util.load_rules_config()

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
    rules = load_registry(config)
    run_engine(ctx, rules)

    accent_json = assemble_accent_json(ctx)
    rule_report = assemble_rule_report(ctx) if write_report else None

    if save_dir is not None:
        write_artifacts(Path(save_dir), accent_json, rule_report)

    return PipelineResult(
        accent_json=accent_json,
        rule_report=rule_report,
        raw_lines=stage1_result.raw_lines,
    )


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
