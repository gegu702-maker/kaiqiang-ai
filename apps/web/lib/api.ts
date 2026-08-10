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

// This module is used by browser components. Do not put SERVER_API_URL before
// NEXT_PUBLIC_API_URL here: non-public variables are not reliably inlined in
// client bundles and can silently make Preview fall back to Production.
const CLIENT_API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === "production" ? "https://api.kaiqiang.ai" : "http://localhost:8000");
const API_URL = typeof window === "undefined" ? process.env.SERVER_API_URL || CLIENT_API_URL : CLIENT_API_URL;

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
    let structured: StructuredApiError | null = null;
    try {
      const payload = JSON.parse(body) as { detail?: unknown; error?: unknown; message?: unknown };
      structured = structuredApiError(payload.detail ?? payload.error ?? payload);
      message = stringifyDetail(payload.detail ?? payload.error ?? payload.message);
    } catch {
      // Fall through to the raw response body below.
    }
    if (structured && (structured.code || structured.stage || structured.request_id || structured.retryable !== undefined)) {
      throw new Error(formatStructuredApiError(structured, response.status, response.statusText));
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

type StructuredApiError = {
  code?: unknown;
  stage?: unknown;
  message?: unknown;
  request_id?: unknown;
  retryable?: unknown;
};

function structuredApiError(value: unknown): StructuredApiError | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as StructuredApiError;
}

