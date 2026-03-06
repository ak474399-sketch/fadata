import JSZip from "jszip";
import * as XLSX from "xlsx";
import { NextResponse } from "next/server";
import type { AnalysisRow, ParsedFileResult } from "@/types/report";

type DownloadPayload = {
  mode: "single" | "zip";
  selectedFileName?: string;
  results: ParsedFileResult[];
};

const BASE_COLUMNS: Array<{ key: keyof AnalysisRow; label: string; percent?: boolean }> = [
  { key: "firstOpen", label: "first open" },
  { key: "authorizedUsers", label: "通知授权用户数" },
  { key: "authorizationRate", label: "授权率", percent: true },
  { key: "uninstallUsers", label: "卸载用户数" },
  { key: "uninstallRate", label: "卸载率", percent: true },
  { key: "d0PushUsers", label: "DAY0发送用户数" },
  { key: "d0PushEvents", label: "DAY0发送事件数" },
  { key: "d0PenetrationRate", label: "DAY0通知渗透率", percent: true },
  { key: "d0AvgSentPerUser", label: "DAY0人均发送" },
  { key: "d0ClickUsers", label: "DAY0点击用户数" },
  { key: "d0ClickEvents", label: "DAY0点击事件数" },
  { key: "d0UserClickRate", label: "DAY0用户点击率", percent: true },
  { key: "d0EventClickRate", label: "DAY0事件点击率", percent: true },
  { key: "d0AvgClickPerUser", label: "DAY0人均点击数" },
  { key: "d1PushUsers", label: "DAY1发送用户数" },
  { key: "d1PushEvents", label: "DAY1发送事件数" },
  { key: "d1PenetrationRate", label: "DAY1通知渗透率", percent: true },
  { key: "d1AvgSentPerUser", label: "DAY1人均发送" },
  { key: "d1ClickUsers", label: "DAY1点击用户数" },
  { key: "d1ClickEvents", label: "DAY1点击事件数" },
  { key: "d1UserClickRate", label: "DAY1用户点击率", percent: true },
  { key: "d1EventClickRate", label: "DAY1事件点击率", percent: true },
  { key: "d1AvgClickPerUser", label: "DAY1人均点击数" }
];

function formatValue(value: number, percent?: boolean): string | number {
  if (percent) return `${(value * 100).toFixed(2)}%`;
  if (Number.isInteger(value)) return value;
  return Number(value.toFixed(4));
}

function toSheetRows(
  rows: AnalysisRow[],
  lead: Array<{ key: "batch" | "version" | "day" | "content"; label: string }>
): Array<Record<string, string | number>> {
  return rows.map((row) => {
    const out: Record<string, string | number> = {};
    for (const column of lead) {
      out[column.label] = (row[column.key] as string | undefined) ?? "";
    }
    for (const column of BASE_COLUMNS) {
      out[column.label] = formatValue(row[column.key] as number, column.percent);
    }
    return out;
  });
}

function toWorkbook(fileResult: ParsedFileResult): ArrayBuffer {
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

  const sheet1Rows = toSheetRows(fileResult.sheets.dailyByDay, dayLead);
  const sheet2Rows = toSheetRows(fileResult.sheets.byContent, contentLead);
  const sheet3Rows = toSheetRows(fileResult.sheets.byVersionSummary, versionLead);

  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(sheet1Rows), "分日 PUSH 分析");
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(sheet2Rows), "PUSH 内容分析");
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(sheet3Rows), "分版本汇总分析");
  return XLSX.write(workbook, { type: "array", bookType: "xlsx" });
}

function withXlsxName(fileName: string): string {
  const idx = fileName.lastIndexOf(".");
  const base = idx >= 0 ? fileName.slice(0, idx) : fileName;
  return `${base}_parsed.xlsx`;
}

export async function POST(request: Request) {
  const payload = (await request.json()) as DownloadPayload;
  if (!payload.results?.length) {
    return NextResponse.json({ message: "无可下载结果。" }, { status: 400 });
  }

  if (payload.mode === "single") {
    const target =
      payload.results.find((item) => item.fileName === payload.selectedFileName) ?? payload.results[0];
    const workbook = toWorkbook(target);
    return new NextResponse(workbook, {
      status: 200,
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": `attachment; filename="${withXlsxName(target.fileName)}"`
      }
    });
  }

  const zip = new JSZip();
  for (const fileResult of payload.results) {
    zip.file(withXlsxName(fileResult.fileName), toWorkbook(fileResult));
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
