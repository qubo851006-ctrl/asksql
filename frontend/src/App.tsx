import { useEffect, useRef, useState } from "react";
import { getSchema, queryNL, QueryResult } from "./api";
import "./App.css";

const EXAMPLE_GROUPS = [
  {
    title: "物业租赁",
    items: [
      "2026年4月物业租赁总租赁面积是多少？",
      "2026年4月物业租赁累计欠缴是多少？",
    ],
  },
  {
    title: "酒店项目",
    items: [
      "4月酒店客房营收排名",
      "北京中航泊悦酒店4月出租率是多少？",
    ],
  },
  {
    title: "物业服务",
    items: [
      "物业服务投诉量是多少？",
      "4月物业服务报事报修数量是多少？",
    ],
  },
  {
    title: "两利四率",
    items: [
      "2026年4月利润总额是多少？",
      "2026年4月资金存量是多少？",
      "2026年4月应收账款逾期应收是多少？",
    ],
  },
];

const MODULES = ["两利四率", "物业租赁", "物业服务", "酒店项目"];

interface HistoryItem {
  question: string;
  result: QueryResult;
  time: string;
}

function formatPeriod(period?: string) {
  if (!period) return "";
  const match = period.match(/^(\d{4})(\d{2})\d{2}-/);
  if (!match) return period;
  return `${match[1]}年${Number(match[2])}月`;
}

function ResultTable({ result }: { result: QueryResult }) {
  if (result.error) {
    return (
      <div className="error-box">
        <span className="error-tag">错误</span>
        <span>{result.error}</span>
      </div>
    );
  }

  if (result.row_count === 0) {
    return <div className="empty-tip">查询成功，暂无数据</div>;
  }

  return (
    <div className="table-wrap">
      <div className="result-meta">共 {result.row_count} 条结果</div>
      <table>
        <thead>
          <tr>
            {result.columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>{cell ?? "-"}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function App() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [schema, setSchema] = useState("");
  const [showSchema, setShowSchema] = useState(false);
  const [showSql, setShowSql] = useState(true);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  async function handleQuery(nextQuestion?: string) {
    const text = (nextQuestion ?? question).trim();
    if (!text || loading) return;

    setQuestion(text);
    setLoading(true);
    setResult(null);

    try {
      const res = await queryNL(text);
      setResult(res);
      setHistory((previous) => [
        { question: text, result: res, time: new Date().toLocaleTimeString() },
        ...previous.slice(0, 19),
      ]);
    } catch (error: any) {
      setResult({
        sql: "",
        columns: [],
        rows: [],
        row_count: 0,
        error: error.message || "查询失败",
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleToggleSchema() {
    if (!showSchema && !schema) {
      const nextSchema = await getSchema().catch((error) => `加载失败：${error.message}`);
      setSchema(nextSchema);
    }
    setShowSchema((value) => !value);
  }

  function handleKeyDown(event: React.KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleQuery();
    }
  }

  return (
    <div className="app">
      <header>
        <div className="brand">
          <span className="brand-mark">SQL</span>
          <div>
            <div className="brand-name">大屏问数</div>
            <div className="brand-sub">只读查询 · 指标结果表 · 2026年1-4月</div>
          </div>
        </div>
        <div className="header-status" aria-label="系统状态">
          <span>MariaDB</span>
          <span>只读</span>
          <span>4个模块</span>
        </div>
        <button className="btn-ghost" onClick={handleToggleSchema}>
          {showSchema ? "隐藏数据范围" : "查看数据范围"}
        </button>
      </header>

      {showSchema && (
        <div className="schema-panel">
          <pre>{schema || "加载中..."}</pre>
        </div>
      )}

      <main>
        <section className="scope-strip" aria-label="可问模块">
          <span className="scope-label">当前可问</span>
          {MODULES.map((module) => (
            <span className="scope-chip" key={module}>
              {module}
            </span>
          ))}
        </section>

        <section className="input-card">
          <label htmlFor="question">输入问题</label>
          <div className="input-row">
            <textarea
              id="question"
              ref={textareaRef}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="例如：2026年4月酒店客房营收排名，按 Enter 发送，Shift+Enter 换行"
              rows={3}
              disabled={loading}
            />
            <button
              className="btn-primary"
              onClick={() => handleQuery()}
              disabled={loading || !question.trim()}
            >
              {loading ? <span className="spinner" /> : "查询"}
            </button>
          </div>
        </section>

        <section className="examples" aria-label="示例问题">
          {EXAMPLE_GROUPS.map((group) => (
            <div className="example-group" key={group.title}>
              <div className="example-title">{group.title}</div>
              <div className="example-chips">
                {group.items.map((item) => (
                  <button
                    key={item}
                    className="chip"
                    onClick={() => handleQuery(item)}
                    disabled={loading}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </section>

        {result && (
          <section className="result-card">
            {result.summary && !result.error && (
              <div className="summary-box">
                <span className="summary-label">回答</span>
                <span className="summary-text">{result.summary}</span>
              </div>
            )}

            {result.plan && !result.error && (
              <div className="plan-bar">
                {result.plan.module_name && <span>{result.plan.module_name}</span>}
                {result.plan.target_name && <span>{result.plan.target_name}</span>}
                {result.plan.target_key && <span>{result.plan.target_key}</span>}
                {result.plan.period && <span>{formatPeriod(result.plan.period)}</span>}
              </div>
            )}

            {result.sql && (
              <div className="sql-block">
                <div className="sql-header">
                  <span>执行的白名单 SQL</span>
                  <button className="btn-ghost sm" onClick={() => setShowSql((value) => !value)}>
                    {showSql ? "收起" : "展开"}
                  </button>
                </div>
                {showSql && <pre className="sql-code">{result.sql}</pre>}
              </div>
            )}

            <ResultTable result={result} />
          </section>
        )}

        {history.length > 0 && (
          <section className="history">
            <div className="history-title">历史查询</div>
            {history.map((item, index) => (
              <button
                key={`${item.time}-${index}`}
                className="history-item"
                onClick={() => {
                  setQuestion(item.question);
                  setResult(item.result);
                }}
              >
                <span className="history-q">{item.question}</span>
                <span className="history-meta">
                  {item.time} · {item.result.error ? "错误" : `${item.result.row_count} 条`}
                </span>
              </button>
            ))}
          </section>
        )}
      </main>
    </div>
  );
}
