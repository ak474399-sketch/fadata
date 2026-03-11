import csv
import io
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple, Union

import pandas as pd


DATE_RANGE_PATTERN = re.compile(r"(\d{8})-(\d{8})")
N_LABEL_PATTERN = re.compile(r"^\d{4}$")
DATE_PATTERN = re.compile(r"^\d{8}$")
ACTIVE_USER_LABELS = {"活跃用户", "活跃用户数", "activeusers", "activeuser"}
EVENT_COUNT_LABELS = {"事件数", "事件", "eventcount", "events", "event"}


def _normalize_label(text: str) -> str:
    return text.replace("\ufeff", "").replace(" ", "").replace("_", "").lower().strip()


def _normalize_int(value) -> int:
    if value is None:
        return 0
    if isinstance(value, float) and pd.isna(value):
        return 0
    text = str(value).strip()
    if not text:
        return 0
    text = text.replace(",", "").replace("，", "").replace(" ", "")
    lowered = text.lower()
    if lowered in {"nan", "none", "null", "-", "--"}:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def _extract_date_range(df: pd.DataFrame) -> Tuple[str, str]:
    for row_index in range(min(10, len(df.index))):
        for value in df.iloc[row_index].tolist():
            if value is None:
                continue
            match = DATE_RANGE_PATTERN.search(str(value))
            if match:
                return match.group(1), match.group(2)
    raise ValueError("未识别到导出日期区间（YYYYMMDD-YYYYMMDD）。")


def _find_event_header_row(df: pd.DataFrame) -> int:
    for row_index in range(len(df.index)):
        row = [str(item).strip() if item is not None else "" for item in df.iloc[row_index].tolist()]
        first_col = _normalize_label(row[0]) if row else ""
        if first_col in {"事件名称", "eventname"}:
            return row_index
    raise ValueError("未找到表头行（事件名称）。")


def _notify_group(name: str) -> str:
    notify_name = (name or "").strip()
    if not notify_name:
        return "unknown"
    if notify_name == "(not set)":
        return "(not set)"

    suffix = notify_name
    if notify_name.startswith("notify_"):
        parts = notify_name.split("_", 2)
        if len(parts) == 3:
            suffix = parts[2]

    suffix = re.sub(r"A\d+$", "", suffix, flags=re.IGNORECASE)
    suffix = re.sub(r"\d+$", "", suffix)
    suffix = suffix.strip("_").lower()
    return suffix or "unknown"


def _notify_scene(name: str) -> str:
    notify_name = (name or "").strip()
    if not notify_name:
        return "unknown"
    if notify_name == "(not set)":
        return "(not set)"
    parts = [part.strip() for part in notify_name.split("_") if part.strip()]
    if not parts:
        return "unknown"

    candidate = ""
    first_lower = parts[0].lower()
    if first_lower == "notify":
        candidate = parts[2] if len(parts) >= 3 else parts[-1]
    elif first_lower.startswith("notify"):
        candidate = parts[1] if len(parts) >= 2 else parts[-1]
    else:
        candidate = parts[-1]

    scene = re.sub(r"A\d+$", "", candidate, flags=re.IGNORECASE)
    scene = re.sub(r"\d+$", "", scene).strip().lower()
    return scene or "unknown"


def _build_header_index(df: pd.DataFrame) -> Dict[str, int]:
    if len(df.index) < 1:
        raise ValueError("文件为空，无法读取头部信息。")
    header_row = [str(item).strip() if item is not None else "" for item in df.iloc[0].tolist()]
    header_map: Dict[str, int] = {}
    for idx, label in enumerate(header_row):
        if not label:
            continue
        clean = label.replace("\ufeff", "").strip()
        header_map[clean] = idx
        header_map[_normalize_label(clean)] = idx
    return header_map


