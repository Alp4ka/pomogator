import React from "react";

export type Link = { type: "external"; url: string } | { type: "internal"; page_id: string };
export type Rich = { text: string; annotations?: Record<string, boolean>; link?: Link };
export type Block = {
  type: string;
  rich_text?: Rich[];
  image_id?: string;
  caption?: string;
  checked?: boolean;
  language?: string;
  icon?: string;
};

export type RenderGroup =
  | { kind: "list"; listType: "bulleted_list_item" | "numbered_list_item"; items: Block[] }
  | { kind: "block"; block: Block };

export function groupBlocks(blocks: Block[]): RenderGroup[] {
  const groups: RenderGroup[] = [];
  let index = 0;
  while (index < blocks.length) {
    const block = blocks[index]!;
    if (block.type === "bulleted_list_item" || block.type === "numbered_list_item") {
      const listType = block.type;
      const items: Block[] = [];
      while (index < blocks.length && blocks[index]?.type === listType) {
        items.push(blocks[index]!);
        index += 1;
      }
      groups.push({ kind: "list", listType, items });
      continue;
    }
    groups.push({ kind: "block", block });
    index += 1;
  }
  return groups;
}

export function RichText({
  items = [],
  onInternal,
}: {
  items?: Rich[];
  onInternal: (id: string) => void;
}) {
  return (
    <>
      {items.map((item, index) => {
        let node: React.ReactNode = item.text;
        if (item.annotations?.code) node = <code>{node}</code>;
        if (item.annotations?.bold) node = <strong>{node}</strong>;
        if (item.annotations?.italic) node = <em>{node}</em>;
        if (item.annotations?.strikethrough) node = <s>{node}</s>;
        if (item.annotations?.underline) node = <u>{node}</u>;
        if (item.link?.type === "external") {
          node = (
            <a href={item.link.url} target="_blank" rel="noopener noreferrer">
              {node}
            </a>
          );
        }
        if (item.link?.type === "internal") {
          const pageId = item.link.page_id;
          node = (
            <button type="button" className="text-link" onClick={() => onInternal(pageId)}>
              {node}
            </button>
          );
        }
        return <React.Fragment key={index}>{node}</React.Fragment>;
      })}
    </>
  );
}

export function DocumentBody({
  blocks,
  imageUrls,
  flag,
  onInternal,
}: {
  blocks: Block[];
  imageUrls: Record<string, string>;
  flag?: string;
  onInternal: (id: string) => void;
}) {
  const rich = (block: Block) => <RichText items={block.rich_text} onInternal={onInternal} />;

  return (
    <article className="article-body notion-doc">
      {groupBlocks(blocks).map((group, groupIndex) => {
        if (group.kind === "list") {
          const ListTag = group.listType === "numbered_list_item" ? "ol" : "ul";
          return (
            <ListTag key={groupIndex} className={`notion-list ${group.listType}`}>
              {group.items.map((item, itemIndex) => (
                <li key={itemIndex}>{rich(item)}</li>
              ))}
            </ListTag>
          );
        }

        const block = group.block;
        if (block.type === "image") {
          const src = imageUrls[block.image_id ?? ""];
          return (
            <figure key={groupIndex}>
              <div className="image-frame">
                {src ? (
                  <img src={src} alt={block.caption || "Иллюстрация к материалу"} />
                ) : (
                  <div className="image-placeholder">{flag}</div>
                )}
              </div>
              {block.caption ? <figcaption>{block.caption}</figcaption> : null}
            </figure>
          );
        }
        if (block.type === "divider") return <hr key={groupIndex} className="notion-divider" />;
        if (block.type === "to_do") {
          return (
            <div className="requirement" key={groupIndex}>
              <span className={block.checked ? "check done" : "check"}>
                {block.checked ? "✓" : ""}
              </span>
              <span>{rich(block)}</span>
            </div>
          );
        }
        if (block.type === "code") {
          return (
            <pre key={groupIndex} className="notion-code">
              <code>{block.rich_text?.map((item) => item.text).join("")}</code>
            </pre>
          );
        }
        if (block.type === "callout") {
          return (
            <aside key={groupIndex} className="notion-callout">
              <span className="callout-icon" aria-hidden>
                {block.icon || "💡"}
              </span>
              <div className="callout-body">{rich(block)}</div>
            </aside>
          );
        }
        if (block.type === "quote") {
          return (
            <blockquote key={groupIndex} className="notion-quote">
              {rich(block)}
            </blockquote>
          );
        }
        if (block.type.startsWith("heading_")) {
          const level = Number(block.type.at(-1) ?? "2");
          const Tag = (`h${Math.min(Math.max(level, 1), 4)}` as "h1" | "h2" | "h3" | "h4");
          return (
            <Tag key={groupIndex} className={`notion-h notion-h${level}`}>
              {rich(block)}
            </Tag>
          );
        }
        return (
          <p key={groupIndex} className="notion-p">
            {rich(block)}
          </p>
        );
      })}
    </article>
  );
}
