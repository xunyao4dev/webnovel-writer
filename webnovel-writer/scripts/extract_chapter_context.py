#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_chapter_context.py - extract chapter writing context

Features:
- chapter outline snippet
- previous chapter summaries (prefers .webnovel/summaries)
- compact state summary
- ContextManager contract sections (reader_signal / genre_profile / writing_guidance)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from chapter_outline_loader import load_chapter_outline

from runtime_compat import enable_windows_utf8_stdio

try:
    from chapter_paths import find_chapter_file
except ImportError:  # pragma: no cover
    from scripts.chapter_paths import find_chapter_file


def _ensure_scripts_path():
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _get_profile_key(genre: str) -> str:
    try:
        from data_modules.genre_aliases import to_profile_key
        return to_profile_key(genre)
    except Exception:
        return genre.strip().lower()


# 题材化 RAG trigger 关键词配置
_RAG_TRIGGER_PROFILES: Dict[str, Dict[str, Any]] = {
    "default": {
        "keywords": (
            "关系", "恩怨", "冲突", "敌对", "同盟", "师徒", "身份",
            "线索", "伏笔", "回收", "地点", "势力", "真相", "来历",
        ),
        "topics": [
            (("关系", "师徒", "敌对", "同盟"), "人物关系与动机"),
            (("地点", "势力"), "地点势力与场景约束"),
            (("伏笔", "线索", "回收"), "伏笔与线索"),
        ],
        "fallback_topic": "剧情关键线索",
    },
    "shuangwen": {
        "keywords": (
            "系统", "任务", "奖励", "打脸", "装逼", "升级", "境界",
            "功法", "丹药", "灵石", "势力", "敌对", "身份", "金手指",
            "伏笔", "线索", "回收", "真相",
        ),
        "topics": [
            (("系统", "任务", "奖励", "金手指"), "系统与金手指"),
            (("境界", "功法", "丹药", "灵石", "升级"), "修炼与资源"),
            (("打脸", "装逼", "身份"), "身份与爽点"),
            (("势力", "敌对"), "势力与敌对"),
            (("伏笔", "线索", "回收", "真相"), "伏笔与线索"),
        ],
        "fallback_topic": "剧情关键线索",
    },
    "xianxia": {
        "keywords": (
            "修仙", "境界", "突破", "功法", "丹药", "灵石", "法宝",
            "宗门", "长老", "弟子", "秘境", "机缘", "渡劫", "飞升",
            "敌对", "势力", "恩怨", "师徒", "身份", "伏笔", "线索",
        ),
        "topics": [
            (("境界", "突破", "功法", "丹药", "灵石", "法宝"), "修炼体系与资源"),
            (("宗门", "长老", "弟子", "秘境", "机缘"), "宗门与机缘"),
            (("敌对", "势力", "恩怨", "师徒", "身份"), "人物关系与势力"),
            (("伏笔", "线索", "渡劫", "飞升"), "长线伏笔与目标"),
        ],
        "fallback_topic": "剧情关键线索",
    },
    "romance": {
        "keywords": (
            "感情", "心动", "吃醋", "误会", "和解", "表白", "分手",
            "重逢", "身份", "关系", "家族", "前任", "暗恋", "追求",
            "伏笔", "真相", "来历",
        ),
        "topics": [
            (("感情", "心动", "吃醋", "误会", "和解", "表白"), "感情线与情绪"),
            (("身份", "关系", "家族", "前任", "暗恋", "追求"), "人物关系与身份"),
            (("伏笔", "真相", "来历"), "伏笔与真相"),
        ],
        "fallback_topic": "剧情关键线索",
    },
    "mystery": {
        "keywords": (
            "凶手", "动机", "线索", "证据", "推理", "真相", "嫌疑",
            "不在场证明", "目击", "指纹", "遗书", "密室", "伏笔",
            "回收", "身份", "来历",
        ),
        "topics": [
            (("凶手", "动机", "嫌疑", "不在场证明"), "案件与嫌疑人"),
            (("线索", "证据", "推理", "目击", "指纹", "遗书", "密室"), "线索与推理"),
            (("真相", "身份", "来历", "伏笔", "回收"), "真相与伏笔"),
        ],
        "fallback_topic": "剧情关键线索",
    },
    "rules-mystery": {
        "keywords": (
            "规则", "污染", "异常", "调查", "收容", "理智", "代价",
            "真相", "线索", "伏笔", "回收", "身份", "来历", "敌对",
        ),
        "topics": [
            (("规则", "污染", "异常", "理智", "代价"), "规则与异常"),
            (("调查", "收容", "线索", "真相"), "调查与真相"),
            (("身份", "来历", "敌对", "伏笔", "回收"), "身份与伏笔"),
        ],
        "fallback_topic": "剧情关键线索",
    },
    "urban-power": {
        "keywords": (
            "异能", "觉醒", "隐藏", "低调", "装逼", "打脸", "身份",
            "掉马", "家族", "公司", "商业", "舆论", "敌对", "势力",
            "伏笔", "线索", "真相",
        ),
        "topics": [
            (("异能", "觉醒", "隐藏", "低调", "掉马"), "异能与身份"),
            (("装逼", "打脸", "家族", "公司", "商业", "舆论"), "社会与商业"),
            (("敌对", "势力", "伏笔", "线索", "真相"), "势力与伏笔"),
        ],
        "fallback_topic": "剧情关键线索",
    },
    "zhihu-short": {
        "keywords": (
            "反转", "情绪", "冲突", "身份", "真相", "伏笔", "回收",
            "关系", "恩怨", "来历", "选择", "代价",
        ),
        "topics": [
            (("反转", "身份", "真相", "来历"), "反转与真相"),
            (("情绪", "冲突", "关系", "恩怨"), "情绪与冲突"),
            (("伏笔", "回收", "选择", "代价"), "伏笔与选择"),
        ],
        "fallback_topic": "剧情关键线索",
    },
    "substitute": {
        "keywords": (
            "替身", "虐心", "误会", "反转", "追妻", "火葬场", "身份",
            "真相", "前任", "暗恋", "关系", "情绪", "伏笔", "回收",
        ),
        "topics": [
            (("替身", "虐心", "误会", "追妻", "火葬场"), "情感主线"),
            (("身份", "真相", "前任", "暗恋", "关系"), "身份与关系"),
            (("情绪", "反转", "伏笔", "回收"), "情绪与伏笔"),
        ],
        "fallback_topic": "剧情关键线索",
    },
    "esports": {
        "keywords": (
            "比赛", "战队", "英雄", "BP", "团战", "逆风", "翻盘",
            "冠军", "积分", "排名", "舆论", "队友", "教练", "对手",
            "战术", "操作", "伏笔", "线索",
        ),
        "topics": [
            (("比赛", "战队", "英雄", "BP", "团战", "战术", "操作"), "比赛与战术"),
            (("逆风", "翻盘", "冠军", "积分", "排名"), "赛事进程"),
            (("舆论", "队友", "教练", "对手"), "团队与舆论"),
            (("伏笔", "线索"), "伏笔与线索"),
        ],
        "fallback_topic": "剧情关键线索",
    },
    "livestream": {
        "keywords": (
            "直播", "流量", "榜单", "带货", "粉丝", "黑粉", "PK",
            "平台", "签约", "舆论", "反转", "身份", "掉马", "敌对",
            "伏笔", "线索", "真相",
        ),
        "topics": [
            (("直播", "流量", "榜单", "带货", "PK", "粉丝", "黑粉"), "直播与流量"),
            (("平台", "签约", "舆论", "反转"), "平台与舆论"),
            (("身份", "掉马", "敌对", "伏笔", "线索", "真相"), "身份与伏笔"),
        ],
        "fallback_topic": "剧情关键线索",
    },
    "cosmic-horror": {
        "keywords": (
            "克苏鲁", "污染", "理智", "疯狂", "古神", "仪式", "禁忌",
            "调查", "真相", "代价", "规则", "异常", "身份", "来历",
            "伏笔", "线索", "回收",
        ),
        "topics": [
            (("克苏鲁", "污染", "理智", "疯狂", "古神", "仪式", "禁忌"), "恐怖与规则"),
            (("调查", "真相", "代价", "异常"), "调查与真相"),
            (("身份", "来历", "伏笔", "线索", "回收"), "身份与伏笔"),
        ],
        "fallback_topic": "剧情关键线索",
    },
    "history-travel": {
        "keywords": (
            "穿越", "历史", "知识", "种田", "发家", "改革", "科举",
            "朝堂", "战争", "身份", "来历", "势力", "敌对", "伏笔",
            "线索", "真相",
        ),
        "topics": [
            (("穿越", "历史", "知识", "种田", "发家", "改革", "科举"), "穿越与知识优势"),
            (("朝堂", "战争", "势力", "敌对"), "朝堂与势力"),
            (("身份", "来历", "伏笔", "线索", "真相"), "身份与伏笔"),
        ],
        "fallback_topic": "剧情关键线索",
    },
    "military": {
        "keywords": (
            "军营", "晋升", "军衔", "派系", "训练", "战备", "轮战",
            "情报网", "调查", "内鬼", "间谍", "转业", "退伍", "立功",
            "评功", "战报", "档案", "政审", "敌对", "势力", "恩怨",
            "师徒", "身份", "伏笔", "线索", "真相",
        ),
        "topics": [
            (("军营", "晋升", "军衔", "派系", "训练", "战备", "轮战"), "军旅晋升与战备"),
            (("情报网", "调查", "内鬼", "间谍", "转业", "退伍"), "情报与身份转折"),
            (("立功", "评功", "战报", "档案", "政审"), "军功与体制规则"),
            (("敌对", "势力", "恩怨", "师徒", "身份"), "人物关系与势力"),
            (("伏笔", "线索", "真相"), "长线伏笔与真相"),
        ],
        "fallback_topic": "剧情关键线索",
    },
    "business": {
        "keywords": (
            "国企", "改制", "并购", "资金链", "上市", "合规", "审查",
            "竞争对手", "市场份额", "供应链", "管理层", "裁员", "扭亏",
            "盈利", "董事会", "股东", "谈判", "合同", "违约", "舆论",
            "身份", "敌对", "势力", "伏笔", "线索", "真相",
        ),
        "topics": [
            (("国企", "改制", "并购", "上市", "资金链"), "商业变革与资本运作"),
            (("合规", "审查", "竞争对手", "市场份额", "供应链"), "竞争与合规博弈"),
            (("管理层", "裁员", "扭亏", "盈利", "董事会", "股东"), "企业管理与决策"),
            (("谈判", "合同", "违约", "舆论", "身份", "敌对", "势力"), "商战交锋与关系"),
            (("伏笔", "线索", "真相"), "伏笔与真相"),
        ],
        "fallback_topic": "剧情关键线索",
    },
    "game-lit": {
        "keywords": (
            "游戏", "系统", "副本", "BOSS", "装备", "技能", "属性",
            "升级", "公会", "队友", "NPC", "任务", "金手指", "敌对",
            "伏笔", "线索", "真相",
        ),
        "topics": [
            (("游戏", "系统", "副本", "BOSS", "装备", "技能", "属性", "升级"), "游戏与成长"),
            (("公会", "队友", "NPC", "任务", "金手指"), "社交与系统"),
            (("敌对", "伏笔", "线索", "真相"), "敌对与伏笔"),
        ],
        "fallback_topic": "剧情关键线索",
    },
}


