import { describe, expect, it } from "vitest";
import {
  classifySessionError,
  isUsableInitData,
  resolveBoundInitData,
} from "./session";

describe("isUsableInitData", () => {
  it("rejects empty and partial values", () => {
    expect(isUsableInitData("")).toBe(false);
    expect(isUsableInitData("user=%7B%7D")).toBe(false);
    expect(isUsableInitData("hash=abc&user=%7B%7D")).toBe(false);
  });

  it("accepts Telegram-shaped initData", () => {
    expect(isUsableInitData("auth_date=1&hash=abc&user=%7B%22id%22%3A1%7D")).toBe(true);
  });
});

describe("resolveBoundInitData", () => {
  it("binds the first session and rejects a different one", () => {
    const first = "auth_date=1&hash=aaa&user=%7B%22id%22%3A1%7D";
    const second = "auth_date=2&hash=bbb&user=%7B%22id%22%3A2%7D";
    expect(resolveBoundInitData(null, first)).toBe(first);
    expect(resolveBoundInitData(first, first)).toBe(first);
    expect(() => resolveBoundInitData(first, second)).toThrow("session-mismatch");
  });

  it("rejects missing Telegram session", () => {
    expect(() => resolveBoundInitData(null, "")).toThrow("no-session");
  });
});

describe("classifySessionError", () => {
  it("maps known session failures", () => {
    expect(classifySessionError(new Error("unauthorized"))).toBe("expired");
    expect(classifySessionError(new Error("no-session"))).toBe("missing");
    expect(classifySessionError(new Error("session-mismatch"))).toBe("mismatch");
    expect(classifySessionError(new Error("http:500"))).toBeNull();
  });
});
