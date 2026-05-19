# -*- coding: utf-8 -*-
"""
MariaDB read-only helpers for the dashboard question-answering MVP.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from config import (
    MARIADB_DATABASE,
    MARIADB_HOST,
    MARIADB_PASSWORD,
    MARIADB_PORT,
    MARIADB_USER,
    QUERY_LIMIT,
)


_WRITE_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|replace|grant|revoke|call|load|outfile)\b",
    re.IGNORECASE,
)


def _connect():
    return pymysql.connect(
        host=MARIADB_HOST,
        port=MARIADB_PORT,
        user=MARIADB_USER,
        password=MARIADB_PASSWORD,
        database=MARIADB_DATABASE,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=DictCursor,
        connect_timeout=3,
        read_timeout=30,
        write_timeout=30,
    )


async def test_connection() -> None:
    await asyncio.to_thread(_run_scalar, "SELECT 1 AS ok", ())


def _run_scalar(sql: str, params: tuple[Any, ...]) -> Any:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return next(iter(row.values())) if row else None


def _validate_select(sql: str) -> str:
    stripped = sql.strip().rstrip(";")
    first = stripped.split(None, 1)[0].lower() if stripped else ""
    if first not in {"select", "with"}:
        raise ValueError("只允许执行 SELECT 查询")
    if _WRITE_RE.search(stripped):
        raise ValueError("SQL 包含非只读关键字，已拦截")
    if ";" in stripped:
        raise ValueError("一次只允许执行一条查询")
    if "data_analysis_ibds.t_resource_view" not in stripped:
        raise ValueError("MVP 仅允许查询 data_analysis_ibds.t_resource_view")
    if re.search(r"\blimit\b", stripped, flags=re.IGNORECASE) is None:
        stripped = f"{stripped} LIMIT {QUERY_LIMIT}"
    return stripped


def _execute(sql: str, params: tuple[Any, ...]) -> dict:
    safe_sql = _validate_select(sql)
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(safe_sql, params)
            rows = cur.fetchall()

    if not rows:
        return {"columns": [], "rows": [], "row_count": 0}

    columns = list(rows[0].keys())
    data = [[_stringify(row.get(col)) for col in columns] for row in rows]
    return {"columns": columns, "rows": data, "row_count": len(data)}


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


async def execute_query(sql: str, params: tuple[Any, ...] = ()) -> dict:
    return await asyncio.to_thread(_execute, sql, params)
