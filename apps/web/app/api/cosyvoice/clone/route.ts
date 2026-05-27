import { NextResponse } from "next/server";

const API_URL = process.env.SERVER_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const COSYVOICE_PROXY_TIMEOUT_MS = 30 * 60 * 1000;

function adminApiKey(): string {
  return (process.env.ADMIN_API_KEY ?? "").replace(/^ADMIN_API_KEY=/, "").trim();
}

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request) {
  const endpoint = `${API_URL.replace(/\/$/, "")}/api/cosyvoice/clone`;

  try {
    const incoming = await request.formData();
    const debugKeys = Array.from(incoming.keys());
    const referenceAudio = incoming.get("reference_audio");
    const text = incoming.get("text")?.toString() || "";
    const taskId = incoming.get("task_id")?.toString() || "";
    const promptText = incoming.get("prompt_text")?.toString() || "";

    console.debug("[CosyVoiceCloneProxy] request", {
      endpoint,
      keys: debugKeys,
      hasReferenceAudio: referenceAudio instanceof File,
      textLength: text.length,
      taskId,
    });

    if (!referenceAudio || !(referenceAudio instanceof File)) {
      return NextResponse.json(
        {
          error: "missing reference_audio file",
          cosyvoice_status: "failed",
        },
        {
          status: 400,
          headers: {
            "Cache-Control": "no-store",
          },
        },
      );
    }

    const upstream = new FormData();
    upstream.append("reference_audio", referenceAudio);
    upstream.append("text", text);
    upstream.append("task_id", taskId);
    upstream.append("prompt_text", promptText);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), COSYVOICE_PROXY_TIMEOUT_MS);
    const res = await fetch(endpoint, {
      method: "POST",
      headers: {
        "x-admin-key": adminApiKey(),
      },
      body: upstream,
      cache: "no-store",
      signal: controller.signal,
    }).finally(() => clearTimeout(timeout));

    const rawText = await res.text();
    let payload: Record<string, unknown> = {};
    try {
      payload = rawText ? (JSON.parse(rawText) as Record<string, unknown>) : {};
    } catch {
      payload = { error: rawText || "CosyVoice clone response is not JSON." };
    }

    if (!res.ok) {
      console.error("[CosyVoiceCloneProxy] FastAPI failed", {
        endpoint,
        status: res.status,
        body: rawText,
        data: payload,
      });

      return NextResponse.json(
        {
          error: "FastAPI cosyvoice clone failed",
          detail: payload,
          cosyvoice_status: "failed",
        },
        {
          status: res.status,
          headers: {
            "Cache-Control": "no-store",
          },
        },
      );
    }

    const task = payload.task as { cosyvoice_status?: string } | null | undefined;
    const audioUrl = payload.audio_url || payload.cloned_voice_url;
    const clonedVoiceUrl = payload.cloned_voice_url || payload.audio_url;
    const cosyvoiceStatus = payload.cosyvoice_status || task?.cosyvoice_status || "completed";

    return NextResponse.json(
      {
        ...payload,
        audio_url: audioUrl,
        cloned_voice_url: clonedVoiceUrl,
        cosyvoice_status: cosyvoiceStatus,
      },
      {
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  } catch (error) {
    console.error("[CosyVoiceCloneProxy] route failed", {
      endpoint,
      error,
    });

    return NextResponse.json(
      {
        error: "Next.js proxy failed",
        detail: error instanceof Error ? `${error.name}: ${error.message}` : String(error),
        cosyvoice_status: "failed",
      },
      {
        status: 500,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }
}
