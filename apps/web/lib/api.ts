import type {
  AdminQuota,
  AdminStats,
  AdminUser,
  CheckoutResponse,
  Order,
  Payment,
  Plan,
  Subscription,
  UsageLog,
  UsageSummary,
  ViralAnalyzeResult,
  ViralPipelineResult,
  VideoLinkResolveResult,
  VideoTask,
  VoiceClone,
} from "@/lib/types";
import type { Locale } from "@/components/LanguageProvider";

const API_URL =
  process.env.SERVER_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === "production" ? "https://api.kaiqiang.ai" : "http://localhost:8000");

function readAdminApiKey(): string {
  const raw = process.env.SERVER_ADMIN_API_KEY ?? process.env.ADMIN_API_KEY ?? "";
  return raw.replace(/^ADMIN_API_KEY=/, "").trim();
}

function adminHeaders(): HeadersInit {
  const key = readAdminApiKey();
  if (!key) {
    throw new Error("Vercel 缺少 SERVER_ADMIN_API_KEY 或 ADMIN_API_KEY，请设置为与 Railway 后端完全相同的值。");
  }
  return { "x-admin-key": key };
}

function stringifyDetail(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

async function parseResponse<T>(response: Response, context?: { url?: string; method?: string }): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    let message = "";
    try {
      const payload = JSON.parse(body) as { detail?: unknown; error?: unknown; message?: unknown };
      message = stringifyDetail(payload.detail ?? payload.error ?? payload.message);
    } catch {
      // Fall through to the raw response body below.
    }
    const details = [
      `API request failed`,
      context?.method ? `Method: ${context.method}` : "",
      context?.url ? `URL: ${context.url}` : "",
      `Status: ${response.status} ${response.statusText}`,
      `Body: ${message || body || "(empty response body)"}`,
    ].filter(Boolean);
    throw new Error(details.join("\n"));
  }
  return response.json() as Promise<T>;
}

function authHeaders(accessToken?: string): HeadersInit {
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}

export async function createVideoTask(formData: FormData, accessToken?: string): Promise<VideoTask> {
  const url = `${API_URL}/api/tasks`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: authHeaders(accessToken),
      body: formData,
      cache: "no-store",
    });
  } catch (error) {
    throw new Error(
      [
        "API request failed",
        "Method: POST",
        `URL: ${url}`,
        `Message: ${error instanceof Error ? error.message : stringifyDetail(error)}`,
      ].join("\n"),
    );
  }
  const payload = await parseResponse<{ task: VideoTask }>(response, { url, method: "POST" });
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

