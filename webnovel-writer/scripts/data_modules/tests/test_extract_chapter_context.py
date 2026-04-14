#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path


def test_extract_state_summary_accepts_dominant_key(tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extract_chapter_context import extract_state_summary

    state = {
        "progress": {"current_chapter": 12, "total_words": 12345},
        "protagonist_state": {
            "power": {"realm": "筑基", "layer": 2},
            "location": "宗门",
            "golden_finger": {"name": "系统", "level": 1},
        },
        "strand_tracker": {
            "history": [
                {"chapter": 10, "dominant": "quest"},
                {"chapter": 11, "dominant": "fire"},
            ]
        },
    }

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)
    (webnovel_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    text = extract_state_summary(tmp_path)
    assert "Ch10:quest" in text
    assert "Ch11:fire" in text


def test_extract_chapter_outline_supports_hyphen_filename(tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extract_chapter_context import extract_chapter_outline

    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第1卷-详细大纲.md").write_text("### 第1章：测试标题\n测试大纲", encoding="utf-8")

    outline = extract_chapter_outline(tmp_path, 1)
    assert "### 第1章：测试标题" in outline
    assert "测试大纲" in outline


def test_extract_chapter_outline_prefers_state_volume_mapping(tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extract_chapter_context import extract_chapter_outline

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "progress": {
            "volumes_planned": [
                {"volume": 1, "chapters_range": "1-10"},
                {"volume": 2, "chapters_range": "11-20"},
            ]
        }
    }
    (webnovel_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第2卷-详细大纲.md").write_text("### 第12章：V2标题\nV2大纲", encoding="utf-8")

    outline = extract_chapter_outline(tmp_path, 12)
    assert "### 第12章：V2标题" in outline
    assert "V2大纲" in outline


def test_extract_chapter_outline_falls_back_when_state_has_no_match(tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extract_chapter_context import extract_chapter_outline

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)
    state = {"progress": {"volumes_planned": [{"volume": 1, "chapters_range": "1-10"}]}}
    (webnovel_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第2卷-详细大纲.md").write_text("### 第60章：V2标题\nV2大纲", encoding="utf-8")

    outline = extract_chapter_outline(tmp_path, 60)
    assert "### 第60章：V2标题" in outline
    assert "V2大纲" in outline


def test_build_chapter_context_payload_includes_contract_sections(tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extract_chapter_context import build_chapter_context_payload
    from data_modules.config import DataModulesConfig
    from data_modules.index_manager import IndexManager, ChapterReadingPowerMeta, ReviewMetrics

    cfg = DataModulesConfig.from_project_root(tmp_path)
    cfg.ensure_dirs()

    state = {
        "project": {"genre": "xuanhuan"},
        "progress": {"current_chapter": 3, "total_words": 9000},
        "protagonist_state": {
            "power": {"realm": "筑基", "layer": 2},
            "location": "宗门",
            "golden_finger": {"name": "系统", "level": 1},
        },
        "strand_tracker": {"history": [{"chapter": 2, "dominant": "quest"}]},
        "chapter_meta": {},
        "disambiguation_warnings": [],
        "disambiguation_pending": [],
    }
    (cfg.webnovel_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    summaries_dir = cfg.webnovel_dir / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    (summaries_dir / "ch0002.md").write_text("## 剧情摘要\n上一章总结", encoding="utf-8")

    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第1卷 详细大纲.md").write_text("### 第3章：测试标题\n测试大纲", encoding="utf-8")

    refs_dir = tmp_path / ".claude" / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (refs_dir / "genre-profiles.md").write_text("## xuanhuan\n- 升级线清晰", encoding="utf-8")
    (refs_dir / "reading-power-taxonomy.md").write_text("## xuanhuan\n- 悬念钩优先", encoding="utf-8")

    idx = IndexManager(cfg)
    idx.save_chapter_reading_power(
        ChapterReadingPowerMeta(chapter=2, hook_type="悬念钩", hook_strength="strong", coolpoint_patterns=["身份掉马"])
    )
    idx.save_review_metrics(
        ReviewMetrics(start_chapter=1, end_chapter=2, overall_score=71, dimension_scores={"plot": 71})
    )

    payload = build_chapter_context_payload(tmp_path, 3)
    assert payload["context_contract_version"] == "v2"
    assert payload.get("context_weight_stage") in {"early", "mid", "late"}
    assert "writing_guidance" in payload
    assert isinstance(payload["writing_guidance"].get("guidance_items"), list)
    assert isinstance(payload["writing_guidance"].get("checklist"), list)
    assert isinstance(payload["writing_guidance"].get("checklist_score"), dict)
    assert payload["genre_profile"].get("genre") == "xuanhuan"
    assert "rag_assist" in payload
    assert isinstance(payload["rag_assist"], dict)
    assert payload["rag_assist"].get("invoked") is False


def test_render_text_contains_writing_guidance_section(tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extract_chapter_context import _render_text

    payload = {
        "chapter": 10,
        "outline": "测试大纲",
        "previous_summaries": ["### 第9章摘要\n上一章"],
        "state_summary": "状态",
        "context_contract_version": "v2",
        "context_weight_stage": "early",
        "reader_signal": {"review_trend": {"overall_avg": 72}, "low_score_ranges": [{"start_chapter": 8, "end_chapter": 9}]},
        "genre_profile": {
            "genre": "xuanhuan",
            "genres": ["xuanhuan", "realistic"],
            "composite_hints": ["以玄幻主线推进，同时保留现实议题表达"],
            "reference_hints": ["升级线清晰"],
        },
        "writing_guidance": {
            "guidance_items": ["先修低分", "钩子差异化"],
            "checklist": [
                {
                    "id": "fix_low_score_range",
                    "label": "修复低分区间问题",
                    "weight": 1.4,
                    "required": True,
                    "source": "reader_signal.low_score_ranges",
                    "verify_hint": "至少完成1处冲突升级",
                }
            ],
            "checklist_score": {
                "score": 81.5,
                "completion_rate": 0.66,
                "required_completion_rate": 0.75,
            },
            "methodology": {
                "enabled": True,
                "framework": "digital-serial-v1",
                "pilot": "xianxia",
                "genre_profile_key": "xianxia",
                "chapter_stage": "confront",
                "observability": {
                    "next_reason_clarity": 78.0,
                    "anchor_effectiveness": 74.0,
                    "rhythm_naturalness": 72.0,
                },
                "signals": {"risk_flags": ["pattern_overuse_watch"]},
            },
        },
    }

    text = _render_text(payload)
    assert "## 写作执行建议" in text
    assert "先修低分" in text
    assert "## Contract (v2)" in text
    assert "- 上下文阶段权重: early" in text
    assert "### 执行检查清单（可评分）" in text
    assert "- 总权重: 1.40" in text
    assert "[必做][w=1.4] 修复低分区间问题" in text
    assert "### 执行评分" in text
    assert "- 评分: 81.5" in text
    assert "- 复合题材: xuanhuan + realistic" in text
    assert "## 长篇方法论策略" in text
    assert "- 适用题材: xianxia" in text
    assert "next_reason=78.0" in text


def test_render_text_contains_rag_assist_section_when_hits_exist(tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extract_chapter_context import _render_text

    payload = {
        "chapter": 12,
        "outline": "测试大纲",
        "previous_summaries": [],
        "state_summary": "状态",
        "context_contract_version": "v2",
        "reader_signal": {},
        "genre_profile": {},
        "writing_guidance": {},
        "rag_assist": {
            "invoked": True,
            "mode": "auto",
            "intent": "relationship",
            "query": "第12章 人物关系与动机：萧炎与药老发生冲突",
            "hits": [
                {
                    "chapter": 9,
                    "scene_index": 2,
                    "source": "graph_hybrid",
                    "score": 0.91,
                    "content": "萧炎与药老在修炼方向上发生分歧。",
                }
            ],
        },
    }

    text = _render_text(payload)
    assert "## RAG 检索线索" in text
    assert "- 模式: auto" in text
    assert "[graph_hybrid]" in text
    assert "萧炎与药老" in text


def test_rag_trigger_config_dynamic_by_genre():
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extract_chapter_context import _get_rag_trigger_config, _build_rag_query

    # 默认配置应包含通用关键词
    default_cfg = _get_rag_trigger_config("")
    assert "关系" in default_cfg["keywords"]

    # 修仙题材应包含"境界"、"功法"等关键词
    xianxia_cfg = _get_rag_trigger_config("修仙")
    assert "境界" in xianxia_cfg["keywords"]
    assert "功法" in xianxia_cfg["keywords"]

    # 电竞题材应包含"比赛"、"BP"等关键词
    esports_cfg = _get_rag_trigger_config("电竞")
    assert "比赛" in esports_cfg["keywords"]
    assert "BP" in esports_cfg["keywords"]

    # 动态 topic 映射：修仙大纲含"功法"
    query = _build_rag_query("主角获得神秘功法残卷", 5, 5, 40, genre="修仙")
    assert "修炼体系与资源" in query

    # 电竞大纲含"团战"
    query = _build_rag_query("关键团战翻盘", 10, 5, 40, genre="电竞")
    assert "比赛与战术" in query

    # 军旅题材应包含"晋升"、"战备"等关键词
    military_cfg = _get_rag_trigger_config("军旅")
    assert "晋升" in military_cfg["keywords"]
    assert "战备" in military_cfg["keywords"]

    # 商战题材应包含"并购"、"资金链"等关键词
    business_cfg = _get_rag_trigger_config("商战")
    assert "并购" in business_cfg["keywords"]
    assert "资金链" in business_cfg["keywords"]

    # 动态 topic 映射：军旅大纲含"轮战"
    query = _build_rag_query("全营动员准备两山轮战", 12, 5, 40, genre="军旅")
    assert "军旅晋升与战备" in query

    # 动态 topic 映射：商战大纲含"改制"
    query = _build_rag_query("国企改制方案通过", 15, 5, 40, genre="商战")
    assert "商业变革与资本运作" in query

    # 无触发词时返回空
    query = _build_rag_query("日常吃饭睡觉", 1, 5, 40, genre="修仙")
    assert query == ""
