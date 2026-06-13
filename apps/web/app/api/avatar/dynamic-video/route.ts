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

function normalizeErrorDetail(value: unknown): { detail: string; extra?: Record<string, unknown> } {
  if (typeof value === "object" && value !== null) {
    const detail = value as Record<string, unknown>;
    if (detail.error === "missing_template_video" || detail.missing_template_video === true) {
      return {
        detail: typeof detail.message === "string" ? detail.message : "当前数字人模板暂未配置动态视频素材，请选择其他模板。",
        extra: {
          error: "missing_template_video",
          avatar_template_id: detail.avatar_template_id,
          missing_template_video: true,
        },
      };
    }
  }
  return { detail: stringifyDetail(value) };
}

export async function POST(request: Request) {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ detail: "请求格式错误，请提交 JSON。" }, { status: 400 });
  }

  try {
    const response = await fetch(`${API_URL}/api/avatar/dynamic-video`, {
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
      const rawDetail =
        typeof data === "object" && data !== null && "detail" in data
          ? (data as { detail?: unknown }).detail
          : data;
      const { detail, extra } = normalizeErrorDetail(rawDetail);
      return NextResponse.json({ detail: detail || "动态数字人生成失败，请检查动态数字人配置。", ...extra }, { status: response.status });
    }
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { detail: `网络错误：${error instanceof Error ? error.message : stringifyDetail(error)}` },
      { status: 502 },
    );
  }
}
