"""
Unit tests for api/common/parser.py

Run:  cd api && pytest tests/test_parser.py -v
"""
import io
import sys
from pathlib import Path

import pandas as pd
import pytest

# Make sure the api package is importable from any working directory.
API_DIR = Path(__file__).resolve().parent.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from common.parser import (
    _normalize_int,
    _normalize_label,
    _normalize_text,
    _parse_event_keywords,
    _parse_visit_range,
    _notify_group,
    _notify_scene,
    _extract_date_range,
    _find_event_header_row,
    _build_header_index,
    _extract_base_meta,
    read_table,
    parse_dataframe,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _df(*rows):
    """Build a DataFrame from a list of lists (all strings)."""
    width = max(len(r) for r in rows)
    padded = [r + [""] * (width - len(r)) for r in rows]
    return pd.DataFrame(padded)


def _minimal_csv(date_range="20260101-20260108") -> bytes:
    """Return the bytes of a minimal valid CSV that parse_dataframe can consume."""
    lines = [
        "项目名称,first open,卸载用户数,通知授权用户数,DAY0发送用户数,DAY0点击数,DAY1发送用户数,DAY1点击数,版本号",
        f"PDF05,1000,100,800,600,200,500,150,1.0.0",
        f"# {date_range}",
        "",
        ",,第 N 天,0001,0001,0000,0000",
        "事件名称,首次访问日期,notifyname,活跃用户,事件数,活跃用户,事件数",
        "pDnotifyPush,20260107,notify_pdf05_home,80,100,60,80",
        "pDnotifyClick,20260107,notify_pdf05_home,20,25,15,18",
    ]
    return "\n".join(lines).encode("utf-8")


# ---------------------------------------------------------------------------
# _normalize_int
# ---------------------------------------------------------------------------

class TestNormalizeInt:
    def test_plain_int(self):
        assert _normalize_int(42) == 42

    def test_float_str(self):
        assert _normalize_int("3.0") == 3

    def test_comma_separated(self):
        assert _normalize_int("1,234") == 1234

    def test_none_returns_zero(self):
        assert _normalize_int(None) == 0

    def test_nan_returns_zero(self):
        assert _normalize_int(float("nan")) == 0

    def test_nan_str_returns_zero(self):
        assert _normalize_int("NaN") == 0

    def test_dash_returns_zero(self):
        assert _normalize_int("-") == 0

    def test_empty_str_returns_zero(self):
        assert _normalize_int("") == 0

    def test_non_numeric_returns_zero(self):
        assert _normalize_int("abc") == 0


# ---------------------------------------------------------------------------
# _normalize_label
# ---------------------------------------------------------------------------

class TestNormalizeLabel:
    def test_strips_bom(self):
        assert _normalize_label("\ufeff事件名称") == "事件名称"

    def test_lowercase_and_strip(self):
        assert _normalize_label("  EventName  ") == "eventname"

    def test_removes_underscore(self):
        assert _normalize_label("active_users") == "activeusers"

    def test_removes_space(self):
        assert _normalize_label("event count") == "eventcount"


# ---------------------------------------------------------------------------
# _normalize_text
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_none_returns_empty(self):
        assert _normalize_text(None) == ""

    def test_nan_returns_empty(self):
        assert _normalize_text(float("nan")) == ""

    def test_null_str_returns_empty(self):
        assert _normalize_text("null") == ""

    def test_double_dash_returns_empty(self):
        assert _normalize_text("--") == ""

    def test_normal_text(self):
        assert _normalize_text("  hello  ") == "hello"


# ---------------------------------------------------------------------------
# _parse_event_keywords
# ---------------------------------------------------------------------------

class TestParseEventKeywords:
    def test_comma_separated(self):
        assert _parse_event_keywords("push,click") == ["push", "click"]

    def test_semicolon_separated(self):
        assert _parse_event_keywords("push;click") == ["push", "click"]

    def test_newline_separated(self):
        assert _parse_event_keywords("push\nclick") == ["push", "click"]

    def test_deduplication(self):
        assert _parse_event_keywords("push,push,click") == ["push", "click"]

    def test_empty_string_returns_empty(self):
        assert _parse_event_keywords("") == []

    def test_whitespace_only_returns_empty(self):
        assert _parse_event_keywords("   ") == []

    def test_uppercase_lowercased(self):
        result = _parse_event_keywords("PUSH,Click")
        assert result == ["push", "click"]


# ---------------------------------------------------------------------------
# _parse_visit_range
# ---------------------------------------------------------------------------

class TestParseVisitRange:
    def test_compact_format(self):
        result = _parse_visit_range("20260305-20260307")
        assert result is not None
        start, end = result
        assert str(start) == "2026-03-05"
        assert str(end) == "2026-03-07"

    def test_hyphenated_format(self):
        result = _parse_visit_range("2026-03-05-2026-03-07")
        assert result is not None
        start, end = result
        assert str(start) == "2026-03-05"
        assert str(end) == "2026-03-07"

    def test_reversed_range_auto_corrected(self):
        result = _parse_visit_range("20260307-20260305")
        assert result is not None
        start, end = result
        assert start <= end

    def test_single_day_range(self):
        result = _parse_visit_range("20260305-20260305")
        assert result is not None
        start, end = result
        assert start == end

    def test_empty_string_returns_none(self):
        assert _parse_visit_range("") is None

    def test_whitespace_returns_none(self):
        assert _parse_visit_range("   ") is None

    def test_invalid_string_returns_none(self):
        assert _parse_visit_range("not-a-date") is None

    def test_with_surrounding_spaces(self):
        result = _parse_visit_range("  20260305-20260307  ")
        assert result is not None


# ---------------------------------------------------------------------------
# _notify_group
# ---------------------------------------------------------------------------

class TestNotifyGroup:
    def test_trailing_alpha_numeric_stripped(self):
        assert _notify_group("notify_pdf05_homeA4") == "notify_pdf05_home"

    def test_trailing_numbers_stripped(self):
        assert _notify_group("notify_pdf05_unlock_07") == "notify_pdf05_unlock"

    def test_not_set_preserved(self):
        assert _notify_group("(not set)") == "(not set)"

    def test_empty_returns_unknown(self):
        assert _notify_group("") == "unknown"

    def test_plain_name_no_trailing_digits(self):
        result = _notify_group("notify_pdf05_fcm")
        assert result == "notify_pdf05_fcm"


# ---------------------------------------------------------------------------
# _notify_scene
# ---------------------------------------------------------------------------

class TestNotifyScene:
    def test_notify_prefix_three_parts(self):
        assert _notify_scene("notify_pdf05_unlock_07") == "unlock"

    def test_notify_prefix_two_parts(self):
        # notify_homeA4 -> parts = [notify, homeA4] -> candidate = homeA4 -> strip -> home
        assert _notify_scene("notify_homeA4") == "home"

    def test_not_set_preserved(self):
        assert _notify_scene("(not set)") == "(not set)"

    def test_empty_returns_unknown(self):
        assert _notify_scene("") == "unknown"

    def test_single_part(self):
        result = _notify_scene("fcm")
        assert result == "fcm"


# ---------------------------------------------------------------------------
# _extract_date_range
# ---------------------------------------------------------------------------

class TestExtractDateRange:
    def test_finds_range_in_first_10_rows(self):
        df = _df(
            ["项目名称", "版本"],
            ["PDF05", "1.0.0"],
            ["# 20260101-20260108"],
        )
        start, end = _extract_date_range(df)
        assert start == "20260101"
        assert end == "20260108"

    def test_raises_when_not_found(self):
        df = _df(["no date here"], ["still no date"])
        with pytest.raises(ValueError, match="未识别到导出日期区间"):
            _extract_date_range(df)

    def test_finds_inline_in_longer_cell(self):
        df = _df(["导出区间：20260301-20260307 数据"])
        start, end = _extract_date_range(df)
        assert start == "20260301"
        assert end == "20260307"


# ---------------------------------------------------------------------------
# _find_event_header_row
# ---------------------------------------------------------------------------

class TestFindEventHeaderRow:
    def test_finds_by_chinese_label(self):
        df = _df(
            ["ignored"],
            ["事件名称", "首次访问日期", "notifyname"],
        )
        assert _find_event_header_row(df) == 1

    def test_finds_by_english_label(self):
        df = _df(
            ["ignored"],
            ["EventName", "date", "notify"],
        )
        assert _find_event_header_row(df) == 1

    def test_raises_when_not_found(self):
        df = _df(["项目名称", "版本"])
        with pytest.raises(ValueError, match="未找到表头行"):
            _find_event_header_row(df)


# ---------------------------------------------------------------------------
# _build_header_index
# ---------------------------------------------------------------------------

class TestBuildHeaderIndex:
    def test_basic_lookup(self):
        df = _df(["项目名称", "版本号", "first open"])
        index = _build_header_index(df)
        assert index["项目名称"] == 0
        assert index["版本号"] == 1

    def test_normalized_lookup(self):
        df = _df(["First Open", "Active_Users"])
        index = _build_header_index(df)
        assert index.get("firstopen") is not None

    def test_empty_raises(self):
        df = pd.DataFrame()
        with pytest.raises(ValueError, match="文件为空"):
            _build_header_index(df)


# ---------------------------------------------------------------------------
# _extract_base_meta
# ---------------------------------------------------------------------------

class TestExtractBaseMeta:
    def test_reads_all_fields(self):
        df = _df(
            ["项目名称", "first open", "卸载用户数", "通知授权用户数",
             "DAY0发送用户数", "DAY0点击数", "DAY1发送用户数", "DAY1点击数", "版本号"],
            ["PDF05", "5000", "300", "4000", "2000", "800", "1800", "600", "2.0.0"],
        )
        meta = _extract_base_meta(df)
        assert meta["projectCode"] == "PDF05"
        assert meta["version"] == "2.0.0"
        assert meta["firstOpen"] == 5000
        assert meta["uninstallUsers"] == 300
        assert meta["authorizedUsers"] == 4000
        assert meta["d0PushUsersBase"] == 2000
        assert meta["d0ClickUsersBase"] == 800
        assert meta["d1PushUsersBase"] == 1800
        assert meta["d1ClickUsersBase"] == 600

    def test_raises_on_missing_version(self):
        df = _df(
            ["项目名称", "first open"],
            ["PDF05", "1000"],
        )
        with pytest.raises(ValueError, match="版本号缺失"):
            _extract_base_meta(df)


# ---------------------------------------------------------------------------
# read_table
# ---------------------------------------------------------------------------

class TestReadTable:
    def test_csv_utf8(self):
        csv_bytes = "a,b,c\n1,2,3\n".encode("utf-8")
        df = read_table("test.csv", csv_bytes)
        assert df.shape == (2, 3)
        assert df.iloc[0, 0] == "a"

    def test_csv_gbk_fallback(self):
        csv_bytes = "项目,版本\nPDF05,1.0\n".encode("gbk")
        df = read_table("test.csv", csv_bytes)
        assert "项目" in df.iloc[0].tolist()

    def test_tsv(self):
        tsv_bytes = "a\tb\tc\n1\t2\t3\n".encode("utf-8")
        df = read_table("test.tsv", tsv_bytes)
        assert df.shape == (2, 3)

    def test_unsupported_format_raises(self):
        with pytest.raises(ValueError, match="不支持的文件格式"):
            read_table("data.json", b"{}")

    def test_xlsx(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["项目名称", "版本"])
        ws.append(["PDF05", "1.0.0"])
        buf = io.BytesIO()
        wb.save(buf)
        df = read_table("test.xlsx", buf.getvalue())
        assert df.iloc[0, 0] == "项目名称"
        assert df.iloc[1, 1] == "1.0.0"


# ---------------------------------------------------------------------------
# parse_dataframe — smoke tests using minimal CSV
# ---------------------------------------------------------------------------

class TestParseDataframe:
    def _parse(self, csv_bytes=None, **kwargs):
        data = csv_bytes if csv_bytes is not None else _minimal_csv()
        df = read_table("test.csv", data)
        return parse_dataframe(df, **kwargs)

    def test_returns_four_sheets(self):
        result = self._parse()
        assert set(result.keys()) >= {"dailyByDay", "byContent", "byVersionSummary", "byNotifyCopyDay"}

    def test_daily_by_day_has_rows(self):
        result = self._parse()
        assert len(result["dailyByDay"]) > 0

    def test_by_version_summary_has_rows(self):
        result = self._parse()
        assert len(result["byVersionSummary"]) > 0

    def test_notify_copy_rows_have_correct_keys(self):
        result = self._parse()
        rows = result["byNotifyCopyDay"]
        assert len(rows) > 0
        required = {"nthDay", "scene", "notifyName", "pushUsers", "clickUsers", "userClickRate"}
        assert required.issubset(set(rows[0].keys()))

    def test_include_batch_adds_batch_field(self):
        result = self._parse(include_batch=True)
        daily = result["dailyByDay"]
        assert all("batch" in row for row in daily)

    def test_issues_list_returned(self):
        result = self._parse()
        assert "issues" in result
        assert isinstance(result["issues"], list)

    def test_custom_send_mapping_matched(self):
        result = self._parse(send_event_mapping="pDnotifyPush")
        assert len(result["dailyByDay"]) > 0

    def test_custom_mapping_miss_raises(self):
        with pytest.raises(ValueError, match="事件映射未命中"):
            self._parse(send_event_mapping="nonExistentEvent123")

    def test_d0_penetration_rate_uses_authorized_users(self):
        # authorizedUsers=800, d0PushUsersBase=600 → d0PenetrationRate = 600/800 = 0.75
        result = self._parse()
        version_row = result["byVersionSummary"][0]
        assert abs(version_row["d0PenetrationRate"] - 600 / 800) < 1e-9

    def test_d0_penetration_rate_zero_when_no_authorized_users(self):
        lines = [
            "项目名称,first open,卸载用户数,通知授权用户数,DAY0发送用户数,DAY0点击数,DAY1发送用户数,DAY1点击数,版本号",
            "PDF05,1000,100,0,600,200,500,150,1.0.0",
            "# 20260101-20260108",
            "",
            ",,第 N 天,0001,0001,0000,0000",
            "事件名称,首次访问日期,notifyname,活跃用户,事件数,活跃用户,事件数",
            "pDnotifyPush,20260107,notify_pdf05_home,80,100,60,80",
        ]
        csv_bytes = "\n".join(lines).encode("utf-8")
        df = read_table("test.csv", csv_bytes)
        result = parse_dataframe(df)
        version_row = result["byVersionSummary"][0]
        assert version_row["d0PenetrationRate"] == 0

    def test_visit_range_filter_compact(self):
        # date_end=20260108; rows: 20260107 (in), 20260103 (out of 20260106-20260108)
        lines = [
            "项目名称,first open,卸载用户数,通知授权用户数,DAY0发送用户数,DAY0点击数,DAY1发送用户数,DAY1点击数,版本号",
            "PDF05,1000,100,800,600,200,500,150,1.0.0",
            "# 20260101-20260108",
            "",
            ",,第 N 天,0001,0001,0000,0000",
            "事件名称,首次访问日期,notifyname,活跃用户,事件数,活跃用户,事件数",
            "pDnotifyPush,20260107,notify_home,80,100,60,80",
            "pDnotifyPush,20260103,notify_home,40,50,30,40",
        ]
        csv_bytes = "\n".join(lines).encode("utf-8")
        df = read_table("test.csv", csv_bytes)
        result_all = parse_dataframe(df)
        result_filtered = parse_dataframe(df, first_visit_range="20260106-20260108")
        # Without filter: two distinct days
        assert len(result_all["dailyByDay"]) == 2
        # With filter (20260103 excluded): one day remains
        assert len(result_filtered["dailyByDay"]) == 1
        assert result_filtered["dailyByDay"][0]["day"] == "20260107"

    def test_visit_range_filter_hyphenated(self):
        lines = [
            "项目名称,first open,卸载用户数,通知授权用户数,DAY0发送用户数,DAY0点击数,DAY1发送用户数,DAY1点击数,版本号",
            "PDF05,1000,100,800,600,200,500,150,1.0.0",
            "# 20260101-20260108",
            "",
            ",,第 N 天,0001,0001,0000,0000",
            "事件名称,首次访问日期,notifyname,活跃用户,事件数,活跃用户,事件数",
            "pDnotifyPush,20260107,notify_home,80,100,60,80",
            "pDnotifyPush,20260103,notify_home,40,50,30,40",
        ]
        csv_bytes = "\n".join(lines).encode("utf-8")
        df = read_table("test.csv", csv_bytes)
        result = parse_dataframe(df, first_visit_range="2026-01-06-2026-01-08")
        assert len(result["dailyByDay"]) == 1

    def test_visit_range_filter_reports_cleaned_count_in_issues(self):
        lines = [
            "项目名称,first open,卸载用户数,通知授权用户数,DAY0发送用户数,DAY0点击数,DAY1发送用户数,DAY1点击数,版本号",
            "PDF05,1000,100,800,600,200,500,150,1.0.0",
            "# 20260101-20260108",
            "",
            ",,第 N 天,0001,0001,0000,0000",
            "事件名称,首次访问日期,notifyname,活跃用户,事件数,活跃用户,事件数",
            "pDnotifyPush,20260107,notify_home,80,100,60,80",
            "pDnotifyPush,20260103,notify_home,40,50,30,40",
        ]
        csv_bytes = "\n".join(lines).encode("utf-8")
        df = read_table("test.csv", csv_bytes)
        result = parse_dataframe(df, first_visit_range="20260106-20260108")
        # Should have a cleaning notice in issues
        assert any("已清洗" in issue for issue in result["issues"])

    def test_visit_range_no_filter_when_empty(self):
        result = self._parse(first_visit_range="")
        assert len(result["dailyByDay"]) > 0

    def test_visit_range_all_rows_filtered_produces_empty_sheets(self):
        lines = [
            "项目名称,first open,卸载用户数,通知授权用户数,DAY0发送用户数,DAY0点击数,DAY1发送用户数,DAY1点击数,版本号",
            "PDF05,1000,100,800,600,200,500,150,1.0.0",
            "# 20260101-20260108",
            "",
            ",,第 N 天,0001,0001,0000,0000",
            "事件名称,首次访问日期,notifyname,活跃用户,事件数,活跃用户,事件数",
            "pDnotifyPush,20260107,notify_home,80,100,60,80",
        ]
        csv_bytes = "\n".join(lines).encode("utf-8")
        df = read_table("test.csv", csv_bytes)
        # Range that excludes 20260107
        result = parse_dataframe(df, first_visit_range="20260101-20260105")
        assert len(result["dailyByDay"]) == 0
        assert any("已清洗" in issue for issue in result["issues"])

    def test_derived_rates_between_zero_and_one(self):
        result = self._parse()
        for row in result["byVersionSummary"]:
            for key in ("authorizationRate", "uninstallRate", "d0PenetrationRate", "d0UserClickRate"):
                val = row.get(key, 0)
                assert 0.0 <= val <= 1.0, f"{key}={val} out of [0,1]"

    def test_zero_first_open_no_division_error(self):
        lines = [
            "项目名称,first open,卸载用户数,通知授权用户数,DAY0发送用户数,DAY0点击数,DAY1发送用户数,DAY1点击数,版本号",
            "PDF05,0,0,0,0,0,0,0,1.0.0",
            "# 20260101-20260108",
            "",
            ",,第 N 天,0001,0001,0000,0000",
            "事件名称,首次访问日期,notifyname,活跃用户,事件数,活跃用户,事件数",
            "pDnotifyPush,20260107,notify_test,10,15,8,10",
        ]
        csv_bytes = "\n".join(lines).encode("utf-8")
        result = self._parse(csv_bytes=csv_bytes)
        for row in result["byVersionSummary"]:
            assert row["authorizationRate"] == 0
            assert row["d0PenetrationRate"] == 0

    def test_missing_date_range_raises(self):
        lines = [
            "项目名称,first open,卸载用户数,通知授权用户数,DAY0发送用户数,DAY0点击数,DAY1发送用户数,DAY1点击数,版本号",
            "PDF05,1000,100,800,600,200,500,150,1.0.0",
            "# no date here",
            "",
            ",,第 N 天,0001,0001,0000,0000",
            "事件名称,首次访问日期,notifyname,活跃用户,事件数,活跃用户,事件数",
        ]
        csv_bytes = "\n".join(lines).encode("utf-8")
        df = read_table("test.csv", csv_bytes)
        with pytest.raises(ValueError, match="未识别到导出日期区间"):
            parse_dataframe(df)

    def test_missing_version_raises(self):
        lines = [
            "项目名称,first open",
            "PDF05,1000",
        ]
        csv_bytes = "\n".join(lines).encode("utf-8")
        df = read_table("test.csv", csv_bytes)
        with pytest.raises(ValueError, match="版本号缺失"):
            parse_dataframe(df)

    def test_not_set_notify_excluded_from_content(self):
        lines = [
            "项目名称,first open,卸载用户数,通知授权用户数,DAY0发送用户数,DAY0点击数,DAY1发送用户数,DAY1点击数,版本号",
            "PDF05,1000,100,800,600,200,500,150,1.0.0",
            "# 20260101-20260108",
            "",
            ",,第 N 天,0001,0001,0000,0000",
            "事件名称,首次访问日期,notifyname,活跃用户,事件数,活跃用户,事件数",
            "pDnotifyPush,20260107,(not set),80,100,60,80",
        ]
        csv_bytes = "\n".join(lines).encode("utf-8")
        df = read_table("test.csv", csv_bytes)
        result = parse_dataframe(df)
        content_keys = [r.get("content") for r in result["byContent"]]
        assert "(not set)" not in content_keys

    def test_multiple_rows_accumulate(self):
        # date_end=20260108, event_date=20260107 → delta_days=1, max_n=1
        # d0_n = max_n - delta_days = 0  → reads n=0 columns (indices 5 and 6)
        # Row layout: col3=n1_active, col4=n1_events, col5=n0_active, col6=n0_events
        # Row1 d0_events = col6 = 80; Row2 d0_events = col6 = 40  → total = 120
        lines = [
            "项目名称,first open,卸载用户数,通知授权用户数,DAY0发送用户数,DAY0点击数,DAY1发送用户数,DAY1点击数,版本号",
            "PDF05,1000,100,800,600,200,500,150,1.0.0",
            "# 20260101-20260108",
            "",
            ",,第 N 天,0001,0001,0000,0000",
            "事件名称,首次访问日期,notifyname,活跃用户,事件数,活跃用户,事件数",
            "pDnotifyPush,20260107,notify_home,80,100,60,80",
            "pDnotifyPush,20260107,notify_unlock,40,50,30,40",
        ]
        csv_bytes = "\n".join(lines).encode("utf-8")
        df = read_table("test.csv", csv_bytes)
        result = parse_dataframe(df)
        version_row = result["byVersionSummary"][0]
        # Both rows: d0 reads n=0 column (event count = 80 and 40) → total 120
        assert version_row["d0PushEvents"] == 120
        # d1 reads n=1 column (event count = 100 and 50) → total 150
        assert version_row["d1PushEvents"] == 150
