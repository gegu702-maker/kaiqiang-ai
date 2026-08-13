"use client";

import { useEffect, useState } from "react";

import { getPreviewReadiness, type PreviewReadiness } from "@/lib/api";

export default function PreviewReadinessPage() {
  const [result, setResult] = useState<PreviewReadiness | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getPreviewReadiness()
      .then((payload) => {
        if (active) setResult(payload);
      })
      .catch((readinessError: unknown) => {
        if (active) setError(readinessError instanceof Error ? readinessError.message : "Preview readiness unavailable");
      });
    return () => { active = false; };
  }, []);

  const state = result?.status === "ok" ? "ready" : error ? "unavailable" : "checking";
  return (
    <main className="mx-auto min-h-screen max-w-3xl px-6 py-16 text-slate-100">
      <h1 className="text-2xl font-semibold">P2.37 Preview readiness</h1>
      <p className="mt-3 text-sm text-slate-400">Safe browser-to-API CORS diagnostic. No user session or business data is used.</p>
      <section data-preview-readiness={state} className="mt-8 rounded-lg border border-white/10 bg-white/5 p-5">
        <p className="font-mono text-sm">status: {state}</p>
        {result ? (
          <dl className="mt-4 grid gap-2 text-sm">
            <div>deployment: {result.deployment.id}</div>
            <div>commit: {result.deployment.commit_sha}</div>
            <div>async_jobs_enabled: {String(result.async_jobs_enabled)}</div>
          </dl>
        ) : null}
        {error ? <pre className="mt-4 whitespace-pre-wrap text-xs text-rose-200">{error}</pre> : null}
      </section>
    </main>
  );
}
