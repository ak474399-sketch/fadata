"""
Integration tests for api/parse_python.py (Flask endpoints)

Run:  cd api && pytest tests/test_app.py -v
"""
import io
import json
import sys
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parent.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from parse_python import app as flask_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def _minimal_csv(
    project="PDF05",
    version="1.0.0",
    date_range="20260101-20260108",
    first_open=1000,
    include_click=True,
) -> bytes:
    rows = [
        f"项目名称,first open,卸载用户数,通知授权用户数,DAY0发送用户数,DAY0点击数,DAY1发送用户数,DAY1点击数,版本号",
        f"{project},{first_open},100,800,600,200,500,150,{version}",
        f"# {date_range}",
        "",
        ",,第 N 天,0001,0001,0000,0000",
        "事件名称,首次访问日期,notifyname,活跃用户,事件数,活跃用户,事件数",
        "pDnotifyPush,20260107,notify_pdf05_home,80,100,60,80",
    ]
    if include_click:
        rows.append("pDnotifyClick,20260107,notify_pdf05_home,20,25,15,18")
    return "\n".join(rows).encode("utf-8")


def _post_files(client, files_data: list, extra_form: dict = None):
    """
    Helper to POST multipart form.
    files_data: list of (field_name, file_bytes, filename)
    extra_form: additional form fields
    Note: multiple files with the same field name must be passed as a list.
    """
    # Group by field name so Flask test client receives them as a list.
    grouped: dict = {}
    for field, content, fname in files_data:
        grouped.setdefault(field, []).append((io.BytesIO(content), fname))

    data: dict = {}
    for field, file_list in grouped.items():
        data[field] = file_list if len(file_list) > 1 else file_list[0]

    if extra_form:
        data.update(extra_form)
    return client.post(
        "/api/parse_python",
        data=data,
        content_type="multipart/form-data",
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_single_file_returns_200(self, client):
        resp = _post_files(client, [("files", _minimal_csv(), "test.csv")])
        assert resp.status_code == 200

    def test_response_has_results_and_errors_keys(self, client):
        resp = _post_files(client, [("files", _minimal_csv(), "test.csv")])
        body = resp.get_json()
        assert "results" in body
        assert "errors" in body

    def test_result_has_filename(self, client):
        resp = _post_files(client, [("files", _minimal_csv(), "myfile.csv")])
        body = resp.get_json()
        assert body["results"][0]["fileName"] == "myfile.csv"

    def test_result_has_four_sheets(self, client):
        resp = _post_files(client, [("files", _minimal_csv(), "test.csv")])
        sheets = resp.get_json()["results"][0]["sheets"]
        assert set(sheets.keys()) == {"dailyByDay", "byContent", "byVersionSummary", "byNotifyCopyDay"}

    def test_no_critical_errors_on_valid_file(self, client):
        resp = _post_files(client, [("files", _minimal_csv(), "test.csv")])
        body = resp.get_json()
        critical = [e for e in body["errors"] if not e["code"].startswith("W_")]
        assert critical == []

    def test_root_endpoint_also_works(self, client):
        data = {"files": (io.BytesIO(_minimal_csv()), "test.csv")}
        resp = client.post("/", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200

    def test_daily_by_day_rows_have_metrics(self, client):
        resp = _post_files(client, [("files", _minimal_csv(), "test.csv")])
        daily = resp.get_json()["results"][0]["sheets"]["dailyByDay"]
        assert len(daily) > 0
        row = daily[0]
        assert "d0PushUsers" in row
        assert "d0UserClickRate" in row

    def test_rates_are_numeric(self, client):
        resp = _post_files(client, [("files", _minimal_csv(), "test.csv")])
        row = resp.get_json()["results"][0]["sheets"]["byVersionSummary"][0]
        assert isinstance(row["authorizationRate"], (int, float))
        assert isinstance(row["d0PenetrationRate"], (int, float))


# ---------------------------------------------------------------------------
# Merge mode
# ---------------------------------------------------------------------------

class TestMergeMode:
    def test_merge_mode_adds_merged_result(self, client):
        csv_a = _minimal_csv(version="1.0.0", date_range="20260101-20260108")
        csv_b = _minimal_csv(version="1.0.1", date_range="20260109-20260116")
        resp = _post_files(
            client,
            [("files", csv_a, "a.csv"), ("files", csv_b, "b.csv")],
            extra_form={"mergeMode": "true"},
        )
        assert resp.status_code == 200
        results = resp.get_json()["results"]
        file_names = [r["fileName"] for r in results]
        assert "并表分析" in file_names

    def test_merge_mode_single_file_no_merge_entry(self, client):
        resp = _post_files(
            client,
            [("files", _minimal_csv(), "only.csv")],
            extra_form={"mergeMode": "true"},
        )
        results = resp.get_json()["results"]
        file_names = [r["fileName"] for r in results]
        assert "并表分析" not in file_names

    def test_merge_result_has_all_sheets(self, client):
        csv_a = _minimal_csv(version="1.0.0", date_range="20260101-20260108")
        csv_b = _minimal_csv(version="1.0.1", date_range="20260109-20260116")
        resp = _post_files(
            client,
            [("files", csv_a, "a.csv"), ("files", csv_b, "b.csv")],
            extra_form={"mergeMode": "true"},
        )
        merged = next(r for r in resp.get_json()["results"] if r["fileName"] == "并表分析")
        assert set(merged["sheets"].keys()) == {"dailyByDay", "byContent", "byVersionSummary", "byNotifyCopyDay"}


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_no_files_returns_400(self, client):
        resp = client.post("/api/parse_python", data={}, content_type="multipart/form-data")
        assert resp.status_code == 400
        body = resp.get_json()
        assert any(e["code"] == "E_NO_FILES" for e in body["errors"])

    def test_invalid_format_returns_error_code(self, client):
        resp = _post_files(client, [("files", b"{}", "data.json")])
        body = resp.get_json()
        codes = [e["code"] for e in body["errors"]]
        assert "E_PARSE_FILE" in codes

    def test_missing_version_returns_schema_invalid(self, client):
        bad_csv = (
            "项目名称,first open\n"
            "PDF05,1000\n"
        ).encode("utf-8")
        resp = _post_files(client, [("files", bad_csv, "bad.csv")])
        body = resp.get_json()
        codes = [e["code"] for e in body["errors"]]
        assert "E_SCHEMA_INVALID" in codes

    def test_missing_date_range_returns_parse_error(self, client):
        # "未识别到导出日期区间" does not match the E_SCHEMA_INVALID patterns
        # (_classify_parse_error only maps "未识别到第 n 天" / "未找到表头行" / "版本号缺失")
        # so it falls through to the generic E_PARSE_FILE code.
        bad_csv = (
            "项目名称,first open,卸载用户数,通知授权用户数,DAY0发送用户数,DAY0点击数,DAY1发送用户数,DAY1点击数,版本号\n"
            "PDF05,1000,100,800,600,200,500,150,1.0.0\n"
            "# no date\n"
            "\n"
            ",,第 N 天,0001,0001,0000,0000\n"
            "事件名称,首次访问日期,notifyname,活跃用户,事件数,活跃用户,事件数\n"
        ).encode("utf-8")
        resp = _post_files(client, [("files", bad_csv, "nodate.csv")])
        body = resp.get_json()
        codes = [e["code"] for e in body["errors"]]
        assert "E_PARSE_FILE" in codes

    def test_missing_header_row_returns_schema_invalid(self, client):
        # "未找到表头行" does match E_SCHEMA_INVALID
        bad_csv = (
            "项目名称,first open,卸载用户数,通知授权用户数,DAY0发送用户数,DAY0点击数,DAY1发送用户数,DAY1点击数,版本号\n"
            "PDF05,1000,100,800,600,200,500,150,1.0.0\n"
            "# 20260101-20260108\n"
            "no event header here\n"
        ).encode("utf-8")
        resp = _post_files(client, [("files", bad_csv, "noheader.csv")])
        body = resp.get_json()
        codes = [e["code"] for e in body["errors"]]
        assert "E_SCHEMA_INVALID" in codes

    def test_bad_event_mapping_returns_event_mapping_miss(self, client):
        resp = _post_files(
            client,
            [("files", _minimal_csv(), "test.csv")],
            extra_form={"sendEventMapping": "nonExistentEvent999"},
        )
        body = resp.get_json()
        codes = [e["code"] for e in body["errors"]]
        assert "E_EVENT_MAPPING_MISS" in codes

    def test_valid_file_plus_invalid_file_partial_results(self, client):
        resp = _post_files(
            client,
            [
                ("files", _minimal_csv(), "good.csv"),
                ("files", b"completely,invalid\nno,version", "bad.csv"),
            ],
        )
        body = resp.get_json()
        # One result succeeds, one error recorded for the bad file
        assert len(body["results"]) == 1
        assert len(body["errors"]) >= 1
        assert body["results"][0]["fileName"] == "good.csv"

    def test_row_issues_returns_warning_code(self, client):
        csv_with_issues = (
            "项目名称,first open,卸载用户数,通知授权用户数,DAY0发送用户数,DAY0点击数,DAY1发送用户数,DAY1点击数,版本号\n"
            "PDF05,1000,100,800,600,200,500,150,1.0.0\n"
            "# 20260101-20260108\n"
            "\n"
            ",,第 N 天,0001,0001,0000,0000\n"
            "事件名称,首次访问日期,notifyname,活跃用户,事件数,活跃用户,事件数\n"
            "pDnotifyPush,BADDATE,notify_home,80,100,60,80\n"
        ).encode("utf-8")
        resp = _post_files(client, [("files", csv_with_issues, "issues.csv")])
        body = resp.get_json()
        codes = [e["code"] for e in body["errors"]]
        assert "W_ROW_ISSUES" in codes

    def test_error_objects_have_required_fields(self, client):
        resp = _post_files(client, [("files", b"", "empty.csv")])
        body = resp.get_json()
        for err in body["errors"]:
            assert "fileName" in err
            assert "code" in err
            assert "message" in err


# ---------------------------------------------------------------------------
# D0 penetration rate formula
# ---------------------------------------------------------------------------

class TestD0PenetrationRate:
    def test_uses_authorized_users_as_denominator(self, client):
        # authorizedUsers=800, d0PushUsersBase=600 → rate = 600/800 = 0.75
        resp = _post_files(client, [("files", _minimal_csv(), "test.csv")])
        version_row = resp.get_json()["results"][0]["sheets"]["byVersionSummary"][0]
        assert abs(version_row["d0PenetrationRate"] - 600 / 800) < 1e-9

    def test_zero_when_authorized_users_is_zero(self, client):
        csv = (
            "项目名称,first open,卸载用户数,通知授权用户数,DAY0发送用户数,DAY0点击数,DAY1发送用户数,DAY1点击数,版本号\n"
            "PDF05,1000,100,0,600,200,500,150,1.0.0\n"
            "# 20260101-20260108\n\n"
            ",,第 N 天,0001,0001,0000,0000\n"
            "事件名称,首次访问日期,notifyname,活跃用户,事件数,活跃用户,事件数\n"
            "pDnotifyPush,20260107,notify_home,80,100,60,80\n"
        ).encode("utf-8")
        resp = _post_files(client, [("files", csv, "test.csv")])
        version_row = resp.get_json()["results"][0]["sheets"]["byVersionSummary"][0]
        assert version_row["d0PenetrationRate"] == 0


# ---------------------------------------------------------------------------
# First visit date range filter
# ---------------------------------------------------------------------------

class TestFirstVisitDateRangeFilter:
    def _two_row_csv(self) -> bytes:
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
        return "\n".join(lines).encode("utf-8")

    def test_compact_format_filters_rows(self, client):
        resp = _post_files(
            client,
            [("files", self._two_row_csv(), "test.csv")],
            extra_form={"firstVisitDateRange": "20260106-20260108"},
        )
        daily = resp.get_json()["results"][0]["sheets"]["dailyByDay"]
        assert len(daily) == 1
        assert daily[0]["day"] == "20260107"

    def test_hyphenated_format_filters_rows(self, client):
        resp = _post_files(
            client,
            [("files", self._two_row_csv(), "test.csv")],
            extra_form={"firstVisitDateRange": "2026-01-06-2026-01-08"},
        )
        daily = resp.get_json()["results"][0]["sheets"]["dailyByDay"]
        assert len(daily) == 1

    def test_empty_range_does_not_filter(self, client):
        resp = _post_files(
            client,
            [("files", self._two_row_csv(), "test.csv")],
            extra_form={"firstVisitDateRange": ""},
        )
        daily = resp.get_json()["results"][0]["sheets"]["dailyByDay"]
        assert len(daily) == 2

    def test_cleaned_rows_reported_in_errors(self, client):
        resp = _post_files(
            client,
            [("files", self._two_row_csv(), "test.csv")],
            extra_form={"firstVisitDateRange": "20260106-20260108"},
        )
        body = resp.get_json()
        warnings = [e for e in body["errors"] if e["code"] == "W_ROW_ISSUES"]
        assert len(warnings) == 1
        assert "已清洗" in warnings[0]["message"]

    def test_all_rows_filtered_returns_empty_daily(self, client):
        resp = _post_files(
            client,
            [("files", self._two_row_csv(), "test.csv")],
            extra_form={"firstVisitDateRange": "20260101-20260102"},
        )
        daily = resp.get_json()["results"][0]["sheets"]["dailyByDay"]
        assert len(daily) == 0


# ---------------------------------------------------------------------------
# Custom event mapping
# ---------------------------------------------------------------------------

class TestCustomEventMapping:
    def test_custom_send_mapping_produces_results(self, client):
        resp = _post_files(
            client,
            [("files", _minimal_csv(), "test.csv")],
            extra_form={"sendEventMapping": "pDnotifyPush"},
        )
        assert resp.status_code == 200
        daily = resp.get_json()["results"][0]["sheets"]["dailyByDay"]
        assert len(daily) > 0

    def test_custom_click_mapping_produces_results(self, client):
        resp = _post_files(
            client,
            [("files", _minimal_csv(), "test.csv")],
            extra_form={"clickEventMapping": "pDnotifyClick"},
        )
        assert resp.status_code == 200

    def test_both_mappings_custom(self, client):
        resp = _post_files(
            client,
            [("files", _minimal_csv(), "test.csv")],
            extra_form={
                "sendEventMapping": "pDnotifyPush",
                "clickEventMapping": "pDnotifyClick",
            },
        )
        assert resp.status_code == 200
        body = resp.get_json()
        critical = [e for e in body["errors"] if not e["code"].startswith("W_")]
        assert critical == []
