import type { AdminUser, CheckoutResponse, Order, UsageLog, UsageSummary, VideoTask, VoiceClone } from "@/lib/types";

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

export async function deleteTask(taskId: string, accessToken?: string): Promise<{ ok: boolean }> {
  const response = await fetch(`${API_URL}/api/tasks/${taskId}`, {
    method: "DELETE",
    headers: authHeaders(accessToken),
    cache: "no-store",
  });
  return parseResponse<{ ok: boolean }>(response);
}

export async function retryTask(taskId: string, accessToken?: string): Promise<VideoTask> {
  const response = await fetch(`${API_URL}/api/tasks/${taskId}/retry`, {
    method: "POST",
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

export async function createPlaceholderOrder(formData: FormData, accessToken?: string): Promise<CheckoutResponse> {
  const response = await fetch(`${API_URL}/api/billing/orders`, {
    method: "POST",
    headers: authHeaders(accessToken),
    body: formData,
    cache: "no-store",
  });
  return parseResponse<CheckoutResponse>(response);
}

export async function getUserOrders(accessToken?: string): Promise<Order[]> {
  if (!accessToken) return [];
  const response = await fetch(`${API_URL}/api/billing/orders`, {
    headers: authHeaders(accessToken),
    cache: "no-store",
  });
  return parseResponse<Order[]>(response);
}

export async function getUserUsageLogs(accessToken?: string): Promise<UsageLog[]> {
  if (!accessToken) return [];
  const response = await fetch(`${API_URL}/api/billing/usage-logs`, {
    headers: authHeaders(accessToken),
    cache: "no-store",
  });
  return parseResponse<UsageLog[]>(response);
}

export async function getVoiceClones(accessToken?: string): Promise<VoiceClone[]> {
  if (!accessToken) return [];
  const response = await fetch(`${API_URL}/api/voice-clone/list`, {
    headers: authHeaders(accessToken),
    cache: "no-store",
  });
  return parseResponse<VoiceClone[]>(response);
}

export async function uploadVoiceClone(formData: FormData, accessToken?: string): Promise<VoiceClone> {
  const response = await fetch(`${API_URL}/api/voice-clone/upload`, {
    method: "POST",
    headers: authHeaders(accessToken),
    body: formData,
    cache: "no-store",
  });
  return parseResponse<VoiceClone>(response);
}

export async function createVoiceClone(formData: FormData, accessToken?: string): Promise<VoiceClone> {
  const response = await fetch(`${API_URL}/api/voice-clone/create`, {
    method: "POST",
    headers: authHeaders(accessToken),
    body: formData,
    cache: "no-store",
  });
  return parseResponse<VoiceClone>(response);
}

export async function deleteVoiceClone(voiceCloneId: string, accessToken?: string): Promise<{ ok: boolean }> {
  const response = await fetch(`${API_URL}/api/voice-clone/${voiceCloneId}`, {
    method: "DELETE",
    headers: authHeaders(accessToken),
    cache: "no-store",
  });
  return parseResponse<{ ok: boolean }>(response);
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

export async function getAdminUsers(): Promise<AdminUser[]> {
  const response = await fetch(`${API_URL}/api/admin/users`, {
    headers: {
      "x-admin-key": process.env.ADMIN_API_KEY ?? "",
    },
    cache: "no-store",
  });
  return parseResponse<AdminUser[]>(response);
}

export async function getAdminOrders(): Promise<Order[]> {
  const response = await fetch(`${API_URL}/api/admin/orders`, {
    headers: {
      "x-admin-key": process.env.ADMIN_API_KEY ?? "",
    },
    cache: "no-store",
  });
  return parseResponse<Order[]>(response);
}

export async function updateAdminUser(userId: string, formData: FormData): Promise<AdminUser> {
  const response = await fetch(`${API_URL}/api/admin/users/${userId}`, {
    method: "PATCH",
    headers: {
      "x-admin-key": process.env.ADMIN_API_KEY ?? "",
    },
    body: formData,
    cache: "no-store",
  });
  return parseResponse<AdminUser>(response);
}

export async function markAdminOrderPaid(orderId: string, formData: FormData): Promise<{ ok: boolean; order: Order }> {
  const response = await fetch(`${API_URL}/api/admin/orders/${orderId}/mark-paid`, {
    method: "POST",
    headers: {
      "x-admin-key": process.env.ADMIN_API_KEY ?? "",
    },
    body: formData,
    cache: "no-store",
  });
  return parseResponse<{ ok: boolean; order: Order }>(response);
}

export async function retryAdminTask(taskId: string): Promise<VideoTask> {
  const response = await fetch(`${API_URL}/api/admin/tasks/${taskId}/retry`, {
    method: "POST",
    headers: {
      "x-admin-key": process.env.ADMIN_API_KEY ?? "",
    },
    cache: "no-store",
  });
  return parseResponse<VideoTask>(response);
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