def _load_genre_from_state(project_root: Path) -> str:
    """从 state.json 读取题材信息。"""
    state_file = project_root / ".webnovel" / "state.json"
    if not state_file.exists():
        return ""
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        project = state.get("project") or state.get("project_info") or {}
        genre = str(project.get("genre") or "").strip()
        return genre
    except Exception:
        return ""


def _split_genre_keys(genre: str) -> List[str]:
    """拆分复合题材，支持 A+B / A/B / A、B / A与B。"""
    raw = re.sub(r"[＋/、]", "+", genre)
    raw = raw.replace("与", "+")
    return [p.strip() for p in raw.split("+") if p.strip()]


def _get_rag_trigger_config(genre: str) -> Dict[str, Any]:
    """根据题材获取 RAG trigger 配置，复合题材自动合并子配置。"""
    if not genre:
        return _RAG_TRIGGER_PROFILES["default"]

    parts = _split_genre_keys(genre)
    profile_keys = []
    for part in parts:
        key = _get_profile_key(part)
        if key and key not in profile_keys:
            profile_keys.append(key)

    if not profile_keys:
        return _RAG_TRIGGER_PROFILES["default"]

    # 单题材直接返回
    if len(profile_keys) == 1:
        return _RAG_TRIGGER_PROFILES.get(profile_keys[0], _RAG_TRIGGER_PROFILES["default"])

    # 复合题材：合并 keywords、topics，fallback_topic 取第一个非 default
    merged_keywords: List[str] = []
    merged_topics: List[Any] = []
    fallback_topic = _RAG_TRIGGER_PROFILES["default"]["fallback_topic"]

    for key in profile_keys:
        cfg = _RAG_TRIGGER_PROFILES.get(key)
        if not cfg:
            continue
        for kw in cfg.get("keywords", ()):
            if kw not in merged_keywords:
                merged_keywords.append(kw)
        for topic in cfg.get("topics", []):
            if topic not in merged_topics:
                merged_topics.append(topic)
        if fallback_topic == _RAG_TRIGGER_PROFILES["default"]["fallback_topic"]:
            fallback_topic = cfg.get("fallback_topic", fallback_topic)

    if not merged_keywords:
        return _RAG_TRIGGER_PROFILES["default"]

    return {
        "keywords": tuple(merged_keywords),
        "topics": merged_topics,
        "fallback_topic": fallback_topic,
    }