def _extract_base_meta(df: pd.DataFrame) -> Dict[str, Union[int, str]]:
    if len(df.index) < 2:
        raise ValueError("缺少基础指标行（第 2 行）。")
    header_index = _build_header_index(df)
    values = df.iloc[1].tolist()

    def get_idx(*labels: str) -> int:
        for label in labels:
            idx = header_index.get(label)
            if idx is not None:
                return idx
            idx = header_index.get(_normalize_label(label))
            if idx is not None:
                return idx
        return -1

    def read_int(*labels: str) -> int:
        idx = get_idx(*labels)
        if idx < 0 or idx >= len(values):
            return 0
        return _normalize_int(values[idx])

    def read_text(*labels: str) -> str:
        idx = get_idx(*labels)
        if idx < 0 or idx >= len(values):
            return ""
        return str(values[idx]).strip() if values[idx] is not None else ""

    version = read_text("版本号", "版本", "version", "Version")
    if not version:
        raise ValueError("第 2 行版本号缺失或表头不合法（应包含“版本号”列）。")

    return {
        "projectCode": read_text("项目名称", "项目代号", "project", "project_name"),
        "version": version,
        "firstOpen": read_int("first open", "first_open"),
        "authorizedUsers": read_int("通知授权用户数"),
        "uninstallUsers": read_int("卸载用户数"),
        # 优先使用报表前置汇总口径，避免事件明细重复触达导致用户数被放大。
        "d0PushUsersBase": read_int("DAY0发送用户数", "D0发送用户数", "day0_send_users"),
        "d1PushUsersBase": read_int("DAY1发送用户数", "D1发送用户数", "day1_send_users"),
        "d0ClickUsersBase": read_int("DAY0点击数", "D0点击数", "day0_click_users", "day0_clicks"),
        "d1ClickUsersBase": read_int("DAY1点击数", "D1点击数", "day1_click_users", "day1_clicks"),
    }


def read_table(file_name: str, payload: bytes) -> pd.DataFrame:
    lower_name = file_name.lower()
    stream = io.BytesIO(payload)

    def _from_delimited(text: str, delimiter: str) -> pd.DataFrame:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = [row for row in reader]
        if not rows:
            return pd.DataFrame()
        width = max(len(row) for row in rows)
        normalized = [row + [""] * (width - len(row)) for row in rows]
        return pd.DataFrame(normalized)

    if lower_name.endswith(".csv"):
        try:
            return _from_delimited(payload.decode("utf-8"), ",")
        except UnicodeDecodeError:
            return _from_delimited(payload.decode("gbk"), ",")
    if lower_name.endswith(".tsv"):
        try:
            return _from_delimited(payload.decode("utf-8"), "\t")
        except UnicodeDecodeError:
            return _from_delimited(payload.decode("gbk"), "\t")
    if lower_name.endswith(".xlsx") or lower_name.endswith(".xls"):
        return pd.read_excel(stream, header=None, dtype=str)
    raise ValueError("不支持的文件格式，仅支持 csv/tsv/xlsx/xls。")


def _empty_group() -> Dict[str, int]:
    return {
        "d0PushUsers": 0,
        "d0PushEvents": 0,
        "d0ClickUsers": 0,
        "d0ClickEvents": 0,
        "d1PushUsers": 0,
        "d1PushEvents": 0,
        "d1ClickUsers": 0,
        "d1ClickEvents": 0,
    }


def _build_metrics(
    group: Dict[str, int],
    first_open: int,
    authorized_users: int,
    uninstall_users: int,
    user_bases: Dict[str, int],
) -> Dict:
    d0_push_users = user_bases.get("d0PushUsersBase", 0) or group["d0PushUsers"]
    d0_push_events = group["d0PushEvents"]
    d0_click_users = user_bases.get("d0ClickUsersBase", 0) or group["d0ClickUsers"]
    d0_click_events = group["d0ClickEvents"]
    d1_push_users = user_bases.get("d1PushUsersBase", 0) or group["d1PushUsers"]
    d1_push_events = group["d1PushEvents"]
    d1_click_users = user_bases.get("d1ClickUsersBase", 0) or group["d1ClickUsers"]
    d1_click_events = group["d1ClickEvents"]

    return {
        "firstOpen": first_open,
        "authorizedUsers": authorized_users,
        "authorizationRate": (authorized_users / first_open) if first_open else 0,
        "uninstallUsers": uninstall_users,
        "uninstallRate": (uninstall_users / first_open) if first_open else 0,
        "d0PushUsers": d0_push_users,
        "d0PushEvents": d0_push_events,
        "d0PenetrationRate": (d0_push_users / first_open) if first_open else 0,
        "d0AvgSentPerUser": (d0_push_events / d0_push_users) if d0_push_users else 0,
        "d0ClickUsers": d0_click_users,
        "d0ClickEvents": d0_click_events,
        "d0UserClickRate": (d0_click_users / d0_push_users) if d0_push_users else 0,
        "d0EventClickRate": (d0_click_events / d0_push_events) if d0_push_events else 0,
        "d0AvgClickPerUser": (d0_click_events / d0_click_users) if d0_click_users else 0,
        "d1PushUsers": d1_push_users,
        "d1PushEvents": d1_push_events,
        "d1PenetrationRate": (d1_push_users / first_open) if first_open else 0,
        "d1AvgSentPerUser": (d1_push_events / d1_push_users) if d1_push_users else 0,
        "d1ClickUsers": d1_click_users,
        "d1ClickEvents": d1_click_events,
        "d1UserClickRate": (d1_click_users / d1_push_users) if d1_push_users else 0,
        "d1EventClickRate": (d1_click_events / d1_push_events) if d1_push_events else 0,
        "d1AvgClickPerUser": (d1_click_events / d1_click_users) if d1_click_users else 0,
    }


