from pathlib import Path
import sys

from flask import Flask, jsonify, request

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from common.parser import parse_dataframe, read_table

app = Flask(__name__)


def _build_error(file_name, code, message, stage):
    return {"fileName": file_name, "code": code, "message": message, "stage": stage}


def _classify_parse_error(file_name, exc: Exception):
    message = str(exc)
    lowered = message.lower()
    if "事件映射未命中" in message:
        return _build_error(file_name, "E_EVENT_MAPPING_MISS", message, "validate")
    if "未识别到第 n 天" in lowered or "未找到表头行" in message or "版本号缺失" in message:
        return _build_error(file_name, "E_SCHEMA_INVALID", message, "read")
    return _build_error(file_name, "E_PARSE_FILE", message, "parse")


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
    notify_copy_rows = []
    for result in results:
        sheets = result.get("sheets", {})
        daily_rows.extend(sheets.get("dailyByDay", []))
        content_rows.extend(sheets.get("byContent", []))
        version_rows.extend(sheets.get("byVersionSummary", []))
        notify_copy_rows.extend(sheets.get("byNotifyCopyDay", []))

    merged_notify_rows = []
    notify_grouped = {}
    for row in notify_copy_rows:
        key = (
            row.get("batch", ""),
            row.get("nthDay", ""),
            row.get("dateRange", ""),
            row.get("projectCode", ""),
            row.get("version", ""),
            row.get("scene", ""),
            row.get("notifyName", ""),
        )
        if key not in notify_grouped:
            notify_grouped[key] = {"pushUsers": 0, "pushEvents": 0, "clickUsers": 0, "clickEvents": 0}
        notify_grouped[key]["pushUsers"] += int(float(row.get("pushUsers", 0)))
        notify_grouped[key]["pushEvents"] += int(float(row.get("pushEvents", 0)))
        notify_grouped[key]["clickUsers"] += int(float(row.get("clickUsers", 0)))
        notify_grouped[key]["clickEvents"] += int(float(row.get("clickEvents", 0)))

    for key, metrics in notify_grouped.items():
        (
            batch,
            nth_day,
            date_range,
            project_code,
            version,
            scene,
            notify_name,
        ) = key
        push_users = metrics["pushUsers"]
        push_events = metrics["pushEvents"]
        click_users = metrics["clickUsers"]
        click_events = metrics["clickEvents"]
        merged_notify_rows.append(
            {
                "batch": batch,
                "nthDay": nth_day,
                "dateRange": date_range or batch,
                "projectCode": project_code,
                "version": version,
                "scene": scene,
                "notifyName": notify_name,
                "pushUsers": push_users,
                "pushEvents": push_events,
                "clickUsers": click_users,
                "clickEvents": click_events,
                "userClickRate": (click_users / push_users) if push_users else 0,
                "eventClickRate": (click_events / push_events) if push_events else 0,
            }
        )
    merged_notify_rows.sort(
        key=lambda row: (
            row.get("batch", ""),
            row.get("nthDay", ""),
            row.get("projectCode", ""),
            row.get("version", ""),
            row.get("scene", ""),
            row.get("notifyName", ""),
        )
    )

    return {
        "fileName": "并表分析",
        "sheets": {
            "dailyByDay": _merge_sheet_rows(daily_rows, ("batch", "version", "day")),
            "byContent": _merge_sheet_rows(content_rows, ("batch", "version", "content")),
            "byVersionSummary": _merge_sheet_rows(version_rows, ("batch", "version")),
            "byNotifyCopyDay": merged_notify_rows,
        },
    }


def _parse_files_impl():
    files = request.files.getlist("files")
    if not files:
        return (
            jsonify(
                {
                    "results": [],
                    "errors": [_build_error("-", "E_NO_FILES", "未上传文件。", "upload")],
                }
            ),
            400,
        )

    merge_mode = str(request.form.get("mergeMode", "false")).lower() == "true"
    send_event_mapping = str(request.form.get("sendEventMapping", "") or "")
    click_event_mapping = str(request.form.get("clickEventMapping", "") or "")
    results = []
    errors = []

    for file in files:
        try:
            payload = file.read()
            dataframe = read_table(file.filename, payload)
            parsed = parse_dataframe(
                dataframe,
                include_batch=merge_mode,
                send_event_mapping=send_event_mapping,
                click_event_mapping=click_event_mapping,
            )
            sheets = {
                "dailyByDay": parsed["dailyByDay"],
                "byContent": parsed["byContent"],
                "byVersionSummary": parsed["byVersionSummary"],
                "byNotifyCopyDay": parsed.get("byNotifyCopyDay", []),
            }
            results.append({"fileName": file.filename, "sheets": sheets})
            issues = parsed.get("issues", [])
            if issues:
                preview = "；".join(issues[:10])
                suffix = "" if len(issues) <= 10 else f"；其余 {len(issues) - 10} 条已省略"
                errors.append(
                    _build_error(
                        file.filename,
                        "W_ROW_ISSUES",
                        f"检测到数据问题：{preview}{suffix}",
                        "validate",
                    )
                )
        except Exception as exc:
            errors.append(_classify_parse_error(file.filename, exc))

    if merge_mode and len(results) > 1:
        results.append(_build_merged_result(results))

    return jsonify({"results": results, "errors": errors})


@app.post("/")
def parse_files_root():
    return _parse_files_impl()


@app.post("/api/parse_python")
def parse_files_scoped():
    return _parse_files_impl()