def find_project_root(start_path: Path | None = None) -> Path:
    """解析真实书项目根（包含 `.webnovel/state.json` 的目录）。"""
    from project_locator import resolve_project_root

    if start_path is None:
        return resolve_project_root()
    return resolve_project_root(str(start_path))


def extract_chapter_outline(project_root: Path, chapter_num: int) -> str:
    """Extract chapter outline segment from volume outline file."""
    return load_chapter_outline(project_root, chapter_num, max_chars=1500)


def _load_summary_file(project_root: Path, chapter_num: int) -> str:
    """Load summary section from `.webnovel/summaries/chNNNN.md`."""
    summary_path = project_root / ".webnovel" / "summaries" / f"ch{chapter_num:04d}.md"
    if not summary_path.exists():
        return ""

    text = summary_path.read_text(encoding="utf-8")
    summary_match = re.search(r"##\s*剧情摘要\s*\r?\n(.+?)(?=\r?\n##|$)", text, re.DOTALL)
    if summary_match:
        return summary_match.group(1).strip()
    return ""


def extract_chapter_summary(project_root: Path, chapter_num: int) -> str:
    """Extract chapter summary, fallback to chapter body head."""
    summary = _load_summary_file(project_root, chapter_num)
    if summary:
        return summary

    chapter_file = find_chapter_file(project_root, chapter_num)
    if not chapter_file or not chapter_file.exists():
        return f"⚠️ 第{chapter_num}章文件不存在"

    content = chapter_file.read_text(encoding="utf-8")

    summary_match = re.search(r"##\s*本章摘要\s*\r?\n(.+?)(?=\r?\n##|$)", content, re.DOTALL)
    if summary_match:
        return summary_match.group(1).strip()

    stats_match = re.search(r"##\s*本章统计\s*\r?\n(.+?)(?=\r?\n##|$)", content, re.DOTALL)
    if stats_match:
        return f"[无摘要，仅统计]\n{stats_match.group(1).strip()}"

    lines = content.split("\n")
    text_lines = [line for line in lines if not line.startswith("#") and line.strip()]
    text = "\n".join(text_lines)[:500]
    return f"[自动截取前500字]\n{text}..."


