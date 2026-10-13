"""开发期环境变量与路径工具（unidic_and_f0 模块）。

职责（总 AGENTS.md §6 / 《本项目配置教程.md》3.6）：

- 由模块文件位置上溯解析**项目根目录**与**模块目录**（禁止硬编码路径）；
- 读取项目根目录 ``test.env`` 中的三个开发期约定值
  （``TEST_USER_ID`` / ``TEST_AUDIO_ID`` / ``TEST_SAVE_PATH``）；
- 拼接产物保存目录 ``<项目根>/fast-api/audio/<user-id>/<audio-id>/``；
  其中 ``TEST_SAVE_PATH`` 按约定写作 Windows 风格（``fast-api\\audio\\``），
  在 Linux（WSL）下必须将 ``\\`` 归一化为 ``/``，否则会生成带字面量反斜杠的目录名；
- 读取规则引擎配置 ``rules_config.json``（模块目录下，含同形語修正表与规则开关）。

本模块只使用标准库（模块 .venv 为裸环境，不引入 python-dotenv 等额外依赖）。
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

#: 开发期环境变量文件名（项目根目录，允许提交，见总 AGENTS.md §6）
TEST_ENV_FILENAME = "test.env"
#: 规则引擎配置文件（模块目录，见《本项目配置教程.md》3.8）
RULES_CONFIG_FILENAME = "rules_config.json"

#: 模块目录（functions/unidic/）——由本文件位置解析，禁止硬编码
MODULE_DIR: Path = Path(__file__).resolve().parent
#: 项目根目录（Utaer/）——模块目录上溯两层
PROJECT_ROOT: Path = MODULE_DIR.parent.parent

#: ``TEST_SAVE_PATH`` 缺失时的默认相对路径（与 test.env 约定一致）
DEFAULT_SAVE_PATH = "fast-api/audio"

#: 规则引擎默认配置（rules_config.json 缺失/损坏时的回退值，保证管线可运行）
DEFAULT_RULES_CONFIG: dict = {
    "rule_overrides": {},          # {rule_id: {"priority": int, "enabled": bool}}
    "custom_rules_dir": "stage2_rules/custom",
    "homograph_overrides": {},     # {表層形: {"reading": ..., "pron": ..., "accent_raw": ...}}
    "resegment": {"enabled": True},
    "nucleus_legality": {"avoid_devoiced": False},
    # 数詞读法预处理（阿拉伯数字链＋助数詞 → NHK Ⅱ 合成读法；10選→ジュッセン）
    "numeral": {"enabled": True},
    # 複合動詞首位規則预处理（多调型動詞 token → 首位動詞裁定）
    "compound_verb": {"enabled": True},
    # 复合词：NHK Ⅰ複合名詞①平板例外表（〜語/化/間/顔/級/金/性/製/的）优先于词典 C 值
    "compound": {"nhk_flat_exceptions_priority": True},
}


class EnvError(RuntimeError):
    """开发期环境约定缺失或不合法（test.env / 保存路径拼接等）。"""


def get_project_root() -> Path:
    """返回项目根目录（Utaer/）。"""
    return PROJECT_ROOT


def get_module_dir() -> Path:
    """返回模块目录（functions/unidic/）。"""
    return MODULE_DIR


def parse_test_env_text(text: str) -> dict[str, str]:
    """解析 ``test.env`` 文本为键值字典。

    格式：每行 ``KEY=VALUE``；空行与 ``#`` 开头行忽略；值不做转义处理
    （``TEST_SAVE_PATH`` 的反斜杠在 :func:`build_save_dir` 中统一归一化）。
    """
    env: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            logger.warning("test.env 存在异常行（缺少 '='）：%s", raw_line)
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def load_test_env(root: Path | None = None) -> dict[str, str]:
    """读取项目根目录 ``test.env``；缺失或不可读时返回空字典并告警。"""
    root = root or PROJECT_ROOT
    path = root / TEST_ENV_FILENAME
    if not path.exists():
        logger.warning("未找到开发期环境文件：%s（将依赖 CLI 覆盖参数）", path)
        return {}
    try:
        return parse_test_env_text(path.read_text(encoding="utf-8"))
    except OSError as exc:
        logger.warning("读取 %s 失败：%s", path, exc)
        return {}


def build_save_dir(
    root: Path | None = None,
    env: dict[str, str] | None = None,
    user: str | None = None,
    audio_id: str | None = None,
) -> Path:
    """拼接开发期产物保存目录：``<项目根>/<TEST_SAVE_PATH>/<user>/<audio_id>/``。

    - ``TEST_SAVE_PATH`` 的反斜杠归一化为 ``/``（跨平台安全）；
    - ``user`` / ``audio_id`` 参数优先于 ``test.env`` 中的值（CLI 覆盖）；
    - 任一必需值缺失 → :class:`EnvError`（调用方负责给出友好提示）。
    """
    root = root or PROJECT_ROOT
    env = env or {}

    save_path = env.get("TEST_SAVE_PATH", DEFAULT_SAVE_PATH).replace("\\", "/").strip("/")
    resolved_user = user or env.get("TEST_USER_ID", "")
    resolved_audio_id = audio_id or env.get("TEST_AUDIO_ID", "")
    if not resolved_user or not resolved_audio_id:
        raise EnvError(
            "缺少 TEST_USER_ID / TEST_AUDIO_ID："
            "test.env 未提供对应值，且未通过 --user / --audio-id 覆盖"
        )
    return root / save_path / resolved_user / resolved_audio_id


def load_rules_config(path: Path | None = None) -> dict:
    """读取 ``rules_config.json``；缺失或损坏时回退 :data:`DEFAULT_RULES_CONFIG` 并告警。

    配置文件为合法 JSON（教程中的 jsonc 注释仅为示意）。
    已知的嵌套配置键（``resegment`` / ``nucleus_legality``）做一层浅合并，
    未知键原样保留（前向兼容）。
    """
    path = path or (MODULE_DIR / RULES_CONFIG_FILENAME)
    config: dict = copy.deepcopy(DEFAULT_RULES_CONFIG)
    if not path.exists():
        logger.warning("未找到 %s，使用内置默认配置", path)
        return config
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("%s 解析失败（%s），回退内置默认配置", path, exc)
        return config
    if not isinstance(data, dict):
        logger.warning("%s 顶层结构应为对象，回退内置默认配置", path)
        return config
    for key, value in data.items():
        if (
            key in ("resegment", "nucleus_legality", "compound", "numeral", "compound_verb")
            and isinstance(value, dict)
            and isinstance(config.get(key), dict)
        ):
            config[key].update(value)
        else:
            config[key] = value
    return config
