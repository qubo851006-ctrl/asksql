# -*- coding: utf-8 -*-
"""
Dictionary-driven dashboard question answering.

The MVP intentionally avoids free-form Text2SQL. Natural-language questions are
mapped to period/module/indicator/dimension slots, then converted to a small
whitelisted query against data_analysis_ibds.t_resource_view.
"""
from __future__ import annotations

import calendar
import csv
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from config import DICTIONARY_DIR, QUERY_LIMIT
from db import execute_query


MODULE_NAMES = {
    "11002": "两利四率及考核完成",
    "11004": "物业租赁",
    "11005": "物业服务",
    "11006": "酒店项目",
}

MODULE_ALIASES = {
    "11002": ["两利", "四率", "考核", "利润", "净利润", "资产负债", "现金", "研发", "劳动生产", "应收", "建开", "法人", "资金存量", "经济增加值"],
    "11004": ["物业租赁", "租赁", "租金", "出租", "楼宇", "写字楼", "客户数量", "租赁面积"],
    "11005": ["物业服务", "报事", "报修", "公寓", "物业费", "维修费", "满意率", "回访率", "完工率", "服务面积"],
    "11006": ["酒店", "客房", "餐饮", "房价", "revpar", "repar", "预算", "泊悦", "国航酒店"],
}

TWO_PROFIT_PROJECTS = {
    "11002001": ("利润总额", ["利润总额", "利润"]),
    "11002002": ("净利润", ["净利润"]),
    "11002003": ("营收利润率", ["营收利润率", "营业收入利润率"]),
    "11002004": ("资产负债率", ["资产负债率"]),
    "11002005": ("市场化写字楼物业出租率", ["市场化写字楼物业出租率", "写字楼出租率", "物业出租率"]),
    "11002006": ("全员劳动生产率", ["全员劳动生产率", "劳动生产率"]),
    "11002007": ("经济增加值", ["经济增加值", "eva"]),
    "11002008": ("公寓入住率", ["公寓入住率", "公寓出租率"]),
    "11002009": ("集团内部保障业务成本", ["集团内部保障业务成本", "保障业务成本", "内部保障成本"]),
    "11002010": ("资金存量", ["资金存量", "资金余额", "资金"]),
    "11002011": ("应收账款", ["应收账款", "应收款", "应收"]),
}

TWO_PROFIT_SUBTARGETS = {
    "外考核指标": ["外考核指标", "考核指标", "外部考核", "指标"],
    "内完成情况": ["内完成情况", "完成情况", "实际完成", "完成值", "完成"],
}

INDICATOR_ALIASES = {
    "客房营收": ["客房收入", "客房营收", "房费收入", "房费营收"],
    "餐饮营收": ["餐饮收入", "餐费", "餐饮营收"],
    "营收": ["酒店收入", "营业收入", "总营收", "营收"],
    "出租率": ["出租率", "入住率", "出房率"],
    "平均房费": ["平均房费", "平均房价", "房价"],
    "REPAR": ["repar", "revpar", "每间可售房收入"],
    "总租赁面积": ["租赁面积", "总面积", "出租面积", "总租赁面积"],
    "总客户数量": ["客户数量", "客户数", "租户数"],
    "平均租金": ["平均租金", "租金均价"],
    "已收金额": ["已收", "已收金额", "实收"],
    "应收金额": ["应收", "应收金额"],
    "累计欠缴": ["欠缴", "累计欠缴", "欠费"],
    "投诉量": ["投诉", "投诉量"],
    "完工率": ["完工率"],
    "回访率": ["回访率"],
    "满意率": ["满意率"],
    "服务总面积": ["服务面积", "服务总面积"],
    "年度物业服务合同额": ["合同额", "物业服务合同额"],
    "报事报修数量": ["报事报修", "报修数量", "报事报修数量"],
    "总房间数": ["房间数", "总房间数"],
    "累计营收": ["累计营收", "公寓营收"],
}


@dataclass(frozen=True)
class IndicatorRow:
    module_id: str
    module_name: str
    project_id: str
    target_id: str
    target_name: str
    target_key: str
    sample_period: str
    sample_value: str
    sort_no: str


@dataclass
class QueryPlan:
    period: str
    module_id: str | None
    project_id: str | None
    project_name: str | None
    target_id: str | None
    target_name: str | None
    target_key: str | None
    order: str | None
    limit: int
    confidence: float
    explanation: str