def extract_state_summary(project_root: Path) -> str:
    """Extract key fields from `.webnovel/state.json`."""
    state_file = project_root / ".webnovel" / "state.json"
    if not state_file.exists():
        return "⚠️ state.json 不存在"

    state = json.loads(state_file.read_text(encoding="utf-8"))
    summary_parts: List[str] = []

    if "progress" in state:
        progress = state["progress"]
        summary_parts.append(
            f"**进度**: 第{progress.get('current_chapter', '?')}章 / {progress.get('total_words', '?')}字"
        )

    if "protagonist_state" in state:
        ps = state["protagonist_state"]
        power = ps.get("power", {})
        summary_parts.append(f"**主角实力**: {power.get('realm', '?')} {power.get('layer', '?')}层")
        summary_parts.append(f"**当前位置**: {ps.get('location', '?')}")
        golden_finger = ps.get("golden_finger", {})
        summary_parts.append(
            f"**金手指**: {golden_finger.get('name', '?')} Lv.{golden_finger.get('level', '?')}"
        )

    if "strand_tracker" in state:
        tracker = state["strand_tracker"]
        history = tracker.get("history", [])[-5:]
        if history:
            items: List[str] = []
            for row in history:
                if not isinstance(row, dict):
                    continue
                chapter = row.get("chapter", "?")
                strand = row.get("strand") or row.get("dominant") or "unknown"
                items.append(f"Ch{chapter}:{strand}")
            if items:
                summary_parts.append(f"**近5章Strand**: {', '.join(items)}")

    plot_threads = state.get("plot_threads", {}) if isinstance(state.get("plot_threads"), dict) else {}
    foreshadowing = plot_threads.get("foreshadowing", [])
    if isinstance(foreshadowing, list) and foreshadowing:
        active = [row for row in foreshadowing if row.get("status") in {"active", "未回收"}]
        urgent = [row for row in active if row.get("urgency", 0) > 50]
        if urgent:
            urgent_list = [
                f"{row.get('content', '?')[:30]}... (紧急度:{row.get('urgency')})"
                for row in urgent[:3]
            ]
            summary_parts.append(f"**紧急伏笔**: {'; '.join(urgent_list)}")

    return "\n".join(summary_parts)


