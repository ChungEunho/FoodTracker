"use client";

import { createClient } from "@/lib/supabase/client";
import type { RateLimitInfo } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Error classes
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class RateLimitError extends ApiError {
  constructor(
    public readonly remaining: number,
    public readonly resets_at_utc: string,
    message: string,
  ) {
    super(429, message);
    this.name = "RateLimitError";
  }
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

async function getAuthHeader(): Promise<Record<string, string>> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.access_token) return {};
  return { Authorization: `Bearer ${session.access_token}` };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    // Token expired — clear local session and redirect to login.
    const supabase = createClient();
    await supabase.auth.signOut();
    window.location.href = "/login";
    throw new ApiError(401, "세션이 만료됐습니다. 다시 로그인해주세요.");
  }

  if (res.status === 429) {
    const body = await res.json().catch(() => ({} as Partial<RateLimitInfo & { error: string }>));
    throw new RateLimitError(
      (body as { remaining?: number }).remaining ?? 0,
      (body as { resets_at_utc?: string }).resets_at_utc ?? "",
      (body as { error?: string }).error ?? "일일 요청 한도를 초과했습니다.",
    );
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({} as { error?: string }));
    throw new ApiError(
      res.status,
      (body as { error?: string }).error || res.statusText || `서버 오류 (${res.status})`,
      body,
    );
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * JSON request helper — supports GET, POST with JSON body, DELETE, etc.
 * All calls are directed exclusively to NEXT_PUBLIC_API_URL (our backend).
 * No third-party services are called from here.
 */
export async function apiRequest<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const authHeader = await getAuthHeader();

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...authHeader,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  return handleResponse<T>(res);
}

/**
 * Multipart form-data upload helper (file upload).
 * Do NOT set Content-Type manually — the browser must set it with the
 * multipart boundary.
 */
export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const authHeader = await getAuthHeader();

  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: authHeader, // no Content-Type — browser adds it with boundary
    body: formData,
  });

  return handleResponse<T>(res);
}