class DashboardDictionary:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.rows: list[IndicatorRow] = []
        self.periods: list[str] = []
        self.target_names: dict[str, set[str]] = {}
        self.target_ids_by_name: dict[tuple[str, str], set[str]] = {}
        self.keys_by_module: dict[str, set[str]] = {}
        self._load()

    def _load(self) -> None:
        path = self.base_dir / "dashboard_indicator_dictionary_utf8.tsv"
        if not path.exists():
            raise FileNotFoundError(f"未找到指标字典文件：{path}")
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for raw in reader:
                row = IndicatorRow(
                    module_id=_clean(raw.get("module_id")),
                    module_name=_clean(raw.get("module_name")),
                    project_id=_clean(raw.get("project_id")),
                    target_id=_clean(raw.get("target_id")),
                    target_name=_clean(raw.get("target_name")),
                    target_key=_clean(raw.get("target_key")),
                    sample_period=_clean(raw.get("sample_period")),
                    sample_value=_clean(raw.get("sample_value")),
                    sort_no=_clean(raw.get("sort_no")),
                )
                if row.module_id == "11003":
                    continue
                self.rows.append(row)
                self.target_names.setdefault(row.module_id, set()).add(row.target_name)
                self.target_ids_by_name.setdefault((row.module_id, row.target_name), set()).add(row.target_id)
                if row.target_key:
                    self.keys_by_module.setdefault(row.module_id, set()).add(row.target_key)

        self.periods = sorted({r.sample_period for r in self.rows if r.sample_period})

    @property
    def latest_period(self) -> str:
        return self.periods[-1] if self.periods else ""

    def schema_text(self) -> str:
        lines = [
            "大屏问数 MVP 数据范围",
            "主表：data_analysis_ibds.t_resource_view",
            "字段：c_bgq, c_module_id, c_project_id, c_target_id, c_target_name, c_target_key, c_target_value, n_pxh",
            "",
            "模块与指标：",
        ]
        for module_id, module_name in MODULE_NAMES.items():
            names = sorted(self.target_names.get(module_id, set()))
            lines.append(f"- {module_id} {module_name}：{', '.join(names)}")
        lines.append("")
        lines.append(f"可用期间：{', '.join(self.periods)}")
        return "\n".join(lines)


_DICT: DashboardDictionary | None = None


def load_dictionary() -> DashboardDictionary:
    global _DICT
    if _DICT is None:
        _DICT = DashboardDictionary(DICTIONARY_DIR)
    return _DICT


async def answer_question(question: str) -> dict:
    dictionary = load_dictionary()
    plan = build_plan(question, dictionary)
    if not plan.target_id and not plan.project_id:
        suggestions = suggest_indicators(question, dictionary, plan.module_id)
        return {
            "sql": "",
            "summary": "我还不能确定你要查哪个指标，可以换一种说法，或从下方候选指标里选一个。",
            "columns": ["模块", "可选指标"],
            "rows": suggestions,
            "row_count": len(suggestions),
            "error": None,
            "plan": plan_to_dict(plan),
        }

    sql, params = build_sql(plan)
    result = await execute_query(sql, params)
    summary = summarize_result(question, plan, result)
    return {"sql": render_sql(sql, params), "summary": summary, "error": None, "plan": plan_to_dict(plan), **result}


def build_plan(question: str, dictionary: DashboardDictionary) -> QueryPlan:
    q = question.strip()
    q_norm = q.lower()
    period = extract_period(q, dictionary)
    module_id = detect_module(q_norm)
    project_id, project_name, project_score = detect_two_profit_project(q_norm, module_id)
    if project_id:
        module_id = "11002"
    target_name, score = detect_indicator(q_norm, dictionary, module_id)
    if target_name and not module_id:
        module_id = module_for_indicator(target_name, dictionary)
    target_id = choose_two_profit_target_id(project_id, q_norm, dictionary) if project_id else None
    if not target_id:
        target_id = choose_target_id(module_id, target_name, dictionary) if module_id and target_name else None
    target_key = detect_dimension(q, dictionary, module_id)
    order = detect_order(q_norm)
    limit = detect_limit(q_norm)
    confidence = max(score, project_score)
    explanation = "按期间、模块、指标和维度从大屏结果表查询"
    display_name = project_name or target_name
    return QueryPlan(period, module_id, project_id, project_name, target_id, display_name, target_key, order, limit, confidence, explanation)


def extract_period(question: str, dictionary: DashboardDictionary) -> str:
    periods = set(dictionary.periods)
    year_month_patterns = [
        r"(20\d{2})\s*年\s*(1[0-2]|0?[1-9])\s*月",
        r"(20\d{2})[-/](1[0-2]|0?[1-9])",
    ]
    for pattern in year_month_patterns:
        match = re.search(pattern, question)
        if match:
            return period_for(int(match.group(1)), int(match.group(2)), periods) or dictionary.latest_period

    month_match = re.search(r"(?<!\d)(1[0-2]|0?[1-9])\s*月", question)
    if month_match:
        latest_year = int(dictionary.latest_period[:4]) if dictionary.latest_period else 2026
        return period_for(latest_year, int(month_match.group(1)), periods) or dictionary.latest_period

    return dictionary.latest_period


