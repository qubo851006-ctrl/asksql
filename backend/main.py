# -*- coding: utf-8 -*-
"""
Dashboard question-answering backend.

Start:
    python -m uvicorn main:app --host 0.0.0.0 --port 8100
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import execute_query, test_connection
from qa_engine import answer_question, load_dictionary


_schema_cache = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _schema_cache
    dictionary = load_dictionary()
    _schema_cache = dictionary.schema_text()
    try:
        await test_connection()
        print("[启动] MariaDB 连接成功，指标字典已加载")
    except Exception as exc:
        print(f"[启动] 指标字典已加载，但 MariaDB 连接测试失败：{exc}")
    yield
    print("[关闭] 服务已停止")


app = FastAPI(title="大屏问数 MVP", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str


class SqlRequest(BaseModel):
    sql: str


@app.get("/api/schema")
async def api_schema():
    return {"schema": _schema_cache}


@app.post("/api/query")
async def api_query(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    try:
        return await answer_question(req.question)
    except ValueError as exc:
        return {"sql": "", "summary": "", "columns": [], "rows": [], "row_count": 0, "error": str(exc)}
    except Exception as exc:
        return {"sql": "", "summary": "", "columns": [], "rows": [], "row_count": 0, "error": f"查询失败：{exc}"}


@app.post("/api/execute")
async def api_execute(req: SqlRequest):
    """只保留受限 SELECT 调试能力，MVP 不开放任意 SQL。"""
    try:
        return {"error": None, **await execute_query(req.sql)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        return {"columns": [], "rows": [], "row_count": 0, "error": str(exc)}


@app.get("/api/health")
async def health():
    return {"status": "ok"}
