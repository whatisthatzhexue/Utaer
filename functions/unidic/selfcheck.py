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

    # 「の」例外：数詞保留（イチ 尾高でも平板化しない条件检查——数值上应保留前部核）
    accent, report = pipeline.run_pipeline("一の", config=config)
    assert report is not None
    check("一の → 数詞例外（不触发 R-PART-NO-ODAKA）",
          not any(r["rule_id"] == "R-PART-NO-ODAKA" for r in report["matched_rules"]))


# ------------------------------------------- 6.6 句级样例回归（test_sentences.txt）
def check_sample_sentences(config: dict) -> None:
    _section("句级测试样例回归（test_sentences.txt）")

    def full_render(text: str) -> str:
        _, report = pipeline.run_pipeline(text, config=config)
        assert report is not None
        multi = [r for r in report["matched_rules"] if r["rule_id"] == "R-MULTI-UNIT"]
        return multi[0]["result"] if multi else ""

    # 已验证完全正确的句子（逐字固定为回归基线）
    check("学生が本を読む。→ ガクセイガ━・ホ＼ンオ・ヨ＼ム",
          full_render("学生が本を読む。") == "ガクセイガ━・ホ＼ンオ・ヨ＼ム",
          full_render("学生が本を読む。"))
    check("私は学生です。→ ワタクシワ━・ガクセイデ＼ス（F2@1 です）",
          full_render("私は学生です。") == "ワタクシワ━・ガクセイデ＼ス",
          full_render("私は学生です。"))

    # 名词部已验证正确；动词尾部（ます/た 接続＝NHK Ⅲ-2 范围）为已知待改进项，
    # 这里仅固定前半部分防止回归（尾部的当前行为见 docs/验证报告）。
    check("図書館で本を読みます。→ 名词部 トショ＼カンデ・ホ＼ンオ",
          full_render("図書館で本を読みます。").startswith("トショ＼カンデ・ホ＼ンオ"),
          full_render("図書館で本を読みます。"))
    check("住民税を払います。→ 名词部 ジューミ＼ンゼイオ",
          full_render("住民税を払います。").startswith("ジューミ＼ンゼイオ"),
          full_render("住民税を払います。"))
    check("東京駅まで歩きます。→ トーキョ＼ーエキ・マ＼デ（まで F2@1 第2単位）",
          full_render("東京駅まで歩きます。").startswith("トーキョ＼ーエキ・マ＼デ"),
          full_render("東京駅まで歩きます。"))
    check("昨日は雨が降りました。→ 名词部 キノ＼ーワ・ア＼メガ",
          full_render("昨日は雨が降りました。").startswith("キノ＼ーワ・ア＼メガ"),
          full_render("昨日は雨が降りました。"))
    check("買い物に行きます。→ カイモノニ━（に F1）",
          full_render("買い物に行きます。").startswith("カイモノニ━"),
          full_render("買い物に行きます。"))


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

    check_mora_util()
    check_ruby_util()
    check_sample1(config)
    check_sample2(config, tagger)
    check_invariants(config)
    check_fallback(config)
    check_particles_m4(config)
    check_sample_sentences(config)
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
