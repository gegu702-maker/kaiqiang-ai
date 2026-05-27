import { NextResponse } from "next/server";

const API_URL = process.env.SERVER_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function stringifyDetail(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export async function POST(request: Request) {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "请求格式错误，请提交 JSON。" }, { status: 400 });
  }

  const url = `${API_URL}/api/debug/tts-test`;
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    const body = await response.text();
    let data: unknown = body;
    try {
      data = body ? JSON.parse(body) : {};
    } catch {
      // Keep the raw backend body.
    }
    if (!response.ok) {
      const detail =
        typeof data === "object" && data !== null && "detail" in data
          ? stringifyDetail((data as { detail?: unknown }).detail)
          : stringifyDetail(data);
      return NextResponse.json({ detail: detail || "TTS 失败，请检查 provider 配置。" }, { status: response.status });
    }
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      {
        detail: `网络错误：${error instanceof Error ? error.message : stringifyDetail(error)}`,
      },
      { status: 502 },
    );
  }
}
