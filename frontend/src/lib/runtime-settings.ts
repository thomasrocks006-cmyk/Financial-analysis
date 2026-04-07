const API_BASE_STORAGE_KEY = "meridian.apiBaseUrl";

function normaliseUrl(value: string | null | undefined): string {
  return (value || "").trim().replace(/\/$/, "");
}

function isLoopbackHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "0.0.0.0";
}

function shouldBypassDirectLoopbackBase(value: string): boolean {
  if (typeof window === "undefined" || !value) return false;
  try {
    const candidate = new URL(value);
    return isLoopbackHost(candidate.hostname) && !isLoopbackHost(window.location.hostname);
  } catch {
    return false;
  }
}

export function getStoredApiBaseUrl(): string {
  if (typeof window === "undefined") return "";
  return normaliseUrl(window.localStorage.getItem(API_BASE_STORAGE_KEY));
}

export function setStoredApiBaseUrl(value: string): void {
  if (typeof window === "undefined") return;
  const normalised = normaliseUrl(value);
  if (!normalised) {
    window.localStorage.removeItem(API_BASE_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(API_BASE_STORAGE_KEY, normalised);
}

export function getRuntimeApiBaseUrl(): string {
  const stored = getStoredApiBaseUrl();
  if (stored && !shouldBypassDirectLoopbackBase(stored)) return stored;

  const envBase = normaliseUrl(process.env.NEXT_PUBLIC_API_URL || "");
  if (envBase && !shouldBypassDirectLoopbackBase(envBase)) return envBase;

  return "";
}

export function getApiTargetLabel(): string {
  const base = getRuntimeApiBaseUrl();
  return base || "same-origin /api proxy → localhost:8000";
}
