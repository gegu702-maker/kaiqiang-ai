import { NextResponse } from "next/server";

import {
  PREVIEW_DEBUG_ROUTE_DISABLED_DETAIL,
  previewDebugRoutesDisabled,
} from "../../../../lib/previewDebugRoutes";

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
  if (previewDebugRoutesDisabled()) {
    return NextResponse.json(
      { detail: PREVIEW_DEBUG_ROUTE_DISABLED_DETAIL },
      { status: 409 },
    );
  }

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "请求格式错误，请提交 JSON。" }, { status: 400 });
  }

  try {
    const response = await fetch(`${API_URL}/api/debug/liveportrait-test`, {
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
      // Keep raw backend body.
    }
    if (!response.ok) {
      const detail =
        typeof data === "object" && data !== null && "detail" in data
          ? stringifyDetail((data as { detail?: unknown }).detail)
          : stringifyDetail(data);
      return NextResponse.json({ detail: detail || "动态数字人生成失败，请检查 LivePortrait API 配置。" }, { status: response.status });
    }
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { detail: `网络错误：${error instanceof Error ? error.message : stringifyDetail(error)}` },
      { status: 502 },
    );
  }
}
