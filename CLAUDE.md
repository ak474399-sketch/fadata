# FAData — AI Quick Reference

## Purpose
Push notification analytics tool. Accepts CSV/TSV/Excel files exported from a mobile analytics platform, parses event rows, and returns structured push metrics (D0/D1 penetration rates, click rates, etc.) across multiple report dimensions.

## Stack
| Layer | Tech |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript |
| Browser utilities | `xlsx`, `jszip` |
| Backend parser | Python 3, Flask, pandas, openpyxl/xlrd |
| Deploy | Vercel (Python Serverless functions via `api/*.py`) |

## Data Flow
```
Browser FormData (files + mergeMode + sendEventMapping + clickEventMapping)
  → POST /api/parse          (Next.js route: src/app/api/parse/route.ts)
    → POST /api/parse_python (Python Flask: api/parse_python.py)
      → read_table()         parses file bytes → pd.DataFrame
      → parse_dataframe()    extracts metrics → 4 sheet dicts
    → JSON { results[], errors[] }
  → UI renders result-table.tsx / triggers download
```

## Input File Format (CSV/TSV/XLSX)

Row layout (0-indexed):
- **Row 0** (header): `项目名称, first open, 卸载用户数, 通知授权用户数, DAY0发送用户数, DAY0点击数, DAY1发送用户数, DAY1点击数, 版本号, ...`
- **Row 1** (base meta): corresponding values (project code, counts, version string)
- **Rows 2–N** (comment/metadata): skipped until event header row is found
- **Event header row**: first column = `事件名称` (or `eventname`)
- **Row above event header**: `第 N 天` labels — 4-digit numbers like `0007`, `0006` … `0000`
- **Data rows**: `event_name, first_visit_date (YYYYMMDD), notify_name, [active_users, event_count] × N_days`

Required date range comment somewhere in rows 0–9: `YYYYMMDD-YYYYMMDD`

## Output Schema (`ParseResponse`)
```ts
{
  results: Array<{
    fileName: string,
    sheets: {
      dailyByDay:        AnalysisRow[],   // keyed by (batch, version, day)
      byContent:         AnalysisRow[],   // keyed by (batch, version, notifyGroup)
      byVersionSummary:  AnalysisRow[],   // keyed by (batch, version)
      byNotifyCopyDay:   NotifyCopyRow[], // keyed by (batch, nthDay, project, version, scene, notifyName)
    }
  }>,
  errors: Array<{ fileName, code, message, stage }>
}
```

### AnalysisRow key metrics
`firstOpen, authorizedUsers, authorizationRate, uninstallUsers, uninstallRate,`
`d0PushUsers, d0PushEvents, d0PenetrationRate, d0AvgSentPerUser,`
`d0ClickUsers, d0ClickEvents, d0UserClickRate, d0EventClickRate, d0AvgClickPerUser,`
`d1PushUsers, d1PushEvents, d1PenetrationRate, d1AvgSentPerUser,`
`d1ClickUsers, d1ClickEvents, d1UserClickRate, d1EventClickRate, d1AvgClickPerUser`

### NotifyCopyRow key fields
`nthDay ("DAY0"|"DAY1"), dateRange, projectCode, version, scene, notifyName,`
`pushUsers, pushEvents, clickUsers, clickEvents, userClickRate, eventClickRate`

## Error Codes
| Code | Stage | Cause |
|---|---|---|
| `E_NO_FILES` | upload | No files in request |
| `E_SCHEMA_INVALID` | read | Missing date range / header row / version column |
| `E_EVENT_MAPPING_MISS` | validate | Custom send/click keyword matched 0 events |
| `E_PARSE_FILE` | parse | Generic parse failure |
| `W_ROW_ISSUES` | validate | Non-fatal row-level issues (missing event name, bad date, missing notify) |
| `E_UPSTREAM_HTTP` | upstream | Python function returned non-2xx |
| `E_UPSTREAM_NON_JSON` | upstream | Python function returned non-JSON |
| `E_PARSE_UNAVAILABLE` | network | fetch() to `/api/parse_python` threw (local dev without Python) |

## Key Python Functions

