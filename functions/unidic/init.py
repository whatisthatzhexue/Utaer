"""双阶段管线 CLI 入口（《本项目 unidic_and_f0 部分启动教程.md》3.3）。

用法（在 ``Utaer/functions/unidic/`` 下执行）::

    python3 init.py --text "米を盛る"
    python3 init.py --input 歌詞.txt [--user <值>] [--audio-id <值>] [--no-report]

行为：

1. 读取待分析文本（``--text`` 或 UTF-8 文件 ``--input``；多行逐行分析后合并）；
2. 运行双阶段管线（阶段一词典确切匹配 → 阶段二确定性规则引擎）；
3. 控制台依次打印「阶段一：词典基础分析」→「分析结果 audio_accent.json」→
   「规则概要报告 rule_report.json」（``--no-report`` 时省略报告）；
4. 按 ``test.env``（项目根目录）三值拼接的保存路径写出产物
   （``--user`` / ``--audio-id`` 可覆盖），禁止硬编码路径。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# 同目录模块导入（脚本位于 functions/unidic/，从任意工作目录运行均可）
sys.path.insert(0, str(Path(__file__).resolve().parent))

from env_util import EnvError, build_save_dir, load_rules_config, load_test_env  # noqa: E402
from pipeline import run_pipeline_full  # noqa: E402
from stage1_analyzer import Stage1Error  # noqa: E402

SECTION_STAGE1 = "===== 阶段一：词典基础分析（确切匹配，禁止推测）====="
SECTION_ACCENT = "===== 分析结果 audio_accent.json（东京式声调）====="
SECTION_REPORT = "===== 规则概要报告 rule_report.json（成功匹配并触发的规则清单）====="


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="init.py",
        description=(
            "Utaer unidic_and_f0 双阶段声调分析："
            "阶段一 tdmelodic 组合词典确切匹配（禁止调型推测）→ 阶段二确定性规则引擎"
        ),
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="直接传入待分析文本")
    source.add_argument("--input", metavar="FILE", help="从 UTF-8 文本文件读取待分析文本")
    parser.add_argument("--user", help="覆盖 test.env 的 TEST_USER_ID")
    parser.add_argument("--audio-id", help="覆盖 test.env 的 TEST_AUDIO_ID")
    parser.add_argument(
        "--no-report", action="store_true", help="不附带输出规则概要报告（默认附带）"
    )
    parser.add_argument("--verbose", action="store_true", help="输出调试日志")
    return parser


def _read_source_text(args: argparse.Namespace) -> str:
    """读取待分析文本；文件不存在或编码错误 → :class:`SystemExit`（exit 1）。"""
    if args.text is not None:
        return args.text
    path = Path(args.input)
    if not path.is_file():
        raise SystemExit(f"[ERROR] 输入文件不存在：{path}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SystemExit(f"[ERROR] 读取输入文件失败（需 UTF-8，无 BOM）：{exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    # UTF-8 控制台（防排错表「输出乱码」）
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # pragma: no cover - 非常规重定向
            pass
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(levelname)s] %(message)s",
    )

    text = _read_source_text(args)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        print("[ERROR] 输入文本为空", file=sys.stderr)
        return 1

    # 保存路径：test.env 三值拼接（反斜杠归一化），CLI 可覆盖
    env = load_test_env()
    try:
        save_dir = build_save_dir(env=env, user=args.user, audio_id=args.audio_id)
    except EnvError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    config = load_rules_config()

    # 逐行运行管线并合并（idx 连续递增，规则 target 同步平移）
    raw_lines_all: list[str] = []
    merged_data: list[dict] = []
    merged_rules: list[dict] = []
    offset = 0
    try:
        for line in lines:
            result = run_pipeline_full(
                line, config=config, save_dir=None, write_report=not args.no_report
            )
            raw_lines_all.extend(result.raw_lines)
            for item in result.accent_json["json_data"]:
                shifted = dict(item)
                shifted["idx"] = offset + int(item["idx"])
                merged_data.append(shifted)
            if result.rule_report is not None:
                for rule in result.rule_report["matched_rules"]:
                    shifted_rule = dict(rule)
                    start, end = rule["target"]
                    shifted_rule["target"] = [offset + int(start), offset + int(end)]
                    merged_rules.append(shifted_rule)
            offset += len(result.accent_json["json_data"])
    except (ValueError, Stage1Error) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    accent_json = {"input": text, "json_data": merged_data}
    rule_report = {"input": text, "matched_rules": merged_rules} if not args.no_report else None

    # 三段打印
    print(SECTION_STAGE1)
    for line in raw_lines_all:
        print(line)
    print()
    print(SECTION_ACCENT)
    print(json.dumps(accent_json, ensure_ascii=False, indent=2))
    if rule_report is not None:
        print()
        print(SECTION_REPORT)
        print(json.dumps(rule_report, ensure_ascii=False, indent=2))

    # 写盘
    try:
        save_dir.mkdir(parents=True, exist_ok=True)
        (save_dir / "audio_accent.json").write_text(
            json.dumps(accent_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if rule_report is not None:
            (save_dir / "rule_report.json").write_text(
                json.dumps(rule_report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    except OSError as exc:
        print(f"[ERROR] 写入产物失败（{save_dir}）：{exc}", file=sys.stderr)
        return 1

    print(f"\n[INFO] 产物已写入：{save_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
