import type { VideoTask } from "@/lib/types";

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

export async function createVideoTask(formData: FormData): Promise<VideoTask> {
  const response = await fetch(`${API_URL}/api/tasks`, {
    method: "POST",
    body: formData,
    cache: "no-store",
  });
  const payload = await parseResponse<{ task: VideoTask }>(response);
  return payload.task;
}

export async function getUserTasks(email: string): Promise<VideoTask[]> {
  if (!email) return [];
  const params = new URLSearchParams({ user_email: email });
  const response = await fetch(`${API_URL}/api/tasks?${params}`, {
    cache: "no-store",
  });
  return parseResponse<VideoTask[]>(response);
}

export async function getTask(taskId: string): Promise<VideoTask> {
  const response = await fetch(`${API_URL}/api/tasks/${taskId}`, {
    cache: "no-store",
  });
  return parseResponse<VideoTask>(response);
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