### `api/common/parser.py`
| Function | Purpose |
|---|---|
| `read_table(file_name, payload)` | Bytes → DataFrame. Handles csv/tsv (utf-8 then gbk fallback), xlsx/xls |
| `parse_dataframe(df, include_batch, send_event_mapping, click_event_mapping, first_visit_range)` | Main entry. Returns `{dailyByDay, byContent, byVersionSummary, byNotifyCopyDay, issues}` |
| `_parse_visit_range(value)` | Parses compact (`20260305-20260307`) or hyphenated (`2026-03-05-2026-03-07`) range string → `(date, date)` or `None` |
| `_extract_base_meta(df)` | Reads row 0/1: project, version, firstOpen, user counts |
| `_extract_date_range(df)` | Scans rows 0–9 for `YYYYMMDD-YYYYMMDD` pattern |
| `_find_event_header_row(df)` | Finds row where col[0] == `事件名称` |
| `_notify_group(name)` | Groups notify name by stripping trailing numeric variants (e.g. `notify_pdf05_homeA4` → `notify_pdf05_home`) |
| `_notify_scene(name)` | Extracts scene segment from notify name (e.g. `notify_pdf05_unlock_07` → `unlock`) |
| `_build_metrics(group, ...)` | Computes derived rates from raw counts |

### `api/parse_python.py`
| Function | Purpose |
|---|---|
| `_parse_files_impl()` | Core handler: reads form data, loops files, calls parser, optionally merges |
| `_build_merged_result(results)` | Merges multiple file results into one "并表分析" entry |
| `_merge_metrics(base)` | Recomputes derived rates after summing raw counts |
| `_classify_parse_error(file_name, exc)` | Maps exception message → error code |

## Form Parameters (POST `/api/parse_python`)
| Field | Type | Description |
|---|---|---|
| `files` | file (multi) | CSV / TSV / XLSX / XLS file(s) |
| `mergeMode` | string `"true"/"false"` | Produce an extra merged "并表分析" result |
| `sendEventMapping` | string | Comma/semicolon/newline-separated custom send event keywords |
| `clickEventMapping` | string | Same for click events |
| `firstVisitDateRange` | string | Optional date range filter (see below) |

### firstVisitDateRange
Rows whose `first_visit_day` falls outside this range are **silently cleaned** before aggregation. A `W_ROW_ISSUES` warning reporting the cleaned count is emitted.

Accepted formats:
- Compact: `20260305-20260307`
- Hyphenated: `2026-03-05-2026-03-07`

If the string is empty or unparseable the filter is disabled (all rows included).

## Event Matching Logic
Default keywords: send = `["push", "sendnotification"]`, click = `["click", "clicknotification"]`
- Custom keywords passed via form fields `sendEventMapping` / `clickEventMapping` (comma/semicolon/newline separated)
- If custom keywords are provided but match 0 rows → raises `ValueError` → `E_EVENT_MAPPING_MISS`

## Metric Calculation (D0/D1)
For each data row, `delta_days = report_date - first_visit_date`.
- D0 column index: `max_n - delta_days`
- D1 column index: `max_n - delta_days + 1`

`byVersionSummary` uses pre-aggregated user counts from Row 1 (`DAY0/DAY1发送用户数`, `DAY0/DAY1点击数`) as the denominator instead of summed event rows, to avoid double-counting.

### Penetration Rate Denominators
| Metric | Formula |
|---|---|
| `d0PenetrationRate` | `d0PushUsers / authorizedUsers` |
| `d1PenetrationRate` | `d1PushUsers / firstOpen` |

> D0 uses **通知授权用户数** as the denominator (reflects reachable audience); D1 still uses `firstOpen`.

## Frontend Components
| File | Role |
|---|---|
| `src/app/page.tsx` | Main page: upload → parse → display; manages all state |
| `src/components/upload-panel.tsx` | File drag-drop + event mapping input |
| `src/components/metric-config-panel.tsx` | Toggle column visibility per sheet |
| `src/components/result-table.tsx` | Renders parsed sheet data as table |
| `src/lib/metric-config.ts` | Column definitions, localStorage persistence (`fadata.metric-config.v1`) |
| `src/types/report.ts` | All TypeScript types for parse response |

## Local Dev
```bash
# Frontend
npm run dev           # Next.js on http://localhost:3000

# Python parser (separate terminal)
cd api
pip install -r requirements.txt
flask --app parse_python run --port 5328
```
Note: Next.js `/api/parse` forwards to same-origin `/api/parse_python`. In local dev this requires the Python server running on the same host or a proxy. Vercel handles this natively via Python Serverless functions.

## Tests
```bash
cd api
pip install pytest
pytest tests/ -v
```
See `api/tests/` for unit tests (parser logic) and integration tests (Flask endpoints).
