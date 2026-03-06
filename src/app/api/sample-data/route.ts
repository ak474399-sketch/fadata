import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

const SAMPLE_PASSWORD = "wangfengshuai";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const password = url.searchParams.get("password") ?? "";
  if (password !== SAMPLE_PASSWORD) {
    return NextResponse.json({ message: "示例文件密码错误。" }, { status: 401 });
  }

  try {
    const filePath = path.join(process.cwd(), "DATA1.csv");
    const content = await fs.readFile(filePath);
    return new NextResponse(content, {
      status: 200,
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="DATA1.csv"'
      }
    });
  } catch {
    return NextResponse.json({ message: "示例文件不存在。" }, { status: 404 });
  }
}