def period_for(year: int, month: int, periods: set[str]) -> str | None:
    last_day = calendar.monthrange(year, month)[1]
    period = f"{year}{month:02d}01-{year}{month:02d}{last_day:02d}"
    return period if period in periods else None


def detect_module(q_norm: str) -> str | None:
    best: tuple[int, str | None] = (0, None)
    for module_id, aliases in MODULE_ALIASES.items():
        hits = sum(1 for alias in aliases if alias.lower() in q_norm)
        if hits > best[0]:
            best = (hits, module_id)
    return best[1]


def detect_two_profit_project(q_norm: str, module_id: str | None) -> tuple[str | None, str | None, float]:
    if module_id and module_id != "11002":
        return None, None, 0.0

    best_project_id = None
    best_name = None
    best_score = 0.0
    for project_id, (name, aliases) in TWO_PROFIT_PROJECTS.items():
        score = score_indicator(q_norm, name)
        for alias in aliases:
            if alias.lower() in q_norm:
                score += max(4, len(alias))
        if score > best_score:
            best_project_id = project_id
            best_name = name
            best_score = score
    return (best_project_id, best_name, min(best_score / 8, 1.0)) if best_score >= 2 else (None, None, 0.0)


def detect_indicator(q_norm: str, dictionary: DashboardDictionary, module_id: str | None) -> tuple[str | None, float]:
    candidates: list[tuple[str, str]] = []
    module_ids = [module_id] if module_id else list(MODULE_NAMES)
    for mid in module_ids:
        for name in dictionary.target_names.get(mid, set()):
            candidates.append((mid, name))

    best_name = None
    best_score = 0.0
    for _, name in candidates:
        score = score_indicator(q_norm, name)
        for alias in INDICATOR_ALIASES.get(name, []):
            if alias.lower() in q_norm:
                score += max(3, len(alias))
        if score > best_score:
            best_name = name
            best_score = score
    return (best_name, min(best_score / 8, 1.0)) if best_score >= 2 else (None, 0.0)


def score_indicator(q_norm: str, name: str) -> float:
    if name.lower() in q_norm:
        return float(len(name) + 4)
    score = 0.0
    for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", name):
        if token and token.lower() in q_norm:
            score += min(len(token), 4)
    for ch in set(name):
        if "\u4e00" <= ch <= "\u9fff" and ch in q_norm:
            score += 0.6
    return score


def module_for_indicator(target_name: str, dictionary: DashboardDictionary) -> str | None:
    matches = [mid for mid in MODULE_NAMES if target_name in dictionary.target_names.get(mid, set())]
    return matches[0] if len(matches) == 1 else None


def choose_target_id(module_id: str, target_name: str, dictionary: DashboardDictionary) -> str | None:
    ids = sorted(dictionary.target_ids_by_name.get((module_id, target_name), set()))
    return ids[0] if ids else None


def choose_two_profit_target_id(project_id: str | None, q_norm: str, dictionary: DashboardDictionary) -> str | None:
    if not project_id:
        return None
    for target_name, aliases in TWO_PROFIT_SUBTARGETS.items():
        if any(alias.lower() in q_norm for alias in aliases):
            target_id = sorted(dictionary.target_ids_by_name.get(("11002", target_name), set()))
            prefix_matches = [tid for tid in target_id if tid.startswith(project_id)]
            return prefix_matches[0] if prefix_matches else None
    return None


def detect_dimension(question: str, dictionary: DashboardDictionary, module_id: str | None) -> str | None:
    module_ids = [module_id] if module_id else list(MODULE_NAMES)
    keys = []
    for mid in module_ids:
        keys.extend(dictionary.keys_by_module.get(mid, set()))
    for key in sorted(set(keys), key=len, reverse=True):
        if key and key in question:
            return key
    return None


def detect_order(q_norm: str) -> str | None:
    if any(word in q_norm for word in ["最低", "最少", "倒序", "后几", "bottom"]):
        return "asc"
    if any(word in q_norm for word in ["最高", "最多", "排名", "排行", "前", "top"]):
        return "desc"
    return None


def detect_limit(q_norm: str) -> int:
    match = re.search(r"(?:前|top)\s*(\d+)", q_norm)
    if match:
        return max(1, min(int(match.group(1)), QUERY_LIMIT))
    return QUERY_LIMIT


