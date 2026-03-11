import JSZip from "jszip";
import * as XLSX from "xlsx";
import { NextResponse } from "next/server";
import { resolveMetricColumns, type MetricConfigState } from "@/lib/metric-config";
import type { AnalysisRow, NotifyCopyRow, ParsedFileResult } from "@/types/report";

type DownloadPayload = {
  mode: "single" | "zip";
  selectedFileName?: string;
  results: ParsedFileResult[];
  metricConfig?: MetricConfigState;
};

function formatValue(value: number, percent?: boolean): string | number {
  if (percent) return `${(value * 100).toFixed(2)}%`;
  if (Number.isInteger(value)) return value;
  return Number(value.toFixed(4));
}

function toSheetRows(
  rows: AnalysisRow[],
  lead: Array<{ key: "batch" | "version" | "day" | "content"; label: string }>,
  metricColumns: Array<{ id: string; label: string; percent?: boolean }>
): Array<Record<string, string | number>> {
  return rows.map((row) => {
    const out: Record<string, string | number> = {};
    for (const column of lead) {
      out[column.label] = (row[column.key] as string | undefined) ?? "";
    }
    for (const column of metricColumns) {
      out[column.label] = formatValue(Number(row[column.id as keyof AnalysisRow] ?? 0), column.percent);
    }
    return out;
  });
}

function toWorkbook(fileResult: ParsedFileResult, metricConfig?: MetricConfigState): ArrayBuffer {
  const workbook = XLSX.utils.book_new();
  const hasBatch = fileResult.sheets.dailyByDay.some((row) => Boolean(row.batch));
  const dayLead: Array<{ key: "batch" | "version" | "day" | "content"; label: string }> = [
    { key: "version", label: "版本号" },
    { key: "day", label: "天" }
  ];
  const contentLead: Array<{ key: "batch" | "version" | "day" | "content"; label: string }> = [
    { key: "version", label: "版本号" },
    { key: "content", label: "内容" }
  ];
  const versionLead: Array<{ key: "batch" | "version" | "day" | "content"; label: string }> = [
    { key: "version", label: "版本号" }
  ];
  if (hasBatch) {
    dayLead.unshift({ key: "batch", label: "批次" });
    contentLead.unshift({ key: "batch", label: "批次" });
    versionLead.unshift({ key: "batch", label: "批次" });
  }

  const sheet1Rows = toSheetRows(
    fileResult.sheets.dailyByDay,
    dayLead,
    resolveMetricColumns("dailyByDay", metricConfig)
  );
  const sheet2Rows = toSheetRows(
    fileResult.sheets.byContent,
    contentLead,
    resolveMetricColumns("byContent", metricConfig)
  );
  const sheet3Rows = toSheetRows(
    fileResult.sheets.byVersionSummary,
    versionLead,
    resolveMetricColumns("byVersionSummary", metricConfig)
  );
  const notifyMetricColumns = resolveMetricColumns("byNotifyCopyDay", metricConfig);
  const sheet4Rows: Array<Record<string, string | number>> = (fileResult.sheets.byNotifyCopyDay ?? []).map(
    (row: NotifyCopyRow) => {
      const out: Record<string, string | number> = {};
      if (hasBatch) out["批次"] = row.batch ?? row.dateRange;
      out["第N天"] = row.nthDay;
      out["日期"] = row.dateRange;
      out["项目代号"] = row.projectCode;
      out["版本"] = row.version;
      out["通知场景"] = row.scene;
      out["通知命名"] = row.notifyName;
      for (const column of notifyMetricColumns) {
        out[column.label] = formatValue(Number(row[column.id as keyof NotifyCopyRow] ?? 0), column.percent);
      }
      return out;
    }
  );

  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(sheet1Rows), "分日 PUSH 分析");
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(sheet2Rows), "PUSH 内容分析");
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(sheet3Rows), "分版本汇总分析");
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(sheet4Rows), "通知文案分天分析");
  return XLSX.write(workbook, { type: "array", bookType: "xlsx" });
}

function withXlsxName(fileName: string): string {
  const idx = fileName.lastIndexOf(".");
  const base = idx >= 0 ? fileName.slice(0, idx) : fileName;
  return `${base}_parsed.xlsx`;
}

function toAsciiFallbackName(fileName: string): string {
  const sanitized = fileName.replace(/[^\x20-\x7E]/g, "_").replace(/["\\]/g, "_");
  return sanitized || "parsed_result.xlsx";
}

function buildAttachmentHeader(fileName: string): string {
  const asciiFallback = toAsciiFallbackName(fileName);
  const encoded = encodeURIComponent(fileName);
  return `attachment; filename="${asciiFallback}"; filename*=UTF-8''${encoded}`;
}

export async function POST(request: Request) {
  const payload = (await request.json()) as DownloadPayload;
  if (!payload.results?.length) {
    return NextResponse.json({ message: "无可下载结果。" }, { status: 400 });
  }

  if (payload.mode === "single") {
    const target =
      payload.results.find((item) => item.fileName === payload.selectedFileName) ?? payload.results[0];
    const workbook = toWorkbook(target, payload.metricConfig);
    return new NextResponse(workbook, {
      status: 200,
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": buildAttachmentHeader(withXlsxName(target.fileName))
      }
    });
  }

  const zip = new JSZip();
  for (const fileResult of payload.results) {
    zip.file(withXlsxName(fileResult.fileName), toWorkbook(fileResult, payload.metricConfig));
  }
  const content = await zip.generateAsync({ type: "arraybuffer" });
  return new NextResponse(content, {
    status: 200,
    headers: {
      "Content-Type": "application/zip",
      "Content-Disposition": 'attachment; filename="parsed_results.zip"'
    }
  });
}
