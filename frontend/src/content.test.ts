import { describe, expect, it } from "vitest";

import {
  buildOutline,
  groupBlocks,
  navDomId,
  splitCalloutText,
  splitPageChrome,
  splitSections,
  withHeadingAnchors,
  type Block,
} from "./document";

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

describe("callout grid grouping", () => {
  it("wraps two or more consecutive callouts", () => {
    const groups = groupBlocks([
      { type: "heading_2", rich_text: [{ text: "Почему" }] },
      { type: "callout", icon: "🏠", rich_text: [{ text: "жизнь" }] },
      { type: "callout", icon: "☀", rich_text: [{ text: "климат" }] },
      { type: "paragraph", rich_text: [{ text: "дальше" }] },
    ]);
    expect(groups).toHaveLength(3);
    expect(groups[1]).toMatchObject({ kind: "callout_grid" });
    if (groups[1]?.kind === "callout_grid") expect(groups[1].items).toHaveLength(2);
  });

  it("keeps a single callout as an ordinary block", () => {
    const groups = groupBlocks([{ type: "callout", rich_text: [{ text: "один" }] }]);
    expect(groups).toEqual([{ kind: "block", block: { type: "callout", rich_text: [{ text: "один" }] } }]);
  });
});

describe("page chrome and sections", () => {
  it("lifts a leading image and short lede", () => {
    const chrome = splitPageChrome([
      { type: "image", image_id: "cover" },
      { type: "paragraph", rich_text: [{ text: "Солнечный город на востоке Бразилии" }] },
      { type: "heading_2", rich_text: [{ text: "Климат" }] },
    ]);
    expect(chrome.hero?.image_id).toBe("cover");
    expect(chrome.lede).toMatch(/Солнечный/);
    expect(chrome.rest).toHaveLength(1);
  });

  it("splits heading_2 groups into sections", () => {
    const sections = splitSections(
      groupBlocks([
        { type: "paragraph", rich_text: [{ text: "intro" }] },
        { type: "heading_2", rich_text: [{ text: "План" }] },
        { type: "numbered_list_item", rich_text: [{ text: "шаг" }] },
      ]),
    );
    expect(sections).toHaveLength(2);
    expect(sections[1]?.heading?.type).toBe("heading_2");
  });

  it("splits bold lead-in from callout body", () => {
    expect(
      splitCalloutText([
        { text: "больницы", annotations: { bold: true } },
        { text: " современная медицина" },
      ]),
    ).toEqual({ title: "больницы", body: "современная медицина" });
  });
});
