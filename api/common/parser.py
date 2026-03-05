import io
import re
import csv
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd


DATE_RANGE_PATTERN = re.compile(r"(\d{8})-(\d{8})")
N_LABEL_PATTERN = re.compile(r"^\d{4}$")
DATE_PATTERN = re.compile(r"^\d{8}$")
NOTIFY_PATTERN = re.compile(r"^notify_[^_]+_([A-Za-z]+?)(?:A\d+)?$")


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


def _extract_report_date(df: pd.DataFrame) -> str:
    for row_index in range(min(8, len(df.index))):
        for value in df.iloc[row_index].tolist():
            if value is None:
                continue
            match = DATE_RANGE_PATTERN.search(str(value))
            if match:
                return match.group(2)
    raise ValueError("未识别到导出日期区间（YYYYMMDD-YYYYMMDD）。")


def _find_event_header_row(df: pd.DataFrame) -> int:
    for row_index in range(len(df.index)):
        row = [str(item).strip() if item is not None else "" for item in df.iloc[row_index].tolist()]
        if row and row[0] == "事件名称":
            return row_index
    raise ValueError("未找到表头行（事件名称）。")


def _notify_group(name: str) -> str:
    notify_name = (name or "").strip()
    if notify_name == "notify_pdf05_fcm":
        return "fcm"
    match = NOTIFY_PATTERN.match(notify_name)
    if match:
        return match.group(1).lower()
    return notify_name.lower() or "unknown"


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


def parse_dataframe(df: pd.DataFrame) -> List[Dict]:
    report_date_text = _extract_report_date(df)
    report_date = datetime.strptime(report_date_text, "%Y%m%d").date()

    header_row = _find_event_header_row(df)
    if header_row < 1:
        raise ValueError("未找到第 N 天表头行。")

    n_row = [str(item).strip() if item is not None else "" for item in df.iloc[header_row - 1].tolist()]
    field_row = [str(item).strip() if item is not None else "" for item in df.iloc[header_row].tolist()]

    n_event_col: Dict[int, int] = {}
    for col_index in range(3, min(len(n_row), len(field_row))):
        n_label = n_row[col_index]
        field_label = field_row[col_index]
        if N_LABEL_PATTERN.match(n_label) and field_label == "事件数":
            n_event_col[int(n_label)] = col_index
    if not n_event_col:
        raise ValueError("未识别到第 N 天与事件数列映射。")

    max_n = max(n_event_col.keys())

    grouped = defaultdict(lambda: {"d0PushSent": 0, "d0Click": 0, "d1PushSent": 0, "d1Click": 0})

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

        d0_col = n_event_col.get(d0_n)
        d1_col = n_event_col.get(d1_n)
        d0_value = _normalize_int(row_values[d0_col]) if d0_col is not None and d0_col < len(row_values) else 0
        d1_value = _normalize_int(row_values[d1_col]) if d1_col is not None and d1_col < len(row_values) else 0

        key: Tuple[str, str] = (first_visit_day, _notify_group(notify_name))
        lowered_event = event_name.lower()
        if "push" in lowered_event:
            grouped[key]["d0PushSent"] += d0_value
            grouped[key]["d1PushSent"] += d1_value
        if "click" in lowered_event:
            grouped[key]["d0Click"] += d0_value
            grouped[key]["d1Click"] += d1_value

    rows: List[Dict] = []
    for (day, notification_content), values in grouped.items():
        d0_push = values["d0PushSent"]
        d0_click = values["d0Click"]
        d1_push = values["d1PushSent"]
        d1_click = values["d1Click"]
        rows.append(
            {
                "day": day,
                "notificationContent": notification_content,
                "d0PushSent": d0_push,
                "d0Click": d0_click,
                "d0ClickRate": (d0_click / d0_push) if d0_push else 0,
                "d1PushSent": d1_push,
                "d1Click": d1_click,
                "d1ClickRate": (d1_click / d1_push) if d1_push else 0,
            }
        )

    rows.sort(key=lambda item: (item["day"], item["notificationContent"]))
    return rows
