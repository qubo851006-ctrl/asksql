# 大屏问数 MVP 改造说明

## 当前范围

本版不是通用 Text2SQL，而是面向大屏指标结果表的受控问数：

- 两利四率及考核完成：`11002`
- 物业租赁：`11004`
- 物业服务：`11005`
- 酒店项目：`11006`

工程项目 `11003` 已按业务确认排除。

## 查询策略

自然语言问题先映射为：

- 期间：例如 `20260401-20260430`
- 模块：例如 `酒店项目`
- 指标：例如 `客房营收`
- 维度：例如 `北京中航泊悦酒店`

然后只查询：

```sql
data_analysis_ibds.t_resource_view
```

后端会拦截非 `SELECT`、写操作关键字、多语句以及非白名单表查询。

## 配置

后端配置文件示例：

```text
backend\.env.dashboard.example
```

把其中 MariaDB 配置复制到 `backend\.env`，尤其是：

```text
MARIADB_HOST=127.0.0.1
MARIADB_PORT=3306
MARIADB_USER=ask_readonly
MARIADB_PASSWORD=你的只读账号密码
MARIADB_DATABASE=data_analysis_ibds
DICTIONARY_DIR=C:\Users\shinh\Desktop\db_export_utf8_processed
```

## 启动

```powershell
cd /d D:\claude\text2sql\backend
python -m uvicorn main:app --host 0.0.0.0 --port 8100
```

如果 `8100` 已被占用，可以先查占用进程，或临时换端口。

## 可测试问题

- `2026年4月物业租赁总租赁面积是多少？`
- `4月酒店客房营收排名`
- `北京中航泊悦酒店4月出租率是多少？`
- `物业服务投诉量是多少？`
- `两利四率建开大合并是多少？`

## 已知限制

- 当前只覆盖大屏已生成的结果指标。
- 单位和口径还没有完整人工校准，比例类指标会按百分比展示。
- 同义词表是第一版，后续需要根据真实问法继续补。
