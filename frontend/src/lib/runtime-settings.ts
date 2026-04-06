const API_BASE_STORAGE_KEY = "meridian.apiBaseUrl";

function normaliseUrl(value: string | null | undefined): string {
  return (value || "").trim().replace(/\/$/, "");
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
  if (stored) return stored;
  return normaliseUrl(process.env.NEXT_PUBLIC_API_URL || "");
}

export function getApiTargetLabel(): string {
  const base = getRuntimeApiBaseUrl();
  return base || "same-origin /api proxy → localhost:8000";
}
