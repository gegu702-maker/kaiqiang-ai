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

export async function GET(request: Request) {
  const authorization = request.headers.get("authorization");
  if (!authorization) {
    return NextResponse.json({ detail: "请先登录后再查看生成记录。" }, { status: 401 });
  }

  try {
    const response = await fetch(`${API_URL}/api/avatar/tasks`, {
      headers: { Authorization: authorization },
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
      return NextResponse.json({ detail: detail || "生成记录读取失败。" }, { status: response.status });
    }
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { detail: `网络错误：${error instanceof Error ? error.message : stringifyDetail(error)}` },
      { status: 502 },
    );
  }
}