def parse_dataframe(df: pd.DataFrame, include_batch: bool = False) -> Dict:
    base_meta = _extract_base_meta(df)
    project_code = str(base_meta["projectCode"] or "").strip() or "unknown"
    version = str(base_meta["version"])
    first_open = int(base_meta["firstOpen"])
    authorized_users = int(base_meta["authorizedUsers"])
    uninstall_users = int(base_meta["uninstallUsers"])
    user_bases = {
        "d0PushUsersBase": int(base_meta["d0PushUsersBase"]),
        "d1PushUsersBase": int(base_meta["d1PushUsersBase"]),
        "d0ClickUsersBase": int(base_meta["d0ClickUsersBase"]),
        "d1ClickUsersBase": int(base_meta["d1ClickUsersBase"]),
    }

    date_start, date_end = _extract_date_range(df)
    batch = f"{date_start}-{date_end}"
    report_date = datetime.strptime(date_end, "%Y%m%d").date()

    header_row = _find_event_header_row(df)
    if header_row < 1:
        raise ValueError("未找到第 N 天表头行。")

    n_row = [str(item).strip() if item is not None else "" for item in df.iloc[header_row - 1].tolist()]
    field_row = [str(item).strip() if item is not None else "" for item in df.iloc[header_row].tolist()]

    n_active_col: Dict[int, int] = {}
    n_event_col: Dict[int, int] = {}
    for col_index in range(3, min(len(n_row), len(field_row))):
        n_label = n_row[col_index]
        field_label = _normalize_label(field_row[col_index])
        if N_LABEL_PATTERN.match(n_label):
            n_value = int(n_label)
            if field_label in ACTIVE_USER_LABELS:
                n_active_col[n_value] = col_index
            elif field_label in EVENT_COUNT_LABELS:
                n_event_col[n_value] = col_index
    if not n_event_col or not n_active_col:
        raise ValueError("未识别到第 N 天的活跃用户/事件数列映射。")

    max_n = max(n_event_col.keys())
    grouped_by_day = defaultdict(_empty_group)
    grouped_by_content = defaultdict(_empty_group)
    grouped_by_version = defaultdict(_empty_group)
    grouped_by_notify_day = defaultdict(
        lambda: {
            "pushUsers": 0,
            "pushEvents": 0,
            "clickUsers": 0,
            "clickEvents": 0,
        }
    )
    row_issues: List[str] = []

    def read_value(row_values: List, n_value: int, mapping: Dict[int, int]) -> int:
        col = mapping.get(n_value)
        if col is None or col >= len(row_values):
            return 0
        return _normalize_int(row_values[col])

    for row_index in range(header_row + 1, len(df.index)):
        row_values = df.iloc[row_index].tolist()
        if len(row_values) < 3:
            continue

        event_name = str(row_values[0]).strip() if row_values[0] is not None else ""
        first_visit_day = str(row_values[1]).strip() if row_values[1] is not None else ""
        notify_name = str(row_values[2]).strip() if row_values[2] is not None else ""
        csv_row_no = row_index + 1

        if not event_name and not first_visit_day and not notify_name:
            continue

        if not event_name:
            row_issues.append(f"第 {csv_row_no} 行事件名称缺失")
            continue
        if not DATE_PATTERN.match(first_visit_day):
            row_issues.append(f"第 {csv_row_no} 行首次访问日期不合法：{first_visit_day or '空值'}")
            continue
        if not notify_name:
            row_issues.append(f"第 {csv_row_no} 行通知内容缺失")
            continue

        first_day = datetime.strptime(first_visit_day, "%Y%m%d").date()
        delta_days = (report_date - first_day).days
        d0_n = max_n - delta_days
        d1_n = d0_n + 1

        d0_active = read_value(row_values, d0_n, n_active_col)
        d0_event = read_value(row_values, d0_n, n_event_col)
        d1_active = read_value(row_values, d1_n, n_active_col)
        d1_event = read_value(row_values, d1_n, n_event_col)

        content_key = _notify_group(notify_name)
        day_key: Tuple[str, str, str] = (batch, version, first_visit_day)
        content_group_key: Tuple[str, str, str] = (batch, version, content_key)
        version_key: Tuple[str, str] = (batch, version)

        targets = [grouped_by_day[day_key], grouped_by_content[content_group_key], grouped_by_version[version_key]]
        lowered_event = event_name.lower()

        if "push" in lowered_event:
            for group in targets:
                group["d0PushUsers"] += d0_active
                group["d0PushEvents"] += d0_event
                group["d1PushUsers"] += d1_active
                group["d1PushEvents"] += d1_event
            if notify_name != "(not set)":
                scene = _notify_scene(notify_name)
                day0_key = (batch, "DAY0", project_code, version, scene, notify_name)
                day1_key = (batch, "DAY1", project_code, version, scene, notify_name)
                grouped_by_notify_day[day0_key]["pushUsers"] += d0_active
                grouped_by_notify_day[day0_key]["pushEvents"] += d0_event
                grouped_by_notify_day[day1_key]["pushUsers"] += d1_active
                grouped_by_notify_day[day1_key]["pushEvents"] += d1_event

        if "click" in lowered_event:
            for group in targets:
                group["d0ClickUsers"] += d0_active
                group["d0ClickEvents"] += d0_event
                group["d1ClickUsers"] += d1_active
                group["d1ClickEvents"] += d1_event
            if notify_name != "(not set)":
                scene = _notify_scene(notify_name)
                day0_key = (batch, "DAY0", project_code, version, scene, notify_name)
                day1_key = (batch, "DAY1", project_code, version, scene, notify_name)
                grouped_by_notify_day[day0_key]["clickUsers"] += d0_active
                grouped_by_notify_day[day0_key]["clickEvents"] += d0_event
                grouped_by_notify_day[day1_key]["clickUsers"] += d1_active
                grouped_by_notify_day[day1_key]["clickEvents"] += d1_event

    daily_rows: List[Dict] = []
    for (row_batch, row_version, day), group in grouped_by_day.items():
        row = {"version": row_version, "day": day}
        if include_batch:
            row["batch"] = row_batch
        row.update(_build_metrics(group, first_open, authorized_users, uninstall_users, user_bases))
        daily_rows.append(row)

    content_rows: List[Dict] = []
    for (row_batch, row_version, content), group in grouped_by_content.items():
        if content == "(not set)":
            continue
        row = {"version": row_version, "content": content}
        if include_batch:
            row["batch"] = row_batch
        row.update(_build_metrics(group, first_open, authorized_users, uninstall_users, user_bases))
        content_rows.append(row)

    version_rows: List[Dict] = []
    for (row_batch, row_version), group in grouped_by_version.items():
        row = {"version": row_version}
        if include_batch:
            row["batch"] = row_batch
        row.update(_build_metrics(group, first_open, authorized_users, uninstall_users, user_bases))
        version_rows.append(row)

    notify_copy_rows: List[Dict] = []
    for (row_batch, nth_day, row_project, row_version, scene, notify_name), group in grouped_by_notify_day.items():
        push_users = int(group["pushUsers"])
        push_events = int(group["pushEvents"])
        click_users = int(group["clickUsers"])
        click_events = int(group["clickEvents"])
        row = {
            "nthDay": nth_day,
            "dateRange": row_batch,
            "projectCode": row_project,
            "version": row_version,
            "scene": scene,
            "notifyName": notify_name,
            "pushUsers": push_users,
            "pushEvents": push_events,
            "clickUsers": click_users,
            "clickEvents": click_events,
            "userClickRate": (click_users / push_users) if push_users else 0,
            "eventClickRate": (click_events / push_events) if push_events else 0,
        }
        if include_batch:
            row["batch"] = row_batch
        notify_copy_rows.append(row)

    if include_batch:
        daily_rows.sort(key=lambda item: (item.get("batch", ""), item["version"], item["day"]))
        content_rows.sort(key=lambda item: (item.get("batch", ""), item["version"], item["content"]))
        version_rows.sort(key=lambda item: (item.get("batch", ""), item["version"]))
        notify_copy_rows.sort(
            key=lambda item: (
                item.get("batch", ""),
                item["nthDay"],
                item["projectCode"],
                item["version"],
                item["scene"],
                item["notifyName"],
            )
        )
    else:
        daily_rows.sort(key=lambda item: (item["version"], item["day"]))
        content_rows.sort(key=lambda item: (item["version"], item["content"]))
        version_rows.sort(key=lambda item: (item["version"],))
        notify_copy_rows.sort(
            key=lambda item: (
                item["nthDay"],
                item["projectCode"],
                item["version"],
                item["scene"],
                item["notifyName"],
            )
        )

    return {
        "dailyByDay": daily_rows,
        "byContent": content_rows,
        "byVersionSummary": version_rows,
        "byNotifyCopyDay": notify_copy_rows,
        "issues": row_issues,
    }