function formatStructuredApiError(detail: StructuredApiError, status: number, statusText: string): string {
  const code = typeof detail.code === "string" ? detail.code : "api_http_error";
  const stage = typeof detail.stage === "string" ? detail.stage : "unknown";
  const message = typeof detail.message === "string" ? detail.message : "API 请求失败。";
  const requestId = typeof detail.request_id === "string" ? detail.request_id : "unavailable";
  const retryable = detail.retryable === true ? "true" : detail.retryable === false ? "false" : "unknown";
  return [
    message,
    `code: ${code}`,
    `stage: ${stage}`,
    `request_id: ${requestId}`,
    `retryable: ${retryable}`,
    `Status: ${status} ${statusText}`.trim(),
  ].join("\n");
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
    rewrite_length?: import("./types").ViralLengthMode;
    client_submission_id: string;
  },
  accessToken?: string,
): Promise<ViralAnalyzeResult> {
  const url = `${API_URL}/api/viral/analyze`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: accessToken
        ? { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` }
        : { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
  } catch {
    throw new Error(
      [
        "未取得 API HTTP 响应。",
        "code: cors_or_api_unreachable",
        "stage: analyzing",
        "request_id: unavailable",
        "retryable: true",
        `endpoint: ${url}`,
      ].join("\n"),
    );
  }
  return parseResponse<ViralAnalyzeResult>(response, { url, method: "POST" });
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
    rewrite_length?: import("./types").ViralLengthMode;
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

export type ViralJobCreateResult = {
  job_id: string;
  request_id: string;
  fingerprint: string;
  status_url: string;
  status: string;
  reused: boolean;
};

export type ViralJobStatus = {
  id: string;
  request_id: string;
  file_fingerprint: string;
  parameter_version: string;
  status: "uploading" | "pending" | "running" | "retry_wait" | "cancel_requested" | "succeeded" | "failed" | "cancelled";
  stage: string;
  progress: number;
  attempt: number;
  retryable: boolean;
  next_retry_at?: string | null;
  error_class?: string | null;
  error_code?: string | null;
  safe_error_message?: string | null;
  result?: ViralAnalyzeResult | null;
  quality?: Record<string, unknown> | null;
  provenance?: Record<string, unknown> | null;
  updated_at: string;
  completed_at?: string | null;
};

export class ViralJobApiUnavailableError extends Error {
  readonly code = "viral_async_jobs_disabled";

  constructor(public readonly originalMessage = "异步任务接口明确返回未启用。") {
    super(originalMessage);
    this.name = "ViralJobApiUnavailableError";
  }
}

export function getViralJobFeatureDisabledMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") return null;
  const root = payload as { code?: unknown; message?: unknown; detail?: unknown };
  const detail = root.detail && typeof root.detail === "object"
    ? root.detail as { code?: unknown; message?: unknown }
    : null;
  const code = detail?.code ?? root.code;
  if (code !== "viral_async_jobs_disabled") return null;
  const message = detail?.message ?? root.message;
  return typeof message === "string" && message.trim() ? message.trim() : "异步任务接口明确返回未启用。";
}

export async function createViralJob(
  formData: FormData,
  accessToken?: string,
  onProgress?: (progress: ViralUploadProgress) => void,
): Promise<ViralJobCreateResult> {
  const url = `${API_URL}/api/viral/jobs`;
  return new Promise<ViralJobCreateResult>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", url);
    request.timeout = 5 * 60 * 1000;
    if (accessToken) request.setRequestHeader("Authorization", `Bearer ${accessToken}`);
    request.upload.onprogress = (event) => {
      const total = event.lengthComputable ? event.total : 0;
      const percent = total ? Math.min(100, Math.round((event.loaded / total) * 100)) : 0;
      onProgress?.({ loaded: event.loaded, total, percent, stage: "uploading" });
    };
    request.upload.onload = () => onProgress?.({ loaded: 0, total: 0, percent: 100, stage: "processing" });
    request.onload = () => {
      let payload: unknown = null;
      try {
        payload = JSON.parse(request.responseText || "{}");
      } catch {
        payload = null;
      }
      if (request.status === 202 && payload) {
        resolve(payload as ViralJobCreateResult);
        return;
      }
      const featureDisabledMessage = getViralJobFeatureDisabledMessage(payload);
      if (featureDisabledMessage) {
        reject(new ViralJobApiUnavailableError(featureDisabledMessage));
        return;
      }
      const detail = payload && typeof payload === "object"
        ? stringifyDetail((payload as { detail?: unknown }).detail)
        : request.responseText;
      reject(new Error(detail || `异步任务创建失败（HTTP ${request.status || "unknown"}）。`));
    };
    request.onerror = () => reject(new Error("异步任务上传网络失败。"));
    request.ontimeout = () => reject(new Error("上传在5分钟内未完成。"));
    request.onabort = () => reject(new Error("上传已中断。"));
    request.send(formData);
  });
}

export async function getViralJob(jobId: string, accessToken?: string): Promise<ViralJobStatus> {
  const response = await fetch(`${API_URL}/api/viral/jobs/${encodeURIComponent(jobId)}`, {
    headers: authHeaders(accessToken),
    cache: "no-store",
  });
  return parseResponse<ViralJobStatus>(response);
}

export async function cancelViralJob(jobId: string, accessToken?: string): Promise<ViralJobStatus> {
  const response = await fetch(`${API_URL}/api/viral/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
    headers: authHeaders(accessToken),
    cache: "no-store",
  });
  return parseResponse<ViralJobStatus>(response);
}

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
      const code = request.status === 401 ? "api_unauthorized" : request.status === 413 ? "upload_too_large" : request.status >= 500 ? "api_server_error" : "api_http_error";
      reject(new Error(["上传请求被 API 拒绝", `code: ${code}`, "stage: uploading", `Status: ${request.status || "unknown"}`, `URL: ${url}`, detail ? `原因: ${detail}` : ""].filter(Boolean).join("\n")));
    };
    request.onerror = () =>
      reject(
        new Error(
          [
            "上传请求失败",
            "code: cors_or_api_unreachable",
            "stage: uploading",
            "request_id: unavailable（请求未取得API响应）",
            "retryable: true",
            `endpoint: ${url}`,
            `origin: ${window.location.origin}`,
            "浏览器自动 CORS 预检或 POST 网络链路未取得可读响应；请检查开发者工具 Network 中的 OPTIONS/POST 状态。",
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
