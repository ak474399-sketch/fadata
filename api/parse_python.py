from pathlib import Path
import sys

from flask import Flask, jsonify, request

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from common.parser import parse_dataframe, read_table

app = Flask(__name__)


def _empty_acc():
    return {
        "firstOpen": 0,
        "authorizedUsers": 0,
        "uninstallUsers": 0,
        "d0PushUsers": 0,
        "d0PushEvents": 0,
        "d0ClickUsers": 0,
        "d0ClickEvents": 0,
        "d1PushUsers": 0,
        "d1PushEvents": 0,
        "d1ClickUsers": 0,
        "d1ClickEvents": 0,
    }


def _merge_metrics(base):
    first_open = base["firstOpen"]
    authorized_users = base["authorizedUsers"]
    uninstall_users = base["uninstallUsers"]
    d0_push_users = base["d0PushUsers"]
    d0_push_events = base["d0PushEvents"]
    d0_click_users = base["d0ClickUsers"]
    d0_click_events = base["d0ClickEvents"]
    d1_push_users = base["d1PushUsers"]
    d1_push_events = base["d1PushEvents"]
    d1_click_users = base["d1ClickUsers"]
    d1_click_events = base["d1ClickEvents"]

    out = dict(base)
    out.update(
        {
            "authorizationRate": (authorized_users / first_open) if first_open else 0,
            "uninstallRate": (uninstall_users / first_open) if first_open else 0,
            "d0PenetrationRate": (d0_push_users / first_open) if first_open else 0,
            "d0AvgSentPerUser": (d0_push_events / d0_push_users) if d0_push_users else 0,
            "d0UserClickRate": (d0_click_users / d0_push_users) if d0_push_users else 0,
            "d0EventClickRate": (d0_click_events / d0_push_events) if d0_push_events else 0,
            "d0AvgClickPerUser": (d0_click_events / d0_click_users) if d0_click_users else 0,
            "d1PenetrationRate": (d1_push_users / first_open) if first_open else 0,
            "d1AvgSentPerUser": (d1_push_events / d1_push_users) if d1_push_users else 0,
            "d1UserClickRate": (d1_click_users / d1_push_users) if d1_push_users else 0,
            "d1EventClickRate": (d1_click_events / d1_push_events) if d1_push_events else 0,
            "d1AvgClickPerUser": (d1_click_events / d1_click_users) if d1_click_users else 0,
        }
    )
    return out


def _merge_sheet_rows(rows, key_fields):
    grouped = {}
    for row in rows:
        key = tuple(row.get(field, "") for field in key_fields)
        if key not in grouped:
            grouped[key] = _empty_acc()
        for metric_key in grouped[key]:
            grouped[key][metric_key] += int(float(row.get(metric_key, 0)))

    merged_rows = []
    for key, metrics in grouped.items():
        item = {field: key[idx] for idx, field in enumerate(key_fields)}
        item.update(_merge_metrics(metrics))
        merged_rows.append(item)
    merged_rows.sort(key=lambda row: tuple(row.get(field, "") for field in key_fields))
    return merged_rows


def _build_merged_result(results):
    daily_rows = []
    content_rows = []
    version_rows = []
    for result in results:
        sheets = result.get("sheets", {})
        daily_rows.extend(sheets.get("dailyByDay", []))
        content_rows.extend(sheets.get("byContent", []))
        version_rows.extend(sheets.get("byVersionSummary", []))

    return {
        "fileName": "并表分析",
        "sheets": {
            "dailyByDay": _merge_sheet_rows(daily_rows, ("batch", "version", "day")),
            "byContent": _merge_sheet_rows(content_rows, ("batch", "version", "content")),
            "byVersionSummary": _merge_sheet_rows(version_rows, ("batch", "version")),
        },
    }


def _parse_files_impl():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"results": [], "errors": [{"fileName": "-", "message": "未上传文件。"}]}), 400

    results = []
    errors = []

    for file in files:
        try:
            payload = file.read()
            dataframe = read_table(file.filename, payload)
            sheets = parse_dataframe(dataframe)
            results.append({"fileName": file.filename, "sheets": sheets})
        except Exception as exc:
            errors.append({"fileName": file.filename, "message": str(exc)})

    if len(results) > 1:
        results.append(_build_merged_result(results))

    return jsonify({"results": results, "errors": errors})


@app.post("/")
def parse_files_root():
    return _parse_files_impl()


@app.post("/api/parse_python")
def parse_files_scoped():
    return _parse_files_impl()