def build_sql(plan: QueryPlan) -> tuple[str, tuple[Any, ...]]:
    where = ["c_bgq = %s", "c_module_id = %s", "n_qybz = 1"]
    params: list[Any] = [plan.period, plan.module_id]
    if plan.target_id:
        where.append("c_target_id = %s")
        params.append(plan.target_id)
    elif plan.project_id:
        where.append("c_project_id = %s")
        params.append(plan.project_id)
    if plan.target_key:
        where.append("c_target_key = %s")
        params.append(plan.target_key)

    order_sql = "n_pxh ASC, c_target_key ASC"
    if plan.order == "desc":
        order_sql = "CAST(c_target_value AS DECIMAL(30, 6)) DESC"
    elif plan.order == "asc":
        order_sql = "CAST(c_target_value AS DECIMAL(30, 6)) ASC"

    sql = f"""
        SELECT
            c_bgq AS period,
            c_module_id AS module_id,
            c_project_id AS project_id,
            c_target_id AS target_id,
            c_target_name AS indicator,
            NULLIF(c_target_key, 'NULL') AS dimension,
            c_target_value AS value
        FROM data_analysis_ibds.t_resource_view
        WHERE {' AND '.join(where)}
        ORDER BY {order_sql}
        LIMIT {plan.limit}
    """
    return sql, tuple(params)


def render_sql(sql: str, params: tuple[Any, ...]) -> str:
    rendered = re.sub(r"\s+", " ", sql).strip()
    for param in params:
        rendered = rendered.replace("%s", repr(param), 1)
    return rendered


def summarize_result(question: str, plan: QueryPlan, result: dict) -> str:
    rows = result.get("rows", [])
    if not rows:
        label = f"{period_label(plan.period)} {plan.target_name or ''}".strip()
        return f"未查询到{label}的相关数据。"

    indicator = plan.target_name or "该指标"
    period = period_label(plan.period)
    if len(rows) == 1:
        row = dict(zip(result["columns"], rows[0]))
        dim = row.get("dimension")
        row_indicator = row.get("indicator")
        value = format_value(row.get("value"), indicator)
        if plan.project_name and row_indicator and row_indicator != plan.project_name:
            subject = f"{plan.project_name}{row_indicator}"
        else:
            subject = f"{dim}的{indicator}" if dim else indicator
        return f"{period}{subject}为 {value}。"

    values = []
    for row_values in rows[:5]:
        row = dict(zip(result["columns"], row_values))
        dim = row.get("dimension") or row.get("indicator") or indicator
        values.append(f"{dim} {format_value(row.get('value'), indicator)}")
    suffix = "；".join(values)
    return f"{period}{indicator}共查询到 {len(rows)} 条结果，前几项为：{suffix}。"


def format_value(value: Any, indicator: str) -> str:
    if value in (None, ""):
        return "暂无数据"
    text = str(value)
    try:
        number = Decimal(text)
    except InvalidOperation:
        return text

    if "率" in indicator or "占比" in indicator:
        pct = number * Decimal("100") if abs(number) <= 2 else number
        return f"{pct.quantize(Decimal('0.01'))}%"

    if number == number.to_integral():
        return f"{number.quantize(Decimal('1'))}"
    return f"{number.normalize():f}"


def period_label(period: str) -> str:
    match = re.match(r"(20\d{2})(\d{2})\d{2}-", period or "")
    if not match:
        return ""
    return f"{match.group(1)}年{int(match.group(2))}月"


def suggest_indicators(question: str, dictionary: DashboardDictionary, module_id: str | None) -> list[list[str]]:
    module_ids = [module_id] if module_id else list(MODULE_NAMES)
    rows = []
    for mid in module_ids:
        names = sorted(dictionary.target_names.get(mid, set()))
        if mid == "11002":
            names = [name for name, _ in TWO_PROFIT_PROJECTS.values()]
        if names:
            rows.append([MODULE_NAMES.get(mid, mid), "、".join(names[:20])])
    return rows


def plan_to_dict(plan: QueryPlan) -> dict:
    return {
        "period": plan.period,
        "module_id": plan.module_id,
        "module_name": MODULE_NAMES.get(plan.module_id or "", ""),
        "project_id": plan.project_id,
        "project_name": plan.project_name,
        "target_id": plan.target_id,
        "target_name": plan.target_name,
        "target_key": plan.target_key,
        "order": plan.order,
        "limit": plan.limit,
        "confidence": plan.confidence,
        "explanation": plan.explanation,
    }


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.upper() == "NULL" else text
