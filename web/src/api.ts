import type { AuditRequest, AuditResponse } from "./types";

export async function fetchHealth(signal?: AbortSignal): Promise<boolean> {
  try {
    const r = await fetch("/health", { signal });
    return r.ok;
  } catch {
    return false;
  }
}

export async function runAudit(req: AuditRequest): Promise<AuditResponse> {
  const r = await fetch("/api/audit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) {
    throw new Error(`API 异常：HTTP ${r.status}`);
  }
  return (await r.json()) as AuditResponse;
}
