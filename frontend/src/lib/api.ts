/**
 * Typed API client for the maestronexus backend.
 *
 * Foundation for every feature module: import `apiFetch` and build typed
 * helpers in `lib/<module>.ts`. Handles the JSON error envelope (docs/13),
 * bearer-token auth, and transparent access-token refresh on 401.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const API_V1 = `${API_BASE_URL}/api/v1`;

const ACCESS_KEY = "mn.access_token";
const REFRESH_KEY = "mn.refresh_token";

// ── Token storage (browser localStorage; SSR-safe no-ops) ───────────────────

export const tokenStore = {
  get access(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(ACCESS_KEY);
  },
  get refresh(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(REFRESH_KEY);
  },
  set(access: string, refresh: string) {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(ACCESS_KEY, access);
    window.localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
  },
};

// ── Error envelope ───────────────────────────────────────────────────────────

export type ApiErrorBody = {
  error?: { code?: string; message?: string; request_id?: string };
};

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

// ── Core fetch ───────────────────────────────────────────────────────────────

export type ApiFetchOptions = Omit<RequestInit, "body"> & {
  /** JSON-serializable body; sets Content-Type automatically. */
  json?: unknown;
  /** Skip the Authorization header (e.g. for login). */
  anonymous?: boolean;
  /** Internal: prevents infinite refresh recursion. */
  _retried?: boolean;
};

async function rawFetch<T>(path: string, opts: ApiFetchOptions = {}): Promise<T> {
  const { json, anonymous, _retried, headers, ...rest } = opts;
  const finalHeaders = new Headers(headers);

  if (json !== undefined) {
    finalHeaders.set("Content-Type", "application/json");
  }
  if (!anonymous) {
    const token = tokenStore.access;
    if (token) finalHeaders.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${API_V1}${path}`, {
    ...rest,
    headers: finalHeaders,
    body: json !== undefined ? JSON.stringify(json) : (rest as RequestInit).body,
    cache: "no-store",
  });

  // Transparent refresh on first 401.
  if (res.status === 401 && !anonymous && !_retried && tokenStore.refresh) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      return rawFetch<T>(path, { ...opts, _retried: true });
    }
    tokenStore.clear();
  }

  if (!res.ok) {
    let code = "error";
    let message = res.statusText;
    try {
      const body = (await res.json()) as ApiErrorBody;
      if (body.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, message);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function apiFetch<T>(path: string, opts?: ApiFetchOptions): Promise<T> {
  return rawFetch<T>(path, opts);
}

// ── Auth endpoints ───────────────────────────────────────────────────────────

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

export type CurrentUser = {
  id: string;
  tenant_id: string;
  email: string;
  display_name: string;
  is_superuser: boolean;
  roles: string[];
  permissions: string[];
};

export async function login(
  username: string,
  password: string,
  tenantSlug?: string,
): Promise<TokenResponse> {
  const tokens = await apiFetch<TokenResponse>("/iam/auth/login", {
    method: "POST",
    anonymous: true,
    json: { username, password, tenant_slug: tenantSlug ?? null },
  });
  tokenStore.set(tokens.access_token, tokens.refresh_token);
  return tokens;
}

async function tryRefresh(): Promise<boolean> {
  const refresh_token = tokenStore.refresh;
  if (!refresh_token) return false;
  try {
    const tokens = await rawFetch<TokenResponse>("/iam/auth/refresh", {
      method: "POST",
      anonymous: true,
      json: { refresh_token },
    });
    tokenStore.set(tokens.access_token, tokens.refresh_token);
    return true;
  } catch {
    return false;
  }
}

export function getMe(): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/iam/auth/me");
}

export function logout() {
  tokenStore.clear();
}

// ── Health (dev shell) ───────────────────────────────────────────────────────

export type HealthCheck = { ok: boolean; detail: string };
export type ReadinessResponse = {
  status: "ready" | "degraded";
  checks: Record<string, HealthCheck>;
};

export async function fetchReadiness(): Promise<ReadinessResponse> {
  const res = await fetch(`${API_BASE_URL}/health/ready`, { cache: "no-store" });
  return (await res.json()) as ReadinessResponse;
}
