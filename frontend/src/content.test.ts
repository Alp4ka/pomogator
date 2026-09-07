import { describe, expect, it } from "vitest";

import { buildOutline, groupBlocks, navDomId, withHeadingAnchors, type Block } from "./document";

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

describe("page outline", () => {
  it("builds interactive heading anchors", () => {
    const blocks = withHeadingAnchors([
      { type: "paragraph", rich_text: [{ text: "intro" }] },
      { type: "heading_2", rich_text: [{ text: "Первый" }] },
      { type: "heading_3", rich_text: [{ text: "Вложенный" }] },
      { type: "heading_2", rich_text: [{ text: "  " }] },
    ]);
    expect(buildOutline(blocks)).toEqual([
      { id: "section-1", level: 2, title: "Первый" },
      { id: "section-2", level: 3, title: "Вложенный" },
    ]);
    expect(blocks[1]?.anchor_id).toBe("section-1");
    expect(blocks[2]?.anchor_id).toBe("section-2");
  });

  it("prefers nav_anchor ids for outline targets", () => {
    expect(navDomId("Docs")).toBe("nav-docs");
    expect(
      buildOutline([
        {
          type: "heading_2",
          rich_text: [{ text: "Документы" }],
          anchor_id: "section-1",
          nav_anchor: "Docs",
        },
      ]),
    ).toEqual([{ id: "nav-docs", level: 2, title: "Документы" }]);
  });
});

describe("list grouping without checklist special-case", () => {
  it("keeps box-prefixed bullets as ordinary list items", () => {
    const blocks: Block[] = [
      { type: "paragraph", rich_text: [{ text: "Сделайте это" }] },
      {
        type: "bulleted_list_item",
        rich_text: [{ text: "▢ Первый" }],
      },
      {
        type: "bulleted_list_item",
        rich_text: [{ text: "▢ Второй" }],
      },
      { type: "paragraph", rich_text: [{ text: "Дальше" }] },
    ];
    const groups = groupBlocks(blocks);
    expect(groups).toHaveLength(3);
    expect(groups[0]).toMatchObject({ kind: "block" });
    expect(groups[1]).toMatchObject({ kind: "list", listType: "bulleted_list_item" });
    if (groups[1]?.kind === "list") expect(groups[1].items).toHaveLength(2);
    expect(groups[2]).toMatchObject({ kind: "block" });
  });
});
