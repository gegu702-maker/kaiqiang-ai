import type { UsageSummary, VideoTask } from "@/lib/types";

const API_URL = process.env.SERVER_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    let message = "";
    try {
      const payload = JSON.parse(body) as { detail?: string };
      message = payload.detail ?? "";
    } catch {
      // Fall through to the raw response body below.
    }
    throw new Error(message || body || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function authHeaders(accessToken?: string): HeadersInit {
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}

export async function createVideoTask(formData: FormData, accessToken?: string): Promise<VideoTask> {
  const response = await fetch(`${API_URL}/api/tasks`, {
    method: "POST",
    headers: authHeaders(accessToken),
    body: formData,
    cache: "no-store",
  });
  const payload = await parseResponse<{ task: VideoTask }>(response);
  return payload.task;
}

export async function getUserTasks(accessToken?: string): Promise<VideoTask[]> {
  if (!accessToken) return [];
  const response = await fetch(`${API_URL}/api/tasks`, {
    headers: authHeaders(accessToken),
    cache: "no-store",
  });
  return parseResponse<VideoTask[]>(response);
}

export async function getTask(taskId: string, accessToken?: string): Promise<VideoTask> {
  const response = await fetch(`${API_URL}/api/tasks/${taskId}`, {
    headers: authHeaders(accessToken),
    cache: "no-store",
  });
  return parseResponse<VideoTask>(response);
}

export async function getUsageSummary(accessToken?: string): Promise<UsageSummary | null> {
  if (!accessToken) return null;
  const response = await fetch(`${API_URL}/api/billing/usage`, {
    headers: authHeaders(accessToken),
    cache: "no-store",
  });
  return parseResponse<UsageSummary>(response);
}

export async function createPlaceholderOrder(formData: FormData, accessToken?: string): Promise<{ message: string }> {
  const response = await fetch(`${API_URL}/api/billing/orders`, {
    method: "POST",
    headers: authHeaders(accessToken),
    body: formData,
    cache: "no-store",
  });
  return parseResponse<{ message: string }>(response);
}

export async function getAdminTasks(): Promise<VideoTask[]> {
  const response = await fetch(`${API_URL}/api/admin/tasks`, {
    headers: {
      "x-admin-key": process.env.ADMIN_API_KEY ?? "",
    },
    cache: "no-store",
  });
  return parseResponse<VideoTask[]>(response);
}

export async function getAdminTask(taskId: string): Promise<VideoTask> {
  const response = await fetch(`${API_URL}/api/admin/tasks/${taskId}`, {
    headers: {
      "x-admin-key": process.env.ADMIN_API_KEY ?? "",
    },
    cache: "no-store",
  });
  return parseResponse<VideoTask>(response);
}

export async function updateAdminTask(taskId: string, formData: FormData): Promise<VideoTask> {
  const response = await fetch(`${API_URL}/api/admin/tasks/${taskId}`, {
    method: "PATCH",
    headers: {
      "x-admin-key": process.env.ADMIN_API_KEY ?? "",
    },
    body: formData,
    cache: "no-store",
  });
  return parseResponse<VideoTask>(response);
}

export async function cloneVoice(formData: FormData): Promise<{ audio_url: string; local_path: string; task: VideoTask | null }> {
  const response = await fetch(`${API_URL}/api/cosyvoice/clone`, {
    method: "POST",
    headers: {
      "x-admin-key": process.env.ADMIN_API_KEY ?? "",
    },
    body: formData,
    cache: "no-store",
  });
  return parseResponse<{ audio_url: string; local_path: string; task: VideoTask | null }>(response);
}
