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


def _normalize_int(value) -> int:
    if value is None:
        return 0
    if isinstance(value, float) and pd.isna(value):
        return 0
    text = str(value).strip()
    if not text:
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
        if row and row[0] == "事件名称":
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


def _build_header_index(df: pd.DataFrame) -> Dict[str, int]:
    if len(df.index) < 1:
        raise ValueError("文件为空，无法读取头部信息。")
    header_row = [str(item).strip() if item is not None else "" for item in df.iloc[0].tolist()]
    return {label: idx for idx, label in enumerate(header_row)}


def _extract_base_meta(df: pd.DataFrame) -> Dict[str, Union[int, str]]:
    if len(df.index) < 2:
        raise ValueError("缺少基础指标行（第 2 行）。")
    header_index = _build_header_index(df)
    values = df.iloc[1].tolist()

    def read_int(label: str) -> int:
        idx = header_index.get(label)
        if idx is None or idx >= len(values):
            return 0
        return _normalize_int(values[idx])

    def read_text(label: str) -> str:
        idx = header_index.get(label)
        if idx is None or idx >= len(values):
            return ""
        return str(values[idx]).strip() if values[idx] is not None else ""

    version = read_text("版本号") or "unknown"
    return {
        "version": version,
        "firstOpen": read_int("first open"),
        "authorizedUsers": read_int("通知授权用户数"),
        "uninstallUsers": read_int("卸载用户数"),
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


def _build_metrics(group: Dict[str, int], first_open: int, authorized_users: int, uninstall_users: int) -> Dict:
    d0_push_users = group["d0PushUsers"]
    d0_push_events = group["d0PushEvents"]
    d0_click_users = group["d0ClickUsers"]
    d0_click_events = group["d0ClickEvents"]
    d1_push_users = group["d1PushUsers"]
    d1_push_events = group["d1PushEvents"]
    d1_click_users = group["d1ClickUsers"]
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


def parse_dataframe(df: pd.DataFrame) -> Dict:
    base_meta = _extract_base_meta(df)
    version = str(base_meta["version"])
    first_open = int(base_meta["firstOpen"])
    authorized_users = int(base_meta["authorizedUsers"])
    uninstall_users = int(base_meta["uninstallUsers"])

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
        field_label = field_row[col_index]
        if N_LABEL_PATTERN.match(n_label):
            n_value = int(n_label)
            if field_label == "活跃用户":
                n_active_col[n_value] = col_index
            elif field_label == "事件数":
                n_event_col[n_value] = col_index
    if not n_event_col or not n_active_col:
        raise ValueError("未识别到第 N 天的活跃用户/事件数列映射。")

    max_n = max(n_event_col.keys())
    grouped_by_day = defaultdict(_empty_group)
    grouped_by_content = defaultdict(_empty_group)
    grouped_by_version = defaultdict(_empty_group)

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
        if not event_name or not DATE_PATTERN.match(first_visit_day):
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

        if "click" in lowered_event:
            for group in targets:
                group["d0ClickUsers"] += d0_active
                group["d0ClickEvents"] += d0_event
                group["d1ClickUsers"] += d1_active
                group["d1ClickEvents"] += d1_event

    daily_rows: List[Dict] = []
    for (row_batch, row_version, day), group in grouped_by_day.items():
        row = {"batch": row_batch, "version": row_version, "day": day}
        row.update(_build_metrics(group, first_open, authorized_users, uninstall_users))
        daily_rows.append(row)

    content_rows: List[Dict] = []
    for (row_batch, row_version, content), group in grouped_by_content.items():
        if content == "(not set)":
            continue
        row = {"batch": row_batch, "version": row_version, "content": content}
        row.update(_build_metrics(group, first_open, authorized_users, uninstall_users))
        content_rows.append(row)

    version_rows: List[Dict] = []
    for (row_batch, row_version), group in grouped_by_version.items():
        row = {"batch": row_batch, "version": row_version}
        row.update(_build_metrics(group, first_open, authorized_users, uninstall_users))
        version_rows.append(row)

    daily_rows.sort(key=lambda item: (item["batch"], item["version"], item["day"]))
    content_rows.sort(key=lambda item: (item["batch"], item["version"], item["content"]))
    version_rows.sort(key=lambda item: (item["batch"], item["version"]))

    return {
        "dailyByDay": daily_rows,
        "byContent": content_rows,
        "byVersionSummary": version_rows,
    }