def _normalize_outline_text(outline: str) -> str:
    text = str(outline or "")
    if not text or text.startswith("⚠️"):
        return ""
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_rag_query(
    outline: str,
    chapter_num: int,
    min_chars: int,
    max_chars: int,
    genre: str = "",
) -> str:
    plain = _normalize_outline_text(outline)
    if not plain or len(plain) < min_chars:
        return ""

    config = _get_rag_trigger_config(genre)
    keywords = config["keywords"]
    if not any(keyword in plain for keyword in keywords):
        return ""

    topic = config["fallback_topic"]
    for keyword_tuple, topic_label in config["topics"]:
        if any(kw in plain for kw in keyword_tuple):
            topic = topic_label
            break

    clean_max = max(40, int(max_chars))
    return f"第{chapter_num}章 {topic}：{plain[:clean_max]}"


def _search_with_rag(
    project_root: Path,
    chapter_num: int,
    query: str,
    top_k: int,
) -> Dict[str, Any]:
    _ensure_scripts_path()
    from data_modules.config import DataModulesConfig
    from data_modules.rag_adapter import RAGAdapter

    config = DataModulesConfig.from_project_root(project_root)
    adapter = RAGAdapter(config)
    intent_payload = adapter.query_router.route_intent(query)
    center_entities = list(intent_payload.get("entities") or [])

    results = []
    mode = "auto"
    fallback_reason = ""
    has_embed_key = bool(str(getattr(config, "embed_api_key", "") or "").strip())
    if has_embed_key:
        try:
            results = asyncio.run(
                adapter.search(
                    query=query,
                    top_k=top_k,
                    strategy="auto",
                    chapter=chapter_num,
                    center_entities=center_entities,
                )
            )
        except Exception as exc:
            fallback_reason = f"auto_failed:{exc.__class__.__name__}"
            mode = "bm25_fallback"
            results = adapter.bm25_search(query=query, top_k=top_k, chapter=chapter_num)
    else:
        mode = "bm25_fallback"
        fallback_reason = "missing_embed_api_key"
        results = adapter.bm25_search(query=query, top_k=top_k, chapter=chapter_num)

    hits: List[Dict[str, Any]] = []
    for row in results:
        content = re.sub(r"\s+", " ", str(getattr(row, "content", "") or "")).strip()
        hits.append(
            {
                "chunk_id": str(getattr(row, "chunk_id", "") or ""),
                "chapter": int(getattr(row, "chapter", 0) or 0),
                "scene_index": int(getattr(row, "scene_index", 0) or 0),
                "score": round(float(getattr(row, "score", 0.0) or 0.0), 6),
                "source": str(getattr(row, "source", "") or mode),
                "source_file": str(getattr(row, "source_file", "") or ""),
                "content": content[:180],
            }
        )

    return {
        "invoked": True,
        "query": query,
        "mode": mode,
        "reason": fallback_reason or ("ok" if hits else "no_hit"),
        "intent": intent_payload.get("intent"),
        "needs_graph": bool(intent_payload.get("needs_graph")),
        "center_entities": center_entities,
        "hits": hits,
    }


