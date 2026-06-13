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

function errorMessage(data: unknown): string {
  if (typeof data !== "object" || data === null) return stringifyDetail(data);
  const payload = data as { detail?: unknown; error?: unknown; message?: unknown };
  const detail = payload.detail;
  if (typeof detail === "object" && detail !== null) {
    const nested = detail as { message?: unknown; error?: unknown; detail?: unknown };
    return stringifyDetail(nested.message ?? nested.error ?? nested.detail ?? detail);
  }
  return stringifyDetail(payload.message ?? payload.error ?? detail);
}

export async function POST(request: Request) {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ success: false, error: "bad_request", message: "请求格式错误，请提交 JSON。" }, { status: 400 });
  }

  const authorization = request.headers.get("authorization");
  if (!authorization) {
    return NextResponse.json({ success: false, error: "unauthorized", message: "请先登录后再生成动态数字人。" }, { status: 401 });
  }

  try {
    const response = await fetch(`${API_URL}/api/avatar/dynamic-video`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: authorization,
      },
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
      return NextResponse.json(
        {
          success: false,
          error: "dynamic_video_failed",
          message: errorMessage(data) || "动态数字人生成失败，请稍后重试。",
          detail: data,
        },
        { status: response.status },
      );
    }
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        error: "network_error",
        message: `网络错误：${error instanceof Error ? error.message : stringifyDetail(error)}`,
      },
      { status: 502 },
    );
  }
}
