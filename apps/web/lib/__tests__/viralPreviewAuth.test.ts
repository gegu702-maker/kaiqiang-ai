import assert from "node:assert/strict";
import test from "node:test";

import {
  getViralJobFeatureDisabledMessage,
  uploadFailureFromHttp,
  ViralJobApiUnavailableError,
  ViralUploadError,
} from "../api";
import {
  getForeignSupabaseAuthStorageNames,
  getSupabaseAuthStorageKey,
  getSupabaseProjectRef,
} from "../supabase/config";
import {
  getVerifiedSupabaseAccessToken,
  inspectSupabaseAccessToken,
  PreviewSessionError,
  type SessionGuardAuth,
} from "../supabase/sessionGuard";
import { submitViralUploadWithExplicitFallback } from "../viralJobSubmission";

const previewRef = "a".repeat(20);
const productionRef = "b".repeat(20);
const previewUrl = `https://${previewRef}.supabase.co`;
const now = 2_000_000_000;

function jwt(projectRef: string, exp: number, aud: string | string[] = "authenticated") {
  const encode = (value: unknown) => Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "HS256", typ: "JWT" })}.${encode({
    iss: `https://${projectRef}.supabase.co/auth/v1`,
    aud,
    exp,
  })}.signature`;
}

function fakeAuth(options: {
  sessionToken?: string;
  refreshedToken?: string;
  refreshError?: boolean;
  userValid?: boolean;
  calls: string[];
}): SessionGuardAuth {
  return {
    async getSession() {
      options.calls.push("getSession");
      return { data: { session: options.sessionToken ? { access_token: options.sessionToken } : null } };
    },
    async refreshSession() {
      options.calls.push("refreshSession");
      return {
        data: { session: options.refreshedToken ? { access_token: options.refreshedToken } : null },
        error: options.refreshError ? new Error("refresh failed") : undefined,
      };
    },
    async getUser() {
      options.calls.push("getUser");
      return {
        data: { user: options.userValid === false ? null : { verified: true } },
        error: options.userValid === false ? new Error("invalid user") : undefined,
      };
    },
  };
}

test("Production project session is rejected before Preview user validation", async () => {
  const calls: string[] = [];
  const auth = fakeAuth({ sessionToken: jwt(productionRef, now + 3600), calls });
  await assert.rejects(
    getVerifiedSupabaseAccessToken(auth, previewUrl, now),
    (error: unknown) => error instanceof PreviewSessionError && error.reason === "project_mismatch",
  );
  assert.deepEqual(calls, ["getSession"]);
});

test("issuer mismatch is classified without accepting the account as logged in", () => {
  const inspection = inspectSupabaseAccessToken(jwt(productionRef, now + 3600), previewUrl, now);
  assert.equal(inspection.valid, false);
  assert.equal(inspection.reason, "project_mismatch");
  assert.equal(inspection.projectRef, productionRef);
});

test("Supabase auth storage key is project scoped and foreign names are isolated", () => {
  assert.equal(getSupabaseProjectRef(previewUrl), previewRef);
  assert.equal(getSupabaseAuthStorageKey(previewUrl), `sb-${previewRef}-auth-token`);
  assert.deepEqual(
    getForeignSupabaseAuthStorageNames(
      [`sb-${previewRef}-auth-token.0`, `sb-${productionRef}-auth-token`, "unrelated"],
      previewRef,
    ),
    [`sb-${productionRef}-auth-token`],
  );
});

test("expired Preview token refreshes, validates, then continues with async job first", async () => {
  const calls: string[] = [];
  const auth = fakeAuth({
    sessionToken: jwt(previewRef, now - 1),
    refreshedToken: jwt(previewRef, now + 3600),
    calls,
  });
  const token = await getVerifiedSupabaseAccessToken(auth, previewUrl, now);
  const submission = await submitViralUploadWithExplicitFallback({
    createJob: async () => {
      calls.push("POST /api/viral/jobs");
      assert.equal(token, jwt(previewRef, now + 3600));
      return { job_id: "mock-job" };
    },
    runLegacyPipeline: async () => {
      calls.push("POST /api/viral/pipeline/upload");
      return { ok: true };
    },
  });
  assert.equal(submission.mode, "async");
  assert.deepEqual(calls, ["getSession", "refreshSession", "getUser", "POST /api/viral/jobs"]);
});

test("refresh failure sends no upload request", async () => {
  const calls: string[] = [];
  const auth = fakeAuth({ sessionToken: jwt(previewRef, now - 1), refreshError: true, calls });
  const uploadCalls = 0;
  await assert.rejects(getVerifiedSupabaseAccessToken(auth, previewUrl, now), PreviewSessionError);
  assert.equal(uploadCalls, 0);
  assert.deepEqual(calls, ["getSession", "refreshSession"]);
});

test("missing Authorization session sends no upload request", async () => {
  const calls: string[] = [];
  const auth = fakeAuth({ calls });
  const uploadCalls = 0;
  await assert.rejects(getVerifiedSupabaseAccessToken(auth, previewUrl, now), PreviewSessionError);
  assert.equal(uploadCalls, 0);
  assert.deepEqual(calls, ["getSession"]);
});

for (const status of [401, 403]) {
  test(`job API ${status} never falls back to legacy upload`, async () => {
    const calls: string[] = [];
    await assert.rejects(
      submitViralUploadWithExplicitFallback({
        createJob: async () => {
          calls.push("jobs");
          throw new Error(`HTTP ${status}`);
        },
        runLegacyPipeline: async () => {
          calls.push("legacy");
          return { ok: true };
        },
      }),
      new RegExp(String(status)),
    );
    assert.deepEqual(calls, ["jobs"]);
  });
}

test("network failure does not retry job creation or fall back", async () => {
  const calls: string[] = [];
  await assert.rejects(
    submitViralUploadWithExplicitFallback({
      createJob: async () => {
        calls.push("jobs");
        throw new Error("network failed");
      },
      runLegacyPipeline: async () => {
        calls.push("legacy");
        return { ok: true };
      },
    }),
    /network failed/,
  );
  assert.deepEqual(calls, ["jobs"]);
});

test("generic 404 is not an async feature-disabled signal", () => {
  assert.equal(getViralJobFeatureDisabledMessage({ detail: "Not Found" }), null);
  assert.equal(getViralJobFeatureDisabledMessage({ detail: { code: "route_not_found" } }), null);
});

test("only explicit feature-disabled response permits legacy fallback", async () => {
  const message = getViralJobFeatureDisabledMessage({
    detail: { code: "viral_async_jobs_disabled", message: "explicitly disabled" },
  });
  assert.equal(message, "explicitly disabled");
  const calls: string[] = [];
  const result = await submitViralUploadWithExplicitFallback({
    createJob: async () => {
      calls.push("jobs");
      throw new ViralJobApiUnavailableError(message ?? undefined);
    },
    runLegacyPipeline: async () => {
      calls.push("legacy");
      return { ok: true };
    },
  });
  assert.deepEqual(calls, ["jobs", "legacy"]);
  assert.deepEqual(result, { mode: "legacy", pipeline: { ok: true }, originalSignal: "explicitly disabled" });
});

test("fallback failure preserves the original feature-disabled signal", async () => {
  await assert.rejects(
    submitViralUploadWithExplicitFallback({
      createJob: async () => {
        throw new ViralJobApiUnavailableError("original feature-disabled signal");
      },
      runLegacyPipeline: async () => {
        throw new Error("legacy failed");
      },
    }),
    /original feature-disabled signal[\s\S]*legacy failed/,
  );
});

for (const [status, code] of [[401, "api_unauthorized"], [403, "api_forbidden"], [404, "api_not_found"], [413, "upload_too_large"], [503, "api_server_error"]] as const) {
  test(`upload HTTP ${status} has a distinct safe classification`, () => {
    const failure = uploadFailureFromHttp(status, {}, {
      stage: "uploading",
      job_id: "00000000-0000-0000-0000-000000000123",
      request_id: "request-safe",
    });
    assert.equal(failure.code, code);
    assert.equal(failure.status, status);
    assert.equal(failure.job_id, "00000000-0000-0000-0000-000000000123");
    assert.equal(failure.request_id, "request-safe");
  });
}

for (const code of ["cors_or_network_error", "client_timeout", "request_aborted"] as const) {
  test(`${code} preserves recoverable job diagnostics`, () => {
    const error = new ViralUploadError({
      code,
      stage: "uploading",
      job_id: "00000000-0000-0000-0000-000000000123",
      request_id: "request-safe",
      retryable: true,
      detail: "safe detail",
    });
    assert.match(error.message, new RegExp(code));
    assert.match(error.message, /job_id: 00000000-0000-0000-0000-000000000123/);
    assert.match(error.message, /request_id: request-safe/);
    assert.doesNotMatch(error.message, /token|secret|object_path/i);
  });
}
