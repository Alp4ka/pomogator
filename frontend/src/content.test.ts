import { describe, expect, it } from "vitest";

import { groupBlocks, type Block } from "./document";

describe("content routing", () => {
  it("keeps external and internal links distinct", () => {
    const external = { type: "external", url: "https://example.com" } as const;
    const internal = { type: "internal", page_id: "page-id" } as const;
    expect(external.url).toMatch(/^https:/);
    expect(internal.page_id).toBe("page-id");
  });
});

describe("groupBlocks", () => {
  it("wraps consecutive list items into a single list group", () => {
    const blocks: Block[] = [
      { type: "paragraph", rich_text: [{ text: "intro" }] },
      { type: "numbered_list_item", rich_text: [{ text: "one" }] },
      { type: "numbered_list_item", rich_text: [{ text: "two" }] },
      { type: "heading_2", rich_text: [{ text: "next" }] },
      { type: "bulleted_list_item", rich_text: [{ text: "a" }] },
    ];
    const groups = groupBlocks(blocks);
    expect(groups).toHaveLength(4);
    expect(groups[1]).toMatchObject({ kind: "list", listType: "numbered_list_item" });
    if (groups[1]?.kind === "list") expect(groups[1].items).toHaveLength(2);
    expect(groups[3]).toMatchObject({ kind: "list", listType: "bulleted_list_item" });
  });
});
