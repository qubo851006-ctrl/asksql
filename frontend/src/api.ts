const BASE = "http://localhost:8100";

export interface QueryPlan {
  period?: string;
  module_name?: string;
  target_name?: string;
  target_key?: string;
  confidence?: number;
}

export interface QueryResult {
  sql: string;
  summary?: string;
  columns: string[];
  rows: Array<Array<string | number | null>>;
  row_count: number;
  plan?: QueryPlan;
  error: string | null;
}

export async function queryNL(question: string): Promise<QueryResult> {
  const res = await fetch(`${BASE}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(`请求失败：${res.status}`);
  return res.json();
}

export async function getSchema(): Promise<string> {
  const res = await fetch(`${BASE}/api/schema`);
  if (!res.ok) throw new Error("获取数据范围失败");
  const data = await res.json();
  return data.schema;
}
