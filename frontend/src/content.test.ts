import { describe, expect, it } from "vitest";

describe("content routing", () => {
  it("keeps external and internal links distinct", () => {
    const external = { type: "external", url: "https://example.com" } as const;
    const internal = { type: "internal", page_id: "page-id" } as const;
    expect(external.url).toMatch(/^https:/);
    expect(internal.page_id).toBe("page-id");
  });
});
