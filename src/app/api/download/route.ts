import JSZip from "jszip";
import { NextResponse } from "next/server";
import type { ParsedFileResult, ParsedRow } from "@/types/report";

type DownloadPayload = {
  mode: "single" | "zip";
  selectedFileName?: string;
  results: ParsedFileResult[];
};

const HEADER = [
  "天",
  "通知内容",
  "D0 PUSH 发送数",
  "D0 点击数",
  "D0 点击率",
  "D1 发送数",
  "D1 点击数",
  "D1 点击率"
];

function toCsv(rows: ParsedRow[]): string {
  const lines = [HEADER.join(",")];
  for (const row of rows) {
    lines.push(
      [
        row.day,
        row.notificationContent,
        row.d0PushSent,
        row.d0Click,
        `${(row.d0ClickRate * 100).toFixed(2)}%`,
        row.d1PushSent,
        row.d1Click,
        `${(row.d1ClickRate * 100).toFixed(2)}%`
      ].join(",")
    );
  }
  return lines.join("\n");
}

function withCsvName(fileName: string): string {
  const idx = fileName.lastIndexOf(".");
  const base = idx >= 0 ? fileName.slice(0, idx) : fileName;
  return `${base}_parsed.csv`;
}

export async function POST(request: Request) {
  const payload = (await request.json()) as DownloadPayload;
  if (!payload.results?.length) {
    return NextResponse.json({ message: "无可下载结果。" }, { status: 400 });
  }

  if (payload.mode === "single") {
    const target =
      payload.results.find((item) => item.fileName === payload.selectedFileName) ?? payload.results[0];
    const csv = toCsv(target.rows);
    return new NextResponse(csv, {
      status: 200,
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": `attachment; filename="${withCsvName(target.fileName)}"`
      }
    });
  }

  const zip = new JSZip();
  for (const fileResult of payload.results) {
    zip.file(withCsvName(fileResult.fileName), toCsv(fileResult.rows));
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
