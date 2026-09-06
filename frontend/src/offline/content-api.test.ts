import { describe, expect, it } from "vitest";

import { classifySessionError } from "../session";
import { ApiError } from "./content-api";

describe("offline api errors", () => {
  it("maps unauthorized ApiError to expired session", () => {
    expect(classifySessionError(new ApiError(401, "unauthorized"))).toBe("expired");
  });
});
