import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json({
    message: "报告生成功能已预留接口，下一阶段将接入 Gemini API。"
  });
}