def _load_rag_assist(project_root: Path, chapter_num: int, outline: str) -> Dict[str, Any]:
    _ensure_scripts_path()
    from data_modules.config import DataModulesConfig

    config = DataModulesConfig.from_project_root(project_root)
    enabled = bool(getattr(config, "context_rag_assist_enabled", True))
    top_k = max(1, int(getattr(config, "context_rag_assist_top_k", 4)))
    min_chars = max(20, int(getattr(config, "context_rag_assist_min_outline_chars", 40)))
    max_chars = max(40, int(getattr(config, "context_rag_assist_max_query_chars", 120)))
    base_payload = {"enabled": enabled, "invoked": False, "reason": "", "query": "", "hits": []}

    if not enabled:
        base_payload["reason"] = "disabled_by_config"
        return base_payload

    genre = _load_genre_from_state(project_root)
    query = _build_rag_query(
        outline, chapter_num=chapter_num, min_chars=min_chars, max_chars=max_chars, genre=genre
    )
    if not query:
        base_payload["reason"] = "outline_not_actionable"
        return base_payload

    vector_db = config.vector_db
    if not vector_db.exists() or vector_db.stat().st_size <= 0:
        base_payload["reason"] = "vector_db_missing_or_empty"
        return base_payload

    try:
        rag_payload = _search_with_rag(project_root=project_root, chapter_num=chapter_num, query=query, top_k=top_k)
        rag_payload["enabled"] = True
        return rag_payload
    except Exception as exc:
        base_payload["reason"] = f"rag_error:{exc.__class__.__name__}"
        return base_payload


def _load_contract_context(project_root: Path, chapter_num: int) -> Dict[str, Any]:
    """Build context via ContextManager and return selected sections."""
    _ensure_scripts_path()
    from data_modules.config import DataModulesConfig
    from data_modules.context_manager import ContextManager

    config = DataModulesConfig.from_project_root(project_root)
    manager = ContextManager(config)
    payload = manager.build_context(
        chapter=chapter_num,
        template="plot",
        use_snapshot=True,
        save_snapshot=True,
        max_chars=8000,
    )

    sections = payload.get("sections", {})
    return {
        "context_contract_version": (payload.get("meta") or {}).get("context_contract_version"),
        "context_weight_stage": (payload.get("meta") or {}).get("context_weight_stage"),
        "reader_signal": (sections.get("reader_signal") or {}).get("content", {}),
        "genre_profile": (sections.get("genre_profile") or {}).get("content", {}),
        "writing_guidance": (sections.get("writing_guidance") or {}).get("content", {}),
    }


