/** Telegram Mini App session helpers — content only with live signed initData. */

export type SessionFailure = "missing" | "mismatch" | "expired";

let boundInitData: string | null = null;

export function isUsableInitData(value: string | null | undefined): boolean {
  if (!value) return false;
  return value.includes("hash=") && value.includes("user=") && value.includes("auth_date=");
}

export function readTelegramInitData(): string {
  return window.Telegram?.WebApp?.initData?.trim() ?? "";
}

export function hasTelegramSession(): boolean {
  return isUsableInitData(readTelegramInitData());
}

export function resolveBoundInitData(bound: string | null, current: string): string {
  if (!isUsableInitData(current)) {
    throw new Error("no-session");
  }
  if (bound === null) return current;
  if (bound !== current) {
    throw new Error("session-mismatch");
  }
  return current;
}

/** Pin the first valid initData for this page lifetime; reject swaps. */
export function requireBoundInitData(): string {
  try {
    const current = resolveBoundInitData(boundInitData, readTelegramInitData());
    boundInitData = current;
    return current;
  } catch (error) {
    if (error instanceof Error && error.message === "no-session") {
      boundInitData = null;
    }
    throw error;
  }
}

export function clearBoundSession(): void {
  boundInitData = null;
}

export function authHeaders(): HeadersInit {
  return { Authorization: `tma ${requireBoundInitData()}` };
}

export function classifySessionError(reason: unknown): SessionFailure | null {
  if (reason && typeof reason === "object" && "status" in reason) {
    const status = (reason as { status?: number }).status;
    if (status === 401) return "expired";
  }
  if (!(reason instanceof Error)) return null;
  if (reason.message === "no-session") return "missing";
  if (reason.message === "session-mismatch") return "mismatch";
  if (reason.message === "unauthorized") return "expired";
  return null;
}
