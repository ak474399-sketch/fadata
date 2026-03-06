import { NextResponse } from "next/server";

export async function POST(request: Request) {
  let reportType = "报告";
  try {
    const body = (await request.json()) as { reportType?: string };
    if (body.reportType) reportType = body.reportType;
  } catch {
    // ignore parse issue and keep default report type
  }
  return NextResponse.json({
    message: `${reportType} 已触发（占位）。下一阶段将接入 Gemini API。`
  });
}
