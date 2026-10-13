"""模块自检（轻量回归，无第三方测试框架依赖）：``python3 selfcheck.py``

覆盖范围（按里程碑验收与契约不变量）：

1. ``mora_util`` 纯函数（括号声调解码/拍数/特殊拍/二重母音副音/＼━渲染），
   对照实测样本（tdmelodic 编码实测 + 用户确认词）；
2. ``ruby_util`` 对齐边界（を/盛る/食べる/熟字訓/送假名歧义兜底/无读音）；
3. 验收样例 1「米を盛る」：``audio_accent.json`` 与 ``rule_report.json``
   逐字段对照《启动教程》4.1 样例（规则报告四条含 logic 文案）；
4. 验收样例 2「住民税」：词典路径（R-LEX-DICT）与复合词路径
   （确定性分解 → R-COMPOUND-C3 → R-NUCLEUS-SPECIAL）双路径；
5. 契约不变量：每アクセント単位至多一个核；确定性（同输入两次输出全等）；
6. 未收录兜底：notes 标注「词典未收录」；語種倾向规则（KANGO11 / GAIRAI3）；
7. 注册表：《本项目配置教程.md》4.3 加载验证、rule_overrides 优先级/禁用、
   custom_rules_dir 自定义规则自动加载；
8. 产物写盘与 JSON 可解析（等价 ``python3 -m json.tool``）。

退出码：0=全部通过；1=存在失败；2=环境缺失（如未安装组合词典）。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_util  # noqa: E402
import mora_util  # noqa: E402
import pipeline  # noqa: E402
import resegment  # noqa: E402
import ruby_util  # noqa: E402
import stage1_analyzer  # noqa: E402
from stage2_rules import load_registry, run_engine  # noqa: E402
from stage2_rules.base import MorphList, MorphState  # noqa: E402

_FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    """断言式检查：打印 PASS/FAIL；失败时记录名称与细节。"""
    if condition:
        print(f"[PASS] {name}")
    else:
        print(f"[FAIL] {name}" + (f" — {detail}" if detail else ""))
        _FAILURES.append(name)


def _section(title: str) -> None:
    print(f"\n===== {title} =====")


# ------------------------------------------- 0. 服务层入口契约（analyze_text）
def check_service_api(config: dict) -> None:
    _section("服务层唯一入口 analyze_text（text+tokens，音拍级 H/L 展开）")

    r = pipeline.analyze_text("米を盛る")
    check("顶层结构 version/text/tokens",
          sorted(r.keys()) == ["text", "tokens", "version"]
          and r["version"] == pipeline.SERVICE_API_VERSION)
    check("text 原样保留", r["text"] == "米を盛る")
    tokens = r["tokens"]
    check("米：moras+pitch L,H（尾高核显现）",
          tokens[0]["moras"] == ["コ", "メ"] and tokens[0]["pitch"] == ["L", "H"]
          and tokens[0]["unit"] == 0)
    check("を：同単位継続 L", tokens[1]["pitch"] == ["L"] and tokens[1]["unit"] == 0)
    check("盛る：平板単位 L,H", tokens[2]["pitch"] == ["L", "H"] and tokens[2]["unit"] == 1)

    r2 = pipeline.analyze_text("私は学生です。")
    by_morph = {x["morph"]: x for x in r2["tokens"]}
    check("学生です：ガクセイデ＼ス（L H H H + H L）",
          by_morph["学生"]["pitch"] == ["L", "H", "H", "H"]
          and by_morph["です"]["pitch"] == ["H", "L"])
    check("标点：空 moras/pitch 且归属単位",
          by_morph["。"]["moras"] == [] and by_morph["。"]["pitch"] == []
          and by_morph["。"]["unit"] == 1)

    r3 = pipeline.analyze_text("米を盛る\n東京駅")
    check("多行：idx 全句连续", [x["idx"] for x in r3["tokens"]] == [0, 1, 2, 3])
    check("多行：unit 全句连续（第2行从 2 起）", r3["tokens"][3]["unit"] == 2)
    check("頭高展开 東京駅（F=3 → L H H L L L）",
          r3["tokens"][3]["pitch"] == ["L", "H", "H", "L", "L", "L"])
    check("text 保留换行原样", r3["text"] == "米を盛る\n東京駅")

    try:
        pipeline.analyze_text("")
        check("空文本 → ValueError", False)
    except ValueError:
        check("空文本 → ValueError", True)

    check("确定性：两次调用全等", pipeline.analyze_text("米を盛る") == r)


# --------------------------------------- 0.5 show_accent（JSON → NHK 标注文本）
def check_show_accent(config: dict) -> None:
    _section("show_accent：analyze_text JSON → 直观 NHK 音调标注文本")

    result = pipeline.analyze_text("米を盛る")
    expected = (
        "【输入】米を盛る\n"
        "【NHK】コメ＼オ・モル━\n"
        "  [単位0] 米を：コメ＼オ（L H L）\n"
        "  [単位1] 盛る：モル━（L H）"
    )
    check("米を盛る：逐字输出", pipeline.show_accent(result) == expected,
          pipeline.show_accent(result))
    check("私は学生です。：记号行（尾高+助詞/平板+です）",
          "【NHK】ワタシワ━・ガクセイデ＼ス"
          in pipeline.show_accent(pipeline.analyze_text("私は学生です。")))
    check("東京駅：明細（L H H L L L）",
          "[単位0] 東京駅：トーキョ＼ーエキ（L H H L L L）"
          in pipeline.show_accent(pipeline.analyze_text("東京駅")))
    check("多行：三単位记号全句连续",
          "【NHK】コメ＼オ・モル━・トーキョ＼ーエキ"
          in pipeline.show_accent(pipeline.analyze_text("米を盛る\n東京駅")))
    try:
        pipeline.show_accent({})
        check("非法输入 → ValueError", False)
    except ValueError:
        check("非法输入 → ValueError", True)


# ---------------------------------------------------------------- 1. mora_util
def check_mora_util() -> None:
    _section("mora_util 纯函数（括号解码/拍数/判定/渲染）")
    check("解码 ジュ[ーミ]ンゼイ → 核3",
          mora_util.decode_bracket_accent("ジュ[ーミ]ンゼイ") == ("ジューミンゼイ", 3, True))
    check("解码 ク]ーキ → 核1",
          mora_util.decode_bracket_accent("ク]ーキ") == ("クーキ", 1, True))
    check("解码 ガ[クセイ → 平板0",
          mora_util.decode_bracket_accent("ガ[クセイ") == ("ガクセイ", 0, True))
    check("解码 无括号 → None",
          mora_util.decode_bracket_accent("コメ") == ("コメ", None, False))
    check("拍数 ジューミンゼイ=6", mora_util.mora_count("ジューミンゼイ") == 6)
    check("拍数 インターネット=7", mora_util.mora_count("インターネット") == 7)
    check("拍数 ニューガク=4（ニュ=1拍）", mora_util.mora_count("ニューガク") == 4)
    check("特殊拍 ン/ッ/ー",
          mora_util.is_special_mora("ン") and mora_util.is_special_mora("ッ")
          and mora_util.is_special_mora("ー"))
    check("二重母音副音 カイのイ", mora_util.is_diphthong_glide(["カ", "イ"], 1) is True)
    check("非副音 トケイのイ（エ段前，可为核）",
          mora_util.is_diphthong_glide(["ケ", "イ"], 1) is False)
    check("渲染 尾高 コメ→コメ＼", mora_util.render_accent("コメ", 2) == "コメ＼")
    check("渲染 平板 モル→モル━", mora_util.render_accent("モル", 0) == "モル━")
    check("渲染 中高 タベル→タベ＼ル", mora_util.render_accent("タベル", 2) == "タベ＼ル")
    check("渲染 頭高? シテイセキ→シテ＼イセキ",
          mora_util.render_accent("シテイセキ", 2) == "シテ＼イセキ")


# ---------------------------------------------------------------- 2. ruby_util
def check_ruby_util() -> None:
    _section("ruby_util 表記-かな 对齐")
    check("を → [[null,を]]", ruby_util.align_ruby_pairs("を", "ヲ") == [[None, "を"]])
    check("米 → [[米,こめ]]", ruby_util.align_ruby_pairs("米", "コメ") == [["米", "こめ"]])
    check("盛る → 送假名逐字",
          ruby_util.align_ruby_pairs("盛る", "モル") == [["盛", "も"], ["る", "る"]])
    check("食べる → [[食,た],[べ,べ],[る,る]]",
          ruby_util.align_ruby_pairs("食べる", "タベル")
          == [["食", "た"], ["べ", "べ"], ["る", "る"]])
    check("今日（熟字訓）→ 整词配对",
          ruby_util.align_ruby_pairs("今日", "キョウ") == [["今日", "きょう"]])
    check("引っ越し（歧义）→ 整词兜底",
          ruby_util.align_ruby_pairs("引っ越し", "ヒッコシ") == [["引っ越し", "ひっこし"]])
    check("无读音 → [[null,表層形]]", ruby_util.align_ruby_pairs("。", "") == [[None, "。"]])
    check("片假名 → 平假名かな",
          ruby_util.align_ruby_pairs("テスト", "テスト") == [[None, "てすと"]])


# ------------------------------------------------------- 3. 验收样例 1（米を盛る）
_EXPECTED_SAMPLE1_DATA = [
    {"idx": 0, "morph": "米", "lemma": "米", "morph_reading": "コメ",
     "pos": "名詞*普通名詞*一般", "accent": 2, "variants": [],
     "ruby_pairs": [["米", "こめ"]]},
    {"idx": 1, "morph": "を", "lemma": "を", "morph_reading": "オ",
     "pos": "助詞*格助詞", "accent": 0, "variants": [],
     "ruby_pairs": [[None, "を"]]},
    {"idx": 2, "morph": "盛る", "lemma": "盛る", "morph_reading": "モル",
     "pos": "動詞*一般", "accent": 0, "variants": [],
     "ruby_pairs": [["盛", "も"], ["る", "る"]]},
]
_EXPECTED_SAMPLE1_RULES = [
    ("R-LEX-DICT", [0, 0], "コメ＼"),
    ("R-PART-FLAT", [0, 1], "コメ＼オ"),
    ("R-LEX-DICT", [2, 2], "モル━"),
    ("R-MULTI-UNIT", [0, 2], "コメ＼オ・モル━"),
]
_EXPECTED_SAMPLE1_LOGICS = [
    "「米」词典收录，调型=2（尾高型，核在第2拍）→ 直接采用",
    "「を」为平板式付属語（无自身下がり目）→ 名詞部分调型保持，直接连读",
    "「盛る」词典收录，调型=0（平板型）→ 直接采用",
    "「米を」与「盛る」各为独立アクセント単位；每单位至多一个核",
]


def check_sample1(config: dict) -> tuple[dict, dict]:
    _section("验收样例 1：米を盛る（对照启动教程 4.1）")
    accent_json, rule_report = pipeline.run_pipeline("米を盛る", config=config)
    assert rule_report is not None
    check("audio_accent.json 逐字段与教程一致",
          accent_json["json_data"] == _EXPECTED_SAMPLE1_DATA,
          json.dumps(accent_json["json_data"], ensure_ascii=False))
    rules = rule_report["matched_rules"]
    check("规则报告共 4 条（顺序一致）", len(rules) == 4)
    check("规则关键字段（rule_id/target/result）一致",
          [(r["rule_id"], r["target"], r["result"]) for r in rules] == _EXPECTED_SAMPLE1_RULES,
          json.dumps([(r["rule_id"], r["target"], r["result"]) for r in rules], ensure_ascii=False))
    check("规则 logic 文案一致",
          [r["logic"] for r in rules] == _EXPECTED_SAMPLE1_LOGICS)
    check("每条规则含六字段",
          all(set(r.keys()) == {"rule_id", "name", "source_ref", "target", "logic", "result"}
              for r in rules))
    check("每条规则 source_ref 非空", all(r["source_ref"] for r in rules))
    return accent_json, rule_report


# ------------------------------------------------------- 4. 验收样例 2（住民税）
def check_sample2(config: dict, tagger) -> None:
    _section("验收样例 2：住民税（词典路径 + 复合词路径）")

    # 路径 A：组合词典整词收录（[] 解码）→ R-LEX-DICT 单条
    accent_json, rule_report = pipeline.run_pipeline("住民税", config=config)
    assert rule_report is not None
    rules = rule_report["matched_rules"]
    check("词典路径：仅 R-LEX-DICT 且 accent=3",
          [r["rule_id"] for r in rules] == ["R-LEX-DICT"]
          and accent_json["json_data"][0]["accent"] == 3)
    check("词典路径：result = ジューミ＼ンゼイ",
          rules[0]["result"] == "ジューミ＼ンゼイ", rules[0]["result"])

    # 路径 B：确定性分解 → 复合词规则 + 核合法性校验（教程 4.2 的两步链路）
    overrides = config.get("homograph_overrides", {})
    parts = resegment.decompose("住民税", tagger, overrides)
    check("分解：住民税 → 住民＋税",
          parts is not None and [p.morph for p in parts] == ["住民", "税"])
    if parts:
        ctx = MorphList([MorphState.from_morph(p) for p in parts])
        run_engine(ctx, load_registry(config))
        hits = [(r["rule_id"], r["target"], r["result"]) for r in ctx.report]
        expected = [
            ("R-COMPOUND-C3", [0, 1], "ジューミン＼ゼー"),
            ("R-NUCLEUS-SPECIAL", [0, 1], "ジューミ＼ンゼー"),
        ]
        check("复合路径：C3 → 核移位 两步报告（与教程 4.2 样例一致）", hits == expected,
              json.dumps(hits, ensure_ascii=False))
        check("复合路径：前部最终 accent=3（核前移后）", ctx[0].accent == 3)
        check("复合路径：整词渲染 ジューミ＼ンゼー",
              ctx.render_range(0, 1) == "ジューミ＼ンゼー", ctx.render_range(0, 1))


# ------------------------------------------------- 5. 契约不变量（単位/确定性）
def check_invariants(config: dict) -> None:
    _section("契约不变量：单位核数上限 / 确定性 / 复合词样例")
    sentence = "私は歌を歌うのが好きです。"
    a1, r1 = pipeline.run_pipeline(sentence, config=config)
    a2, r2 = pipeline.run_pipeline(sentence, config=config)
    check("确定性：同输入两次输出全等", a1 == a2 and r1 == r2)
    assert r1 is not None
    multi = [r for r in r1["matched_rules"] if r["rule_id"] == "R-MULTI-UNIT"]
    if multi:
        ok = all(part.count("＼") <= 1 for part in multi[0]["result"].split("・"))
        check("每アクセント単位至多一个核", ok, multi[0]["result"])
    else:
        check("每アクセント単位至多一个核（单单位跳过）", True)

    # 真实拆分复合词：入学手続き（MeCab 拆为 入学＋手続き，后部无结合型 → NHK 拍数规律）
    accent3, report3 = pipeline.run_pipeline("入学手続き", config=config)
    assert report3 is not None
    compound_hits = [r for r in report3["matched_rules"] if r["rule_id"].startswith("R-COMPOUND")]
    check("入学手続き：复合词规则命中", len(compound_hits) == 1,
          json.dumps([r["rule_id"] for r in report3["matched_rules"]], ensure_ascii=False))


# ----------------------------------------------------------- 6. 未收录兜底与語種
def check_fallback(config: dict) -> None:
    _section("未收录兜底：notes 标注 / 語種倾向（KANGO11・GAIRAI3）")
    accent_json, rule_report = pipeline.run_pipeline("気", config=config)
    assert rule_report is not None
    check("気：notes 标注「词典未收录」",
          "词典未收录" in accent_json["json_data"][0].get("notes", []))
    check("気：兜底规则命中",
          any(r["rule_id"].startswith("R-FALLBACK") for r in rule_report["matched_rules"]))

    def fake_unknown(surface: str, pron: str, mora: int, pos: str = "名詞-固有名詞-一般") -> MorphState:
        return MorphState(
            idx=0, morph=surface, lemma=surface, reading=pron, pron=pron,
            pos=pos, conj_type="", conj_form="", accent_raw="@", mora_count=mora,
            is_unknown=True, accent_source="unknown",
        )

    ctx = MorphList([fake_unknown("燵燵", "タツタツ", 2)])
    run_engine(ctx, load_registry(config))
    check("二字漢語(1+1) → 頭高型 accent=1",
          ctx[0].accent == 1 and ctx.report[0]["rule_id"] == "R-FALLBACK-GOSHU-KANGO11",
          f"accent={ctx[0].accent}")

    ctx = MorphList([fake_unknown("グモラ", "グモラ", 3)])
    run_engine(ctx, load_registry(config))
    check("外来語3拍（无特殊拍）→ 頭高型 accent=1",
          ctx[0].accent == 1 and ctx.report[0]["rule_id"] == "R-FALLBACK-GOSHU-GAIRAI3")
    check("外来語3拍：notes 标注", "词典未收录" in ctx[0].notes)

    ctx = MorphList([fake_unknown("バナン", "バナン", 3)])
    run_engine(ctx, load_registry(config))
    check("外来語3拍（末拍ン）→ 中高型 accent=2", ctx[0].accent == 2)

    # —— M4 补充語種倾向分支 ——
    ctx = MorphList([fake_unknown("燵灯", "タツヒ", 3)])
    run_engine(ctx, load_registry(config))
    check("二字漢語3拍（名词性）→ 頭高 accent=1",
          ctx[0].accent == 1 and ctx.report[0]["rule_id"] == "R-FALLBACK-GOSHU-KANGO21")

    ctx = MorphList([fake_unknown("燵灯", "タツヒ", 3, pos="名詞-普通名詞-サ変可能")])
    run_engine(ctx, load_registry(config))
    check("二字漢語3拍（サ変可能）→ 平板 accent=0", ctx[0].accent == 0)

    ctx = MorphList([fake_unknown("燵燵", "タツタツ", 4)])
    run_engine(ctx, load_registry(config))
    check("二字漢語4拍（2+2）→ 平板 accent=0",
          ctx[0].accent == 0 and ctx.report[0]["rule_id"] == "R-FALLBACK-GOSHU-KANGO22")

    ctx = MorphList([fake_unknown("メロディー", "メロディー", 4)])
    run_engine(ctx, load_registry(config))
    check("外来語4拍（末拍長音）→ 頭高 accent=1",
          ctx[0].accent == 1 and ctx.report[0]["rule_id"] == "R-FALLBACK-GOSHU-GAIRAI4")

    ctx = MorphList([fake_unknown("カタカナ", "カタカナ", 4)])
    run_engine(ctx, load_registry(config))
    check("外来語4拍（无特殊拍）→ 平板 accent=0", ctx[0].accent == 0)

    # [-4]（后ろから4番目の拍のあと）= 6 拍では位置 3（NHK Ⅲ全般 1.g 原文定义）
    ctx = MorphList([fake_unknown("イデオロギー", "イデオロギー", 6)])
    run_engine(ctx, load_registry(config))
    check("外来語6拍（末拍長音）→ 中高[-4] accent=3",
          ctx[0].accent == 3 and ctx.report[0]["rule_id"] == "R-FALLBACK-GOSHU-GAIRAI5",
          f"accent={ctx[0].accent}")

    # 落点撞上特殊拍（ー）时由核合法性规则前移（スマートカー: [-4]→3 落在「ー」→ 2）
    ctx = MorphList([fake_unknown("スマートカー", "スマートカー", 6)])
    run_engine(ctx, load_registry(config))
    check("外来語[-4]落点遇長音 → 核合法性前移 accent=2",
          ctx[0].accent == 2
          and any(r["rule_id"] == "R-NUCLEUS-SPECIAL" for r in ctx.report),
          f"accent={ctx[0].accent}")

    ctx = MorphList([fake_unknown("めぐる", "メグル", 3, pos="動詞-一般")])
    run_engine(ctx, load_registry(config))
    check("動詞3拍 → 中高[-2] accent=2",
          ctx[0].accent == 2 and ctx.report[0]["rule_id"] == "R-FALLBACK-GOSHU-VERB")

    ctx = MorphList([fake_unknown("うつくしい", "ウツクシイ", 5, pos="形容詞-一般")])
    run_engine(ctx, load_registry(config))
    check("形容詞5拍 → 中高[-2] accent=4",
          ctx[0].accent == 4 and ctx.report[0]["rule_id"] == "R-FALLBACK-GOSHU-ADJ")

    # 形容词名词化「〜さ」兜底（用户确认：多为0调）
    ctx = MorphList([fake_unknown("ほげさ", "ホゲサ", 3)])
    run_engine(ctx, load_registry(config))
    check("未收录〜さ名词化 → 平板0（R-FALLBACK-SASA）",
          ctx[0].accent == 0 and ctx.report[0]["rule_id"] == "R-FALLBACK-SASA")


# --------------------------------------------- 6.5 名词付属語全套（表12 F 系列）
def check_particles_m4(config: dict) -> None:
    _section("资料二 表12 F 系列 / NHK Ⅲ-1（名词付属語全套）")

    def last_result(text: str) -> str:
        _, report = pipeline.run_pipeline(text, config=config)
        assert report is not None
        hits = [r for r in report["matched_rules"] if r["rule_id"].startswith("R-PART")]
        return hits[-1]["result"] if hits else ""

    check("酒まで → サケマ＼デ（NHK 1.2a 原文例；F2@1 前部0型）",
          last_result("酒まで") == "サケマ＼デ", last_result("酒まで"))
    check("みそまで → ミ＼ソ・マ＼デ（NHK 1.2b 原文例；前部核+第2単位）",
          last_result("みそまで") == "ミ＼ソ・マ＼デ", last_result("みそまで"))
    check("米まで → コメ＼・マ＼デ（NHK 1.2c 第一形式）",
          last_result("米まで") == "コメ＼・マ＼デ", last_result("米まで"))
    check("米ぐらい → コメグ＼ライ（NHK 2.2 原文例；F4@1 決定型）",
          last_result("米ぐらい") == "コメグ＼ライ", last_result("米ぐらい"))
    check("みそぐらい → ミソグ＼ライ（NHK 2.2 原文例）",
          last_result("みそぐらい") == "ミソグ＼ライ", last_result("みそぐらい"))
    # らしい の発音は ラシー（3 拍）——NHK 表記 ラシ＼イ ≙ 発音 ラシ＼ー（同一发音）
    check("米らしい → コメラシ＼ー（NHK 2.2；F4@2 発音表记）",
          last_result("米らしい") == "コメラシ＼ー", last_result("米らしい"))

    accent, report = pipeline.run_pipeline("米の", config=config)
    assert report is not None
    no_odaka = [r for r in report["matched_rules"] if r["rule_id"] == "R-PART-NO-ODAKA"]
    check("米の → コメノ━（NHK 2.1 尾高+の 平板化例外）",
          bool(no_odaka) and no_odaka[0]["result"] == "コメノ━",
          json.dumps(no_odaka, ensure_ascii=False))

    # 中高型＋末拍特殊拍/二重母音副音 → 平板化（NHK 2.1 倾向首列形，W5）
    check("日本の → ニホンノ━（NHK 2.1 原文例）",
          last_result("日本の") == "ニホンノ━", last_result("日本の"))
    check("きのうの → キノーノ━（NHK 2.1 原文例）",
          last_result("きのうの") == "キノーノ━", last_result("きのうの"))
    check("おとといの → オトトイノ━（NHK 2.1 原文例）",
          last_result("おとといの") == "オトトイノ━", last_result("おとといの"))
    check("ミソの → ミ＼ソノ（頭高保持：付属語不干渉原则）",
          last_result("ミソの") == "ミ＼ソノ", last_result("ミソの"))

    # 「の」例外：数詞保留（イチ 尾高でも平板化しない条件检查——数值上应保留前部核）
    accent, report = pipeline.run_pipeline("一の", config=config)
    assert report is not None
    check("一の → 数詞例外（不触发 R-PART-NO-ODAKA）",
          not any(r["rule_id"] == "R-PART-NO-ODAKA" for r in report["matched_rules"]))


# ------------------------------------------- 6.6 动词接付属語（NHK Ⅲ-2 / 表12 F@動詞）
def check_verb_connection(config: dict, tagger) -> None:
    _section("NHK Ⅲ-2 动词接付属語（表12 動詞%F 规格 + た/て 家族 + サ変并入）")

    overrides = config.get("homograph_overrides", {})
    rules = load_registry(config)

    def full_render(text: str) -> str:
        r = stage1_analyzer.analyze(text, tagger, overrides)
        ctx = MorphList([MorphState.from_morph(m) for m in r.morphs])
        resegment.resegment_unknowns(ctx, tagger, overrides)
        run_engine(ctx, rules)
        return ctx.render_units()

    # —— た形・て形家族（NHK Ⅲ-2 1.1a/1.2a；用户确认 + 活用形一覧表）——
    check("食べた → タ＼ベタ（一段 核前移1拍）", full_render("食べた") == "タ＼ベタ", full_render("食べた"))
    check("食べて → タ＼ベテ（一段）", full_render("食べて") == "タ＼ベテ", full_render("食べて"))
    check("食べたら → タ＼ベタラ（NHK 1.2a 原文例）", full_render("食べたら") == "タ＼ベタラ", full_render("食べたら"))
    check("来た → キ＼タ（カ変）", full_render("来た") == "キ＼タ", full_render("来た"))
    check("太った → フト＼ッタ（五段保持；太る=2调）", full_render("太った") == "フト＼ッタ", full_render("太った"))
    check("飲んだ → ノ＼ンダ（五段保持）", full_render("飲んだ") == "ノ＼ンダ", full_render("飲んだ"))
    check("飲んだら → ノ＼ンダラ（NHK 1.2a 原文例）", full_render("飲んだら") == "ノ＼ンダラ", full_render("飲んだら"))
    check("咲いた → サイタ━（平板动词保持）", full_render("咲いた") == "サイタ━", full_render("咲いた"))

    # —— ます（F4 動詞%F4@1；NHK 4.1 付属語決定型）——
    check("歩きます → アルキマ＼ス", full_render("歩きます") == "アルキマ＼ス", full_render("歩きます"))
    check("読みます → ヨミマ＼ス", full_render("読みます") == "ヨミマ＼ス", full_render("読みます"))
    check("食べました → タベマ＼シタ（NHK 4.1 〜マ＼シタ）",
          full_render("食べました") == "タベマ＼シタ", full_render("食べました"))

    # —— が（F2@0：平板动词插入 / 起伏动词直接連続；NHK Ⅲ-2 1.1b）——
    check("働くが → ハタラク＼ガ（平板动词 下がり目挿入型＝N1+0，モル＼ガ 型）",
          full_render("働くが") == "ハタラク＼ガ", full_render("働くが"))
    check("飲むが → ノ＼ムガ（起伏动词 直接連続）", full_render("飲むが") == "ノ＼ムガ", full_render("飲むが"))

    # —— サ変（名詞＋し）単位并入 ——
    check("勉強します → ベンキョーシマ＼ス（单一単位）",
          full_render("勉強します") == "ベンキョーシマ＼ス", full_render("勉強します"))


# ------------------------------------------- 6.7 句级样例回归（test_sentences.txt）
def check_sample_sentences(config: dict) -> None:
    _section("句级测试样例回归（test_sentences.txt）")

    def full_render(text: str) -> str:
        _, report = pipeline.run_pipeline(text, config=config)
        assert report is not None
        multi = [r for r in report["matched_rules"] if r["rule_id"] == "R-MULTI-UNIT"]
        return multi[0]["result"] if multi else ""

    check("私は学生です。→ ワタシワ━・ガクセイデ＼ス（私=ワタシ；F2@1 です）",
          full_render("私は学生です。") == "ワタシワ━・ガクセイデ＼ス",
          full_render("私は学生です。"))
    check("東京駅まで歩きます。→ トーキョ＼ーエキ・マ＼デ・アルキマ＼ス",
          full_render("東京駅まで歩きます。") == "トーキョ＼ーエキ・マ＼デ・アルキマ＼ス",
          full_render("東京駅まで歩きます。"))
    check("桜の花が咲きました。→ サクラノ＼ハナガ・サキマ＼シタ",
          full_render("桜の花が咲きました。") == "サクラノ＼ハナガ・サキマ＼シタ",
          full_render("桜の花が咲きました。"))
    check("図書館で本を読みます。→ トショ＼カンデ・ホ＼ンオ・ヨミマ＼ス",
          full_render("図書館で本を読みます。") == "トショ＼カンデ・ホ＼ンオ・ヨミマ＼ス",
          full_render("図書館で本を読みます。"))
    check("空気がきれいです。→ ク＼ーキガ・キ＼レーデス（形状詞+です：范围外，现状固定）",
          full_render("空気がきれいです。") == "ク＼ーキガ・キ＼レーデス",
          full_render("空気がきれいです。"))
    check("コーヒーを飲みます。→ コーヒ＼ーオ・ノミマ＼ス（コーヒー=3调）",
          full_render("コーヒーを飲みます。") == "コーヒ＼ーオ・ノミマ＼ス",
          full_render("コーヒーを飲みます。"))
    check("日本語を勉強します。→ ニホンゴオ━・ベンキョーシマ＼ス（日本=ニホン；平板例外：語）",
          full_render("日本語を勉強します。") == "ニホンゴオ━・ベンキョーシマ＼ス",
          full_render("日本語を勉強します。"))
    check("学生が本を読む。→ ガクセイガ━・ホ＼ンオ・ヨ＼ム",
          full_render("学生が本を読む。") == "ガクセイガ━・ホ＼ンオ・ヨ＼ム",
          full_render("学生が本を読む。"))
    check("お米を食べました。→ オコメ＼オ・タベマ＼シタ",
          full_render("お米を食べました。") == "オコメ＼オ・タベマ＼シタ",
          full_render("お米を食べました。"))
    check("買い物に行きます。→ カイモノニ━・イキマ＼ス",
          full_render("買い物に行きます。") == "カイモノニ━・イキマ＼ス",
          full_render("買い物に行きます。"))
    check("昨日は雨が降りました。→ キノ＼ーワ・ア＼メガ・フリマ＼シタ",
          full_render("昨日は雨が降りました。") == "キノ＼ーワ・ア＼メガ・フリマ＼シタ",
          full_render("昨日は雨が降りました。"))
    check("住民税を払います。→ ジューミ＼ンゼイオ・ハライマ＼ス",
          full_render("住民税を払います。") == "ジューミ＼ンゼイオ・ハライマ＼ス",
          full_render("住民税を払います。"))


# ------------------------------------------- 6.6b 形容词接付属語（NHK Ⅲ-3）
def check_adjective_connection(config: dict, tagger) -> None:
    _section("NHK Ⅲ-3 形容词接付属語（表12 形容詞%F + ない/なる）")

    overrides = config.get("homograph_overrides", {})
    rules = load_registry(config)

    def full_render(text: str) -> str:
        r = stage1_analyzer.analyze(text, tagger, overrides)
        ctx = MorphList([MorphState.from_morph(m) for m in r.morphs])
        resegment.resegment_unknowns(ctx, tagger, overrides)
        run_engine(ctx, rules)
        return ctx.render_units()

    # です（F2@-1；NHK 1.1b アマ＼イデス 首列）
    check("甘いです → アマ＼イデス（NHK 1.1b 首列）",
          full_render("甘いです") == "アマ＼イデス", full_render("甘いです"))
    check("うまいです → ウマ＼イデス（起伏：そのまま連なる）",
          full_render("うまいです") == "ウマ＼イデス", full_render("うまいです"))
    check("高いです → タカ＼イデス", full_render("高いです") == "タカ＼イデス", full_render("高いです"))

    # が/から/と（F2@-1：1拍前移形，NHK 并记列）
    check("甘いが → アマ＼イガ", full_render("甘いが") == "アマ＼イガ", full_render("甘いが"))
    check("甘いから → アマ＼イカラ", full_render("甘いから") == "アマ＼イカラ", full_render("甘いから"))

    # 活用形（形容詞%F4@-2；NHK 一览表原文例）
    check("甘かった → アマ＼カッタ（NHK 原文例）",
          full_render("甘かった") == "アマ＼カッタ", full_render("甘かった"))
    check("冷たかった → ツメタ＼カッタ（NHK 原文例）",
          full_render("冷たかった") == "ツメタ＼カッタ", full_render("冷たかった"))
    check("おいしかった → オイシ＼カッタ（NHK 首列例）",
          full_render("おいしかった") == "オイシ＼カッタ", full_render("おいしかった"))
    check("楽しかった → タノシ＼カッタ", full_render("楽しかった") == "タノシ＼カッタ", full_render("楽しかった"))
    check("甘くて → アマ＼クテ（NHK 原文例）",
          full_render("甘くて") == "アマ＼クテ", full_render("甘くて"))

    # ない/なる（KIFUKU 兜底；NHK 1.2 アマクナ＼イ；起伏 2 単位）
    check("甘くない → アマクナ＼イ（NHK 1.2）",
          full_render("甘くない") == "アマクナ＼イ", full_render("甘くない"))
    check("高くない → タカ＼ク・ナ＼イ（起伏：2 単位）",
          full_render("高くない") == "タカ＼ク・ナ＼イ", full_render("高くない"))
    check("甘くなる → アマクナ＼ル", full_render("甘くなる") == "アマクナ＼ル", full_render("甘くなる"))


# ----------------------------------- 6.6c 活用形・アクセント修飾型（表9 / NHK Ⅲ-2）
def check_conjugation_mod(config: dict, tagger) -> None:
    _section("资料二 表9 アクセント修飾型＋命令形（R-CONJ-MOD）")

    overrides = config.get("homograph_overrides", {})
    rules = load_registry(config)

    def full_render(text: str) -> str:
        r = stage1_analyzer.analyze(text, tagger, overrides)
        ctx = MorphList([MorphState.from_morph(m) for m in r.morphs])
        resegment.resegment_unknowns(ctx, tagger, overrides)
        run_engine(ctx, rules)
        return ctx.render_units()

    # 意志推量形（词典 M1@1：N0 − M；NHK Ⅲ-2 一览表 タベヨ＼ー 等）
    check("食べよう → タベヨ＼ー（M1@1 = N0−1；NHK 一览表）",
          full_render("食べよう") == "タベヨ＼ー", full_render("食べよう"))
    check("飲もう → ノモ＼ー", full_render("飲もう") == "ノモ＼ー", full_render("飲もう"))
    check("帰ろう → カエロ＼ー", full_render("帰ろう") == "カエロ＼ー", full_render("帰ろう"))
    # たかっ/たけれ（词典 M2@2；NHK 4.1 〜タ＼カッタ/〜タ＼ケレバ）
    check("食べたかった → タベタ＼カッタ（NHK 4.1 〜タ＼カッタ）",
          full_render("食べたかった") == "タベタ＼カッタ", full_render("食べたかった"))
    check("食べたければ → タベタ＼ケレバ（NHK 4.1 〜タ＼ケレバ）",
          full_render("食べたければ") == "タベタ＼ケレバ", full_render("食べたければ"))
    # 命令形（NHK 一览表：タベ＼ロ、ノ＼メ、コ＼イ）
    check("食べろ → タベ＼ロ（NHK 一览表原文）", full_render("食べろ") == "タベ＼ロ", full_render("食べろ"))
    check("飲め → ノ＼メ", full_render("飲め") == "ノ＼メ", full_render("飲め"))
    check("起きろ → オキ＼ロ", full_render("起きろ") == "オキ＼ロ", full_render("起きろ"))
    check("来い → コ＼イ", full_render("来い") == "コ＼イ", full_render("来い"))
    # 冲突让位：たら 由 TA-TE 家族处理（词典 M2@1 与 NHK 表冲突 → 资料三优先）
    check("食べたら → タ＼ベタラ（CONJ-MOD 让位 TA-TE）",
          full_render("食べたら") == "タ＼ベタラ", full_render("食べたら"))


# --------------------------------- 6.6d 个人名＋肩書き（NHK Ⅰ複合名詞 2））
def check_name_title(config: dict, tagger) -> None:
    _section("NHK Ⅰ 2）个人名＋肩書き（R-COMPOUND-NAME-TITLE 等）")

    overrides = config.get("homograph_overrides", {})
    rules = load_registry(config)

    def full_render(text: str) -> str:
        r = stage1_analyzer.analyze(text, tagger, overrides)
        ctx = MorphList([MorphState.from_morph(m) for m in r.morphs])
        resegment.resegment_unknowns(ctx, tagger, overrides)
        run_engine(ctx, rules)
        return ctx.render_units()

    # 普通语素＋肩書き → 复合（1単位・後部一型；NHK 原文例的模式）
    check("釣り名人 → ツリメ＼イジン（C2 後部一型；NHK ツリメ＼ージン 模式）",
          full_render("釣り名人") == "ツリメ＼イジン", full_render("釣り名人"))
    check("文学博士 → ブンガクハ＼カセ（NHK ブンガクハ＼クシ 模式）",
          full_render("文学博士") == "ブンガクハ＼カセ", full_render("文学博士"))
    # 词典整词（族名）：与 NHK 原文逐字一致
    check("徳川氏 → トクガワ＼シ（NHK 原文例；词典整词）",
          full_render("徳川氏") == "トクガワ＼シ", full_render("徳川氏"))

    # 个人名（固有名詞-人名）＋肩書き → 不复合（2単位；合成数据验证规则本体）
    from dataclasses import replace as _replace
    parsed = stage1_analyzer.analyze("高橋博士", tagger, overrides).morphs
    front = _replace(parsed[0], pos="名詞-固有名詞-人名-姓")
    ctx = MorphList([MorphState.from_morph(front), MorphState.from_morph(parsed[1])])
    run_engine(ctx, rules)
    check("〔合成〕高橋(人名-姓)＋博士 → タカ＼ハシ・ハ＼カセ（NHK タカ＼ハシ・ハ＼クシ 模式）",
          ctx.render_units() == "タカ＼ハシ・ハ＼カセ"
          and any(x["rule_id"] == "R-COMPOUND-NAME-TITLE" for x in ctx.report),
          ctx.render_units())


# ------------------------------------------- 6.65 数詞＋助数詞2単位語（NHK Ⅱ）
def check_numeral_two_unit(config: dict, tagger) -> None:
    _section("NHK Ⅱ 数詞＋助数詞・2単位語（15/14/19＋2拍以下助数詞）")

    overrides = config.get("homograph_overrides", {})
    rules = load_registry(config)

    def full_render(text: str) -> str:
        r = stage1_analyzer.analyze(text, tagger, overrides)
        ctx = MorphList([MorphState.from_morph(m) for m in r.morphs])
        resegment.resegment_unknowns(ctx, tagger, overrides)
        run_engine(ctx, rules)
        return ctx.render_units()

    check("十五本 → ジュ＼ー・ゴポン━（NHK Ⅱ 2単位语模式）",
          full_render("十五本") == "ジュ＼ー・ゴポン━", full_render("十五本"))
    check("十五日 → ジュ＼ー・ゴニチ━", full_render("十五日") == "ジュ＼ー・ゴニチ━", full_render("十五日"))
    check("十四日 → ジュ＼ー・ヨンニチ━（14 同型）",
          full_render("十四日") == "ジュ＼ー・ヨンニチ━", full_render("十四日"))
    check("十九人 → ジュ＼ー・キューニン━（19 同型）",
          full_render("十九人") == "ジュ＼ー・キューニン━", full_render("十九人"))
    check("十五本を読みます。→ ジュ＼ー・ゴポンオ━・ヨミマ＼ス（句级集成）",
          full_render("十五本を読みます。") == "ジュ＼ー・ゴポンオ━・ヨミマ＼ス",
          full_render("十五本を読みます。"))

    # 非 15/14/19 的数词链不得命中该规则（走复合词路径）
    r = stage1_analyzer.analyze("十二本", tagger, overrides)
    ctx = MorphList([MorphState.from_morph(m) for m in r.morphs])
    run_engine(ctx, rules)
    check("十二本：不触发 R-NUM-TWO-UNIT（走复合词 C 规则路径）",
          not any(x["rule_id"] == "R-NUM-TWO-UNIT" for x in ctx.report),
          json.dumps([x["rule_id"] for x in ctx.report], ensure_ascii=False))


# ------------------------------------- 6.75 同形語修正表（日本=ニホン 等）
def check_homograph_overrides(config: dict, tagger) -> None:
    _section("同形語修正表（日本→ニホン 全词族；用户指定「所有日本=にほん」）")

    overrides = config.get("homograph_overrides", {})

    def first_morph(text: str) -> tuple[str, str, str]:
        r = stage1_analyzer.analyze(text, tagger, overrides)
        m = r.morphs[0]
        return m.morph, m.pron, m.accent_raw

    check("日本 → ニホン（调型2）", first_morph("日本") == ("日本", "ニホン", "2"),
          str(first_morph("日本")))
    check("日本語を 的拆分成分 日本 → ニホン", first_morph("日本語を") == ("日本", "ニホン", "2"),
          str(first_morph("日本語を")))
    check("日本人 → ニホンジン（调型4＝ニホンジ＼ン；NHK Ⅲ-1 原文佐证）",
          first_morph("日本人") == ("日本人", "ニホンジン", "4"), str(first_morph("日本人")))


# ------------------------------------- 6.8 复合词平板例外表优先级（P2）
def check_compound_flat_exceptions(config: dict, tagger) -> None:
    _section("复合词平板例外表优先级（NHK Ⅰ複合名詞① vs 词典 C 值 + 配置开关）")

    overrides = config.get("homograph_overrides", {})
    parsed = stage1_analyzer.analyze("日本語を", tagger, overrides)
    pair = [m for m in parsed.morphs if m.morph in ("日本", "語")]
    check("前置数据：日本＋語（語 的词典 aCon 值 C3，NHK 例外表列其为平板）",
          len(pair) == 2 and pair[1].a_con_type.strip().upper() == "C3",
          json.dumps([m.a_con_type for m in pair], ensure_ascii=False))

    ctx = MorphList([MorphState.from_morph(m) for m in pair])
    run_engine(ctx, load_registry(config))
    check("默认（NHK 平板例外优先）：R-COMPOUND-C4 → ニホンゴ━",
          bool(ctx.report) and ctx.report[0]["rule_id"] == "R-COMPOUND-C4"
          and ctx.render_units() == "ニホンゴ━",
          json.dumps([r["rule_id"] for r in ctx.report], ensure_ascii=False)
          + " / " + ctx.render_units())

    ctx_off = MorphList([MorphState.from_morph(m) for m in pair])
    off_config = {**config, "compound": {"nhk_flat_exceptions_priority": False}}
    run_engine(ctx_off, load_registry(off_config))
    check("关闭开关（词典严密优先）：R-COMPOUND-C3 → ニホ＼ンゴ（核移位后）",
          bool(ctx_off.report) and ctx_off.report[0]["rule_id"] == "R-COMPOUND-C3"
          and ctx_off.render_units() == "ニホ＼ンゴ",
          json.dumps([r["rule_id"] for r in ctx_off.report], ensure_ascii=False)
          + " / " + ctx_off.render_units())


# ------------------------------------- 6.9 参照对照长例句（用户提供预期输出）
_EXPECTED_SENT1 = (
    "ア＼モイ・ア＼モイワ・チュ＼ーゴク・ナント＼ーブノ・ウツクシ＼ー・ミナト＼マチデス・"
    "コ＼ンカイワ・ア＼モイノ・ゼッタイニ━・ハズセナイ━・オススメカンコ＼ーチ・"
    "ジュ＼ッセンオ・ゴショーカイシマ＼ス・アモイリョ＼コーノ・ケーカクオ━・タテ＼ル・"
    "サ＼イワ・ゼ＼ヒ・サンコーニ━・シテ━・クダサ＼イ"
)
_EXPECTED_SENT2 = (
    "コ＼ンカイノ・タイカイニ━・カ＼ンシテワ・アマリ＼ノ・アツ＼サデ・ヨセンタ＼イカイガ・"
    "ヒト＼ツ・チューシニ━・ナ＼ッタリトカ・イロイロ━・ヨテ＼ーガイノ・コト＼ガ・ア＼ッテ・"
    "ケンチサンモ━・イッテイタ＼ケド・ソーユー━・ナ＼カデ・ヨ＼クゾ・ケッショータ＼イカイ・"
    "マ＼デ・タドリツ＼ケタナッテ・ユー＼ノガ・ショージ＼キナ・カンソーデ＼スヨネ・マ＼ー・"
    "コトシワ━・イロイロト━・タイヘンデ＼シタ・ワライ━"
)


def check_reference_sentences(config: dict) -> None:
    _section("参照对照长例句（用户提供预期输出；test_sentences.txt 13-14 行）")

    def nhk_line(text: str) -> str:
        out = pipeline.show_accent(pipeline.analyze_text(text))
        return [ln for ln in out.splitlines() if ln.startswith("【NHK】")][0][len("【NHK】"):]

    t1 = ("廈門（アモイ）は、中国南東部の美しい港町です。今回は、廈門の絶対に外せない"
          "おすすめ観光地10選をご紹介します。廈門旅行の計画を立てる際は、ぜひ参考にしてください。")
    t2 = ("今回の大会に関しては、あまりの暑さで予選大会がひとつ中止になったりとか、"
          "いろいろ予定外のことがあって。ケンチさんも言っていたけど、そういう中でよくぞ"
          "決勝大会までたどり着けたなっていうのが、正直な感想ですよね。まあ今年は、"
          "いろいろと大変でした（笑）。")

    got1 = nhk_line(t1)
    exp1_units = _EXPECTED_SENT1.split("・")
    got1_units = got1.split("・")
    diff1 = [k for k in range(max(len(exp1_units), len(got1_units)))
             if (exp1_units[k] if k < len(exp1_units) else None)
             != (got1_units[k] if k < len(got1_units) else None)]
    # 数词读法子系统（R-NUM-READING）落地后，10選→ジュ＼ッセンオ 与参照一致
    check("句1：21/21 単位逐字一致（含 10選→ジュ＼ッセンオ 数词读法）",
          len(diff1) == 0,
          f"diff={diff1}")

    got2 = nhk_line(t2)
    check("句2：29/29 単位逐字一致（含た/て家族、そういう合并、です/でし、形状詞+でし、"
          "数詞不合并、ユー＼ノガ、ワライ━ 等 13 项逻辑修正）",
          got2 == _EXPECTED_SENT2, got2)

    t3 = ("あの、揺れる世界に落ちている私は許されないでしょうかって"
          "思い込んだら、どうぞ救ってください")
    exp3 = ("アノ━・ユレル━・セ＼カイニ・オ＼チテイル・ワタシワ━・"
            "ユルサレ＼ナイデショ＼ーカッテ・オモイコンダ＼ラ・ド＼ーゾ・"
            "スクッテ━・クダサ＼イ")
    got3 = nhk_line(t3)
    check("句3：10/10 逐字一致（私=ワタシ、あの=平板、M4前部清零、複合動詞首位规则）",
          got3 == exp3, got3)


# ------------------------------- 6.9 数词读法（NHK Ⅱ：数字链＋促音规则）
def check_numeral(config: dict) -> None:
    _section("数词读法（numeral_util ＋ R-NUM-READING）")

    import numeral_util

    for value, kana, accent in [
        (10, "ジュー", 1), (11, "ジューイチ", 1), (15, "ジューゴ", 1),
        (21, "ニジューイチ", 0), (100, "ヒャク", 0), (300, "サンビャク", 0),
        (600, "ロッピャク", 0), (800, "ハッピャク", 0), (3000, "サンゼン", 0),
        (8000, "ハッセン", 0), (10000, "イチマン", 0),
    ]:
        check(f"读法合成 {value} → {kana}（アクセント {accent}）",
              numeral_util.compose_number_kana(value) == (kana, accent),
              str(numeral_util.compose_number_kana(value)))

    for kana, surf, read, expected in [
        ("ジュー", "選", "セン", "ジュッ"), ("ジューイチ", "階", "カイ", "ジューイッ"),
        ("ロク", "階", "カイ", "ロッ"), ("ハチ", "階", "カイ", "ハッ"),
        ("ジュー", "月", "ガツ", "ジュー"), ("ジュー", "時", "ジ", "ジュー"),
    ]:
        check(f"促音规则 {kana}＋{surf} → {expected}",
              numeral_util.apply_sokuon(kana, surf, read) == expected,
              numeral_util.apply_sokuon(kana, surf, read))

    out = pipeline.show_accent(pipeline.analyze_text("10選をご紹介します。"))
    got = [ln for ln in out.splitlines() if ln.startswith("【NHK】")][0][len("【NHK】"):]
    check("句级 10選をご紹介します。→ ジュ＼ッセンオ・ゴショーカイシマ＼ス",
          got == "ジュ＼ッセンオ・ゴショーカイシマ＼ス", got)


# ------------------------------- 6.95 拓展例句回归（〜ています/でしょう/ください 防护）
def check_extended_sentences(config: dict) -> None:
    _section("拓展例句回归（修正项防护：动词链清零/多核渲染/终助词/でしょう）")

    cases = [
        ("飲んでいます。", "ノ＼ンデイマ＼ス"),          # 用户数据：动词核保留+ます核（双下降）
        ("東京都に住んでいます。", "トーキョ＼ートニ・ス＼ンデイマ＼ス"),
        ("コーヒーを飲みながら本を読んでいます。",
         "コーヒ＼ーオ・ノミナ＼ガラ・ホ＼ンオ・ヨ＼ンデイマ＼ス"),
        ("明日はきっと晴れるでしょう。", "アス＼ワ・キット━・ハレ＼ルデショ＼ー"),  # 修正表+多核渲染
        ("電気を消してください。", "デ＼ンキオ・ケシテ━・クダサ＼イ"),            # 命令形补助动词独立
        ("来ました。", "キマ＼シタ"),                                            # 非自立零化边界（来-保留）
        ("大きくなったり。", "オーキ＼ク・ナ＼ッタリ"),                          # 起伏形容词+なる 2単位（NHK Ⅲ-3）
    ]
    for text, expected in cases:
        out = pipeline.show_accent(pipeline.analyze_text(text))
        got = [ln for ln in out.splitlines() if ln.startswith("【NHK】")][0][len("【NHK】"):]
        check(f"{text} → {expected}", got == expected, got)


# ------------------------------------------------------------- 7. 注册表与配置
def check_registry(config: dict) -> None:
    _section("注册表（教程 4.3）：优先级 / rule_overrides / custom_rules_dir")
    reg = load_registry(config)
    ids = [r.rule_id for r in reg]
    check("核合法性规则在首位（最高优先级）", ids[0] == "R-NUCLEUS-SPECIAL", str(ids))
    priorities = [r.priority for r in reg]
    check("排序单调不增（数值大者先）",
          all(a >= b for a, b in zip(priorities, priorities[1:])), str(priorities))
    check("每条规则携带 source_ref", all(r.source_ref for r in reg))

    disabled = load_registry({**config, "rule_overrides": {"R-FALLBACK-HEIBAN": {"enabled": False}}})
    check("rule_overrides 禁用生效",
          "R-FALLBACK-HEIBAN" not in [r.rule_id for r in disabled])

    boosted = load_registry({**config, "rule_overrides": {"R-FALLBACK-HEIBAN": {"priority": 999}}})
    check("rule_overrides 优先级覆盖生效",
          [r.rule_id for r in boosted][:2] == ["R-NUCLEUS-SPECIAL", "R-FALLBACK-HEIBAN"])

    # custom_rules_dir 动态加载（临时目录，不污染仓库）
    with tempfile.TemporaryDirectory() as td:
        custom = Path(td) / "my_rule.py"
        custom.write_text(
            "from stage2_rules.base import Rule\n"
            "class MyCustomRule(Rule):\n"
            "    rule_id = 'R-CUSTOM-MYRULE'\n"
            "    name = '自定义规则示例'\n"
            "    source_ref = '自定义（依据：NHK Ⅲ-1 2.1）'\n"
            "    priority = 70\n"
            "    def match(self, morphs, i):\n"
            "        return False\n"
            "    def apply(self, morphs, i):\n"
            "        return None\n",
            encoding="utf-8",
        )
        custom_reg = load_registry({**config, "custom_rules_dir": td})
        check("custom_rules_dir：自定义规则自动加载",
              "R-CUSTOM-MYRULE" in [r.rule_id for r in custom_reg])


# --------------------------------------------------------------- 8. 产物写盘
def check_artifacts(config: dict) -> None:
    _section("产物写盘与 JSON 合法性")
    with tempfile.TemporaryDirectory() as td:
        accent_json, rule_report = pipeline.run_pipeline("米を盛る", config=config, save_dir=td)
        accent_path = Path(td) / "audio_accent.json"
        report_path = Path(td) / "rule_report.json"
        check("双产物已写出", accent_path.is_file() and report_path.is_file())
        loaded_accent = json.loads(accent_path.read_text(encoding="utf-8"))
        loaded_report = json.loads(report_path.read_text(encoding="utf-8"))
        check("产物 JSON 可解析且内容一致",
              loaded_accent == accent_json and loaded_report == rule_report)


def main() -> int:
    print("Utaer functions/unidic 双阶段声调管线 — 模块自检")
    try:
        tagger = stage1_analyzer.build_tagger()
    except stage1_analyzer.Stage1Error as exc:
        print(f"[ENV] 阶段一环境不可用：{exc}")
        return 2

    config = env_util.load_rules_config()

    check_service_api(config)
    check_show_accent(config)
    check_mora_util()
    check_ruby_util()
    check_sample1(config)
    check_sample2(config, tagger)
    check_invariants(config)
    check_fallback(config)
    check_particles_m4(config)
    check_verb_connection(config, tagger)
    check_adjective_connection(config, tagger)
    check_conjugation_mod(config, tagger)
    check_numeral_two_unit(config, tagger)
    check_name_title(config, tagger)
    check_homograph_overrides(config, tagger)
    check_compound_flat_exceptions(config, tagger)
    check_sample_sentences(config)
    check_numeral(config)
    check_extended_sentences(config)
    check_reference_sentences(config)
    check_registry(config)
    check_artifacts(config)

    print()
    if _FAILURES:
        print(f"自检结束：{len(_FAILURES)} 项失败 → {', '.join(_FAILURES)}")
        return 1
    print("自检结束：全部通过 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