def build_chapter_context_payload(project_root: Path, chapter_num: int) -> Dict[str, Any]:
    """Assemble full chapter context payload for text/json output."""
    outline = extract_chapter_outline(project_root, chapter_num)

    prev_summaries = []
    for prev_ch in range(max(1, chapter_num - 2), chapter_num):
        summary = extract_chapter_summary(project_root, prev_ch)
        prev_summaries.append(f"### 第{prev_ch}章摘要\n{summary}")

    state_summary = extract_state_summary(project_root)
    contract_context = _load_contract_context(project_root, chapter_num)
    rag_assist = _load_rag_assist(project_root, chapter_num, outline)

    return {
        "chapter": chapter_num,
        "outline": outline,
        "previous_summaries": prev_summaries,
        "state_summary": state_summary,
        "context_contract_version": contract_context.get("context_contract_version"),
        "context_weight_stage": contract_context.get("context_weight_stage"),
        "reader_signal": contract_context.get("reader_signal", {}),
        "genre_profile": contract_context.get("genre_profile", {}),
        "writing_guidance": contract_context.get("writing_guidance", {}),
        "rag_assist": rag_assist,
    }


def _render_text(payload: Dict[str, Any]) -> str:
    chapter_num = payload.get("chapter")
    lines: List[str] = []

    lines.append(f"# 第 {chapter_num} 章创作上下文")
    lines.append("")

    lines.append("## 本章大纲")
    lines.append("")
    lines.append(str(payload.get("outline", "")))
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 前文摘要")
    lines.append("")
    for item in payload.get("previous_summaries", []):
        lines.append(item)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 当前状态")
    lines.append("")
    lines.append(str(payload.get("state_summary", "")))
    lines.append("")

    contract_version = payload.get("context_contract_version")
    if contract_version:
        lines.append(f"## Contract ({contract_version})")
        lines.append("")
        stage = payload.get("context_weight_stage")
        if stage:
            lines.append(f"- 上下文阶段权重: {stage}")
            lines.append("")

    writing_guidance = payload.get("writing_guidance") or {}
    guidance_items = writing_guidance.get("guidance_items") or []
    checklist = writing_guidance.get("checklist") or []
    checklist_score = writing_guidance.get("checklist_score") or {}
    methodology = writing_guidance.get("methodology") or {}
    if guidance_items or checklist:
        lines.append("## 写作执行建议")
        lines.append("")
        for idx, item in enumerate(guidance_items, start=1):
            lines.append(f"{idx}. {item}")

        if checklist:
            total_weight = 0.0
            required_count = 0
            for row in checklist:
                if isinstance(row, dict):
                    try:
                        total_weight += float(row.get("weight") or 0)
                    except (TypeError, ValueError):
                        pass
                    if row.get("required"):
                        required_count += 1

            lines.append("")
            lines.append("### 执行检查清单（可评分）")
            lines.append("")
            lines.append(f"- 项目数: {len(checklist)}")
            lines.append(f"- 总权重: {total_weight:.2f}")
            lines.append(f"- 必做项: {required_count}")
            lines.append("")

            for idx, row in enumerate(checklist, start=1):
                if not isinstance(row, dict):
                    lines.append(f"{idx}. {row}")
                    continue
                label = str(row.get("label") or "").strip() or "未命名项"
                weight = row.get("weight")
                required_tag = "必做" if row.get("required") else "可选"
                verify_hint = str(row.get("verify_hint") or "").strip()
                lines.append(f"{idx}. [{required_tag}][w={weight}] {label}")
                if verify_hint:
                    lines.append(f"   - 验收: {verify_hint}")

        if checklist_score:
            lines.append("")
            lines.append("### 执行评分")
            lines.append("")
            lines.append(f"- 评分: {checklist_score.get('score')}")
            lines.append(f"- 完成率: {checklist_score.get('completion_rate')}")
            lines.append(f"- 必做完成率: {checklist_score.get('required_completion_rate')}")

        lines.append("")

    if isinstance(methodology, dict) and methodology.get("enabled"):
        lines.append("## 长篇方法论策略")
        lines.append("")
        lines.append(f"- 框架: {methodology.get('framework')}")
        methodology_scope = methodology.get("genre_profile_key") or methodology.get("pilot") or "general"
        lines.append(f"- 适用题材: {methodology_scope}")
        lines.append(f"- 章节阶段: {methodology.get('chapter_stage')}")
        observability = methodology.get("observability") or {}
        if observability:
            lines.append(
                "- 指标: "
                f"next_reason={observability.get('next_reason_clarity')}, "
                f"anchor={observability.get('anchor_effectiveness')}, "
                f"rhythm={observability.get('rhythm_naturalness')}"
            )
        signals = methodology.get("signals") or {}
        risk_flags = list(signals.get("risk_flags") or [])
        if risk_flags:
            lines.append(f"- 风险标记: {', '.join(str(flag) for flag in risk_flags)}")
        lines.append("")

    reader_signal = payload.get("reader_signal") or {}
    review_trend = reader_signal.get("review_trend") or {}
    if review_trend:
        overall_avg = review_trend.get("overall_avg")
        lines.append("## 追读信号")
        lines.append("")
        lines.append(f"- 最近审查均分: {overall_avg}")
        low_ranges = reader_signal.get("low_score_ranges") or []
        if low_ranges:
            lines.append(f"- 低分区间数: {len(low_ranges)}")
        lines.append("")

    genre_profile = payload.get("genre_profile") or {}
    if genre_profile.get("genre"):
        lines.append("## 题材锚定")
        lines.append("")
        lines.append(f"- 题材: {genre_profile.get('genre')}")
        genres = genre_profile.get("genres") or []
        if len(genres) > 1:
            lines.append(f"- 复合题材: {' + '.join(str(token) for token in genres)}")
            composite_hints = genre_profile.get("composite_hints") or []
            for row in composite_hints[:2]:
                lines.append(f"- {row}")
        refs = genre_profile.get("reference_hints") or []
        for row in refs[:3]:
            lines.append(f"- {row}")
        lines.append("")

    rag_assist = payload.get("rag_assist") or {}
    hits = rag_assist.get("hits") or []
    if rag_assist.get("invoked") and hits:
        lines.append("## RAG 检索线索")
        lines.append("")
        lines.append(f"- 模式: {rag_assist.get('mode')}")
        lines.append(f"- 意图: {rag_assist.get('intent')}")
        lines.append(f"- 查询: {rag_assist.get('query')}")
        lines.append("")
        for idx, row in enumerate(hits[:5], start=1):
            chapter = row.get("chapter", "?")
            scene_index = row.get("scene_index", "?")
            score = row.get("score", 0)
            source = row.get("source", "unknown")
            content = row.get("content", "")
            lines.append(f"{idx}. [Ch{chapter}-S{scene_index}][{source}][score={score}] {content}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="提取章节创作所需的精简上下文")
    parser.add_argument("--chapter", type=int, required=True, help="目标章节号")
    parser.add_argument("--project-root", type=str, help="项目根目录")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")

    args = parser.parse_args()

    try:
        project_root = (
            find_project_root(Path(args.project_root))
            if args.project_root
            else find_project_root()
        )
        payload = build_chapter_context_payload(project_root, args.chapter)

        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(_render_text(payload), end="")

    except Exception as exc:
        print(f"❌ 错误: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if sys.platform == "win32":
        enable_windows_utf8_stdio()
    main()

