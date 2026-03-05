import csv
import io
from typing import Dict, Iterable


HEADER = [
    "天",
    "通知内容",
    "D0 PUSH 发送数",
    "D0 点击数",
    "D0 点击率",
    "D1 发送数",
    "D1 点击数",
    "D1 点击率",
]


def rows_to_csv_bytes(rows: Iterable[Dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADER)
    for row in rows:
        writer.writerow(
            [
                row["day"],
                row["notificationContent"],
                int(row["d0PushSent"]),
                int(row["d0Click"]),
                f"{float(row['d0ClickRate']) * 100:.2f}%",
                int(row["d1PushSent"]),
                int(row["d1Click"]),
                f"{float(row['d1ClickRate']) * 100:.2f}%",
            ]
        )
    return buffer.getvalue().encode("utf-8")
