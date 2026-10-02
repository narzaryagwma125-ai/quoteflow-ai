const API_BASE = "/api";

export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function asList<T>(value: unknown, fallback: T[] = []): T[] {
  if (Array.isArray(value)) {
    return value as T[];
  }
  if (isRecord(value) && Array.isArray(value.items)) {
    return value.items as T[];
  }
  return fallback;
}

export function asNumber(value: unknown, fallback = 0): number {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function errorMessageFromBody(body: unknown): string | null {
  if (typeof body === "string") {
    return body.length > 0 ? body : null;
  }
  if (body === null || typeof body !== "object") {
    return null;
  }
  const record = body as Record<string, unknown>;

  const detail = record.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (typeof first === "string") {
      return first;
    }
    if (first !== null && typeof first === "object") {
      const msg = (first as Record<string, unknown>).msg;
      if (typeof msg === "string") {
        return msg;
      }
    }
  }

  const errors = record.errors;
  if (Array.isArray(errors) && errors.length > 0) {
    const first = errors[0];
    if (typeof first === "string") {
      return first;
    }
    if (first !== null && typeof first === "object") {
      const msg =
        (first as Record<string, unknown>).message ??
        (first as Record<string, unknown>).msg;
      if (typeof msg === "string") {
        return msg;
      }
    }
  }

  if (typeof record.message === "string" && record.message.length > 0) {
    return record.message;
  }
  return null;
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "same-origin",
  });

  const contentType = res.headers.get("content-type") || "";
  if (!res.ok) {
    let message = "Something went wrong. Please try again.";
    if (contentType.includes("application/json")) {
      try {
        message = errorMessageFromBody(await res.json()) ?? message;
      } catch {
        // Non-JSON or unparseable body; keep the default message.
      }
    }
    if (res.status === 401 && message === "Something went wrong. Please try again.") {
      message = "Authentication required.";
    }
    if (res.status >= 500) {
      message = "The server hit an unexpected error. Please try again in a moment.";
    }
    throw new ApiError(res.status, message);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export async function apiBlob(path: string, options: RequestInit = {}): Promise<Blob> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: options.headers as Record<string, string>,
    credentials: "same-origin",
  });
  if (!res.ok) {
    let message = "Download failed.";
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      try {
        message = errorMessageFromBody(await res.json()) ?? message;
      } catch {
        // Non-JSON or unparseable body; keep the default message.
      }
    }
    throw new ApiError(res.status, message);
  }
  return res.blob();
}

export { ApiError };
export function asQuoteId(value: unknown): number {
  const v = value as Record<string, unknown>;
  if (isRecord(v)) {
    if (isRecord(v.quote) && typeof v.quote.id === "number") return v.quote.id;
    if (typeof v.id === "number") return v.id;
  }
  throw new Error("Save failed: malformed quote response.");
}