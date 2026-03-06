import { NextResponse } from "next/server";

function getBaseUrl(request: Request): string {
  const host = request.headers.get("host");
  const proto = request.headers.get("x-forwarded-proto") ?? "http";
  if (!host) return "http://localhost:3000";
  return `${proto}://${host}`;
}

export async function POST(request: Request) {
  try {
    const body = await request.formData();
    const baseUrl = getBaseUrl(request);
    const upstream = await fetch(`${baseUrl}/api/parse_python`, {
      method: "POST",
      body
    });
    const text = await upstream.text();
    let payload: unknown = null;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      payload = null;
    }

    if (!upstream.ok) {
      const upstreamErrorText =
        typeof payload === "object" && payload && "error" in payload
          ? String((payload as { error?: unknown }).error ?? "")
          : text.slice(0, 300);
      return NextResponse.json(
        {
          results: [],
          errors: [
            {
              fileName: "-",
              code: "E_UPSTREAM_HTTP",
              stage: "upstream",
              message: `解析服务异常（HTTP ${upstream.status}）。${upstreamErrorText || "请检查 Vercel Function 日志。"}`
            }
          ]
        },
        { status: 502 }
      );
    }

    if (payload && typeof payload === "object") {
      const safePayload = payload as {
        results?: unknown[];
        errors?: Array<{ fileName?: string; code?: string; message?: string; stage?: string }>;
      };
      const errors = Array.isArray(safePayload.errors)
        ? safePayload.errors.map((item) => ({
            fileName: item.fileName ?? "-",
            code: item.code ?? "E_UNKNOWN",
            message: item.message ?? "未知错误",
            stage:
              item.stage === "upload" ||
              item.stage === "read" ||
              item.stage === "parse" ||
              item.stage === "validate" ||
              item.stage === "upstream" ||
              item.stage === "network"
                ? item.stage
                : "parse"
          }))
        : [];
      return NextResponse.json({ results: safePayload.results ?? [], errors });
    }

    return NextResponse.json(
      {
        results: [],
        errors: [
          {
            fileName: "-",
            code: "E_UPSTREAM_NON_JSON",
            stage: "upstream",
            message: "解析服务返回了非 JSON 响应，请稍后重试。"
          }
        ]
      },
      { status: 502 }
    );
  } catch {
    return NextResponse.json(
      {
        results: [],
        errors: [
          {
            fileName: "-",
            code: "E_PARSE_UNAVAILABLE",
            stage: "network",
            message:
              "解析服务暂不可用。请在 Vercel 环境或支持 Python Function 的环境中调用 /api/parse。"
          }
        ]
      },
      { status: 500 }
    );
  }
}