export async function getUserPayments(accessToken?: string): Promise<Payment[]> {
  if (!accessToken) return [];
  const response = await fetch(`${API_URL}/api/billing/payments`, {
    headers: authHeaders(accessToken),
    cache: "no-store",
  });
  return parseResponse<Payment[]>(response);
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

export async function analyzeViralScript(
  payload: {
    source_url?: string;
    raw_script?: string;
    industry: string;
    language: Locale;
    rewrite_length?: "short" | "medium" | "full";
  },
  accessToken?: string,
): Promise<ViralAnalyzeResult> {
  const response = await fetch(`${API_URL}/api/viral/analyze`, {
    method: "POST",
    headers: accessToken
      ? { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }
      : { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  return parseResponse<ViralAnalyzeResult>(response, { url: `${API_URL}/api/viral/analyze`, method: "POST" });
}

export async function resolveVideoLink(sourceUrl: string, accessToken?: string): Promise<VideoLinkResolveResult> {
  const response = await fetch(`${API_URL}/api/viral/link/resolve`, {
    method: "POST",
    headers: accessToken
      ? { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }
      : { "Content-Type": "application/json" },
    body: JSON.stringify({ source_url: sourceUrl }),
    cache: "no-store",
  });
  return parseResponse<VideoLinkResolveResult>(response, { url: `${API_URL}/api/viral/link/resolve`, method: "POST" });
}

export async function checkVideoLink(sourceUrl: string, accessToken?: string): Promise<VideoLinkResolveResult> {
  const response = await fetch(`${API_URL}/api/viral/link/check`, {
    method: "POST",
    headers: accessToken
      ? { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }
      : { "Content-Type": "application/json" },
    body: JSON.stringify({ source_url: sourceUrl }),
    cache: "no-store",
  });
  return parseResponse<VideoLinkResolveResult>(response, { url: `${API_URL}/api/viral/link/check`, method: "POST" });
}

export async function runViralPipeline(
  payload: {
    source_url: string;
    raw_input?: string;
    industry?: string;
    language?: Locale;
    rewrite_length?: "short" | "medium" | "full";
  },
  accessToken?: string,
): Promise<ViralPipelineResult> {
  const response = await fetch(`${API_URL}/api/viral/pipeline/run`, {
    method: "POST",
    headers: accessToken
      ? { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }
      : { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  return parseResponse<ViralPipelineResult>(response, { url: `${API_URL}/api/viral/pipeline/run`, method: "POST" });
}

export type ViralUploadProgress = {
  loaded: number;
  total: number;
  percent: number;
  stage: "uploading" | "processing";
};

export async function runUploadedViralPipeline(
  formData: FormData,
  accessToken?: string,
  onProgress?: (progress: ViralUploadProgress) => void,
): Promise<ViralPipelineResult> {
  const url = `${API_URL}/api/viral/pipeline/upload`;
  return new Promise<ViralPipelineResult>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", url);
    request.timeout = 35 * 60 * 1000;
    if (accessToken) request.setRequestHeader("Authorization", `Bearer ${accessToken}`);
    // Do not set Content-Type: the browser must add the multipart boundary.
    request.upload.onprogress = (event) => {
      const total = event.lengthComputable ? event.total : 0;
      const percent = total ? Math.min(100, Math.round((event.loaded / total) * 100)) : 0;
      onProgress?.({ loaded: event.loaded, total, percent, stage: "uploading" });
    };
    request.upload.onload = () => onProgress?.({ loaded: 0, total: 0, percent: 100, stage: "processing" });
    request.onload = () => {
      let payload: unknown;
      try {
        payload = JSON.parse(request.responseText || "{}");
      } catch {
        payload = null;
      }
      if (request.status >= 200 && request.status < 300 && payload) {
        resolve(payload as ViralPipelineResult);
        return;
      }
      const detail = payload && typeof payload === "object" ? stringifyDetail((payload as { detail?: unknown; message?: unknown }).detail ?? (payload as { message?: unknown }).message) : request.responseText;
      reject(new Error(["上传请求被 API 拒绝", `Status: ${request.status || "unknown"}`, `URL: ${url}`, detail ? `原因: ${detail}` : ""].filter(Boolean).join("\n")));
    };
    request.onerror = () =>
      reject(
        new Error(
          [
            "上传请求失败",
            "code: network_error",
            "stage: uploading",
            "request_id: unavailable（请求未取得API响应）",
            "retryable: true",
            `endpoint: ${url}`,
            `origin: ${window.location.origin}`,
            "浏览器未收到可读取的 HTTP 响应，请检查 Preview API 地址与 CORS。",
          ].join("\n"),
        ),
      );
    request.ontimeout = () =>
      reject(
        new Error(
          [
            "上传请求超时",
            "code: client_timeout",
            "stage: processing",
            "request_id: unavailable（客户端未取得最终API响应）",
            "retryable: true",
            `endpoint: ${url}`,
            "客户端等待超过 35 分钟，上传或后端处理未完成。",
          ].join("\n"),
        ),
      );
    request.onabort = () =>
      reject(
        new Error(
          [
            "上传已中断",
            "code: request_aborted",
            "stage: uploading",
            "request_id: unavailable",
            "retryable: true",
            `endpoint: ${url}`,
            "请重新选择文件后重试。",
          ].join("\n"),
        ),
      );
    request.send(formData);
  });
}

export async function continueReviewedViralPipeline(
  payload: {
    review_context: Record<string, unknown>;
    review_token: string;
    confirmed_segments: Array<Record<string, unknown>>;
    source_url?: string;
    industry?: string;
    language?: Locale;
    rewrite_length?: "short" | "medium" | "full";
  },
  accessToken?: string,
): Promise<ViralPipelineResult> {
  const url = `${API_URL}/api/viral/pipeline/continue`;
  const response = await fetch(url, {
    method: "POST",
    headers: accessToken
      ? { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }
      : { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  return parseResponse<ViralPipelineResult>(response, { url, method: "POST" });
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
    headers: adminHeaders(),
    cache: "no-store",
  });
  return parseResponse<VideoTask[]>(response);
}

export async function getAdminUsers(): Promise<AdminUser[]> {
  const response = await fetch(`${API_URL}/api/admin/users`, {
    headers: adminHeaders(),
    cache: "no-store",
  });
  return parseResponse<AdminUser[]>(response);
}

export async function getAdminOrders(): Promise<Order[]> {
  const response = await fetch(`${API_URL}/api/admin/orders`, {
    headers: adminHeaders(),
    cache: "no-store",
  });
  return parseResponse<Order[]>(response);
}

export async function getUserSubscriptions(accessToken?: string): Promise<Subscription[]> {
  if (!accessToken) return [];
  const response = await fetch(`${API_URL}/api/billing/subscriptions`, {
    headers: authHeaders(accessToken),
    cache: "no-store",
  });
  return parseResponse<Subscription[]>(response);
}

export async function cancelUserSubscription(accessToken?: string): Promise<{ ok: boolean }> {
  const response = await fetch(`${API_URL}/api/billing/subscription/cancel`, {
    method: "POST",
    headers: authHeaders(accessToken),
    cache: "no-store",
  });
  return parseResponse<{ ok: boolean }>(response);
}

export async function getAdminSubscriptions(): Promise<Subscription[]> {
  const response = await fetch(`${API_URL}/api/admin/subscriptions`, {
    headers: adminHeaders(),
    cache: "no-store",
  });
  return parseResponse<Subscription[]>(response);
}

export async function getAdminPayments(): Promise<Payment[]> {
  const response = await fetch(`${API_URL}/api/admin/payments`, {
    headers: adminHeaders(),
    cache: "no-store",
  });
  return parseResponse<Payment[]>(response);
}

export async function getAdminPlans(): Promise<Plan[]> {
  const response = await fetch(`${API_URL}/api/admin/plans`, {
    headers: adminHeaders(),
    cache: "no-store",
  });
  return parseResponse<Plan[]>(response);
}

export async function updateAdminPlan(code: string, formData: FormData): Promise<Plan> {
  const response = await fetch(`${API_URL}/api/admin/plans/${code}`, {
    method: "PATCH",
    headers: adminHeaders(),
    body: formData,
    cache: "no-store",
  });
  return parseResponse<Plan>(response);
}

export async function getAdminQuotas(): Promise<AdminQuota[]> {
  const response = await fetch(`${API_URL}/api/admin/quotas`, {
    headers: adminHeaders(),
    cache: "no-store",
  });
  return parseResponse<AdminQuota[]>(response);
}

export async function updateAdminQuota(quotaId: string, formData: FormData): Promise<AdminQuota> {
  const response = await fetch(`${API_URL}/api/admin/quotas/${quotaId}`, {
    method: "PATCH",
    headers: adminHeaders(),
    body: formData,
    cache: "no-store",
  });
  return parseResponse<AdminQuota>(response);
}

export async function getAdminStats(): Promise<AdminStats> {
  const response = await fetch(`${API_URL}/api/admin/stats`, {
    headers: adminHeaders(),
    cache: "no-store",
  });
  return parseResponse<AdminStats>(response);
}

export async function updateAdminUser(userId: string, formData: FormData): Promise<AdminUser> {
  const response = await fetch(`${API_URL}/api/admin/users/${userId}`, {
    method: "PATCH",
    headers: adminHeaders(),
    body: formData,
    cache: "no-store",
  });
  return parseResponse<AdminUser>(response);
}

export async function markAdminOrderPaid(orderId: string, formData: FormData): Promise<{ ok: boolean; order: Order }> {
  const response = await fetch(`${API_URL}/api/admin/orders/${orderId}/mark-paid`, {
    method: "POST",
    headers: adminHeaders(),
    body: formData,
    cache: "no-store",
  });
  return parseResponse<{ ok: boolean; order: Order }>(response);
}

export async function retryAdminTask(taskId: string): Promise<VideoTask> {
  const response = await fetch(`${API_URL}/api/admin/tasks/${taskId}/retry`, {
    method: "POST",
    headers: adminHeaders(),
    cache: "no-store",
  });
  return parseResponse<VideoTask>(response);
}

export async function getAdminTask(taskId: string): Promise<VideoTask> {
  const response = await fetch(`${API_URL}/api/admin/tasks/${taskId}`, {
    headers: adminHeaders(),
    cache: "no-store",
  });
  return parseResponse<VideoTask>(response);
}

export async function updateAdminTask(taskId: string, formData: FormData): Promise<VideoTask> {
  const response = await fetch(`${API_URL}/api/admin/tasks/${taskId}`, {
    method: "PATCH",
    headers: adminHeaders(),
    body: formData,
    cache: "no-store",
  });
  return parseResponse<VideoTask>(response);
}

export async function cloneVoice(formData: FormData): Promise<{ audio_url: string; local_path: string; task: VideoTask | null }> {
  const response = await fetch(`${API_URL}/api/cosyvoice/clone`, {
    method: "POST",
    headers: adminHeaders(),
    body: formData,
    cache: "no-store",
  });
  return parseResponse<{ audio_url: string; local_path: string; task: VideoTask | null }>(response);
}

export async function getDebugConfig(): Promise<{
  avatar_motion_provider?: string;
  liveportrait_api_configured?: boolean;
  replicate_api_configured?: boolean;
}> {
  const response = await fetch(`${API_URL}/debug/config`, {
    cache: "no-store",
  });
  return parseResponse(response);
}

export function getPublicApiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}
