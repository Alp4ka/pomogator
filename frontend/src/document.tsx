import React, { useEffect, useRef } from "react";

import { YouTubeEmbed, collectYouTubeIds } from "./youtube-embed";
import { parseYouTubeVideoId } from "./youtube";

export type Link =
  | { type: "external"; url: string }
  | { type: "internal"; page_id: string }
  | { type: "anchor"; label: string };
export type Rich = { text: string; annotations?: Record<string, boolean>; link?: Link };

export type FieldRun =
  | ({ type: "text" } & Rich)
  | {
      type: "input";
      key: string;
      width: number;
      placeholder: string;
      default?: string;
    }
  | { type: "checkbox"; key: string; default: string }
  | { type: "nav_label"; label: string };

export type TableCell =
  | Rich[]
  | {
      rich_text?: Rich[];
      runs?: FieldRun[];
      nav_anchor?: string;
    };

export type Block = {
  type: string;
  rich_text?: Rich[];
  runs?: FieldRun[];
  image_id?: string;
  caption?: string;
  checked?: boolean;
  language?: string;
  icon?: string;
  url?: string;
  video_id?: string;
  anchor_id?: string;
  nav_anchor?: string;
  rows?: TableCell[][];
  has_column_header?: boolean;
  has_row_header?: boolean;
};

export type OutlineItem = { id: string; level: number; title: string };

export type RenderGroup =
  | { kind: "list"; listType: "bulleted_list_item" | "numbered_list_item"; items: Block[] }
  | { kind: "block"; block: Block };

export function plainRichText(items: Rich[] | undefined): string {
  return (items ?? []).map((item) => item.text).join("").trim();
}

export function buildOutline(blocks: Block[]): OutlineItem[] {
  const items: OutlineItem[] = [];
  let index = 0;
  for (const block of blocks) {
    if (!block.type.startsWith("heading_")) continue;
    const title = plainRichText(block.rich_text);
    if (!title) continue;
    const level = Number(block.type.at(-1) ?? "2");
    index += 1;
    items.push({
      id: block.nav_anchor
        ? navDomId(block.nav_anchor)
        : (block.anchor_id ?? `section-${index}`),
      level: Math.min(Math.max(level, 1), 4),
      title,
    });
  }
  return items;
}

export function withHeadingAnchors(blocks: Block[]): Block[] {
  let index = 0;
  return blocks.map((block) => {
    if (!block.type.startsWith("heading_") || !plainRichText(block.rich_text)) return block;
    index += 1;
    return { ...block, anchor_id: `section-${index}` };
  });
}

export function scrollToSection(id: string): void {
  const target = document.getElementById(id);
  if (!target) return;
  target.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function navDomId(label: string): string {
  return `nav-${label.trim().toLocaleLowerCase()}`;
}

function blockDomId(block: Block): string | undefined {
  if (block.nav_anchor) return navDomId(block.nav_anchor);
  return block.anchor_id;
}

function wrapLink(
  node: React.ReactNode,
  link: Link | undefined,
  onInternal: (id: string) => void,
): React.ReactNode {
  if (!link) return node;
  if (link.type === "external") {
    return (
      <a href={link.url} target="_blank" rel="noopener noreferrer" className="text-link">
        {node}
      </a>
    );
  }
  if (link.type === "internal" && link.page_id) {
    const pageId = link.page_id;
    return (
      <button type="button" className="text-link" onClick={() => onInternal(pageId)}>
        {node}
      </button>
    );
  }
  if (link.type === "anchor" && link.label) {
    const target = navDomId(link.label);
    return (
      <button type="button" className="text-link" onClick={() => scrollToSection(target)}>
        {node}
      </button>
    );
  }
  return node;
}

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
      if (items.length) groups.push({ kind: "list", listType, items });
      continue;
    }
    groups.push({ kind: "block", block });
    index += 1;
  }
  return groups;
}

function normalizeCell(cell: TableCell): { rich_text: Rich[]; runs?: FieldRun[] } {
  if (Array.isArray(cell)) return { rich_text: cell };
  return {
    rich_text: cell.rich_text ?? [],
    runs: cell.runs,
  };
}

function richYouTubeUrls(items: Rich[] | undefined): string[] {
  if (!items?.length) return [];
  const urls: string[] = [];
  for (const item of items) {
    if (item.link?.type === "external") urls.push(item.link.url);
    const bare = item.text.trim();
    if (bare.startsWith("http://") || bare.startsWith("https://")) urls.push(bare);
  }
  return urls;
}

function isYouTubeOnlyRich(items: Rich[] | undefined): boolean {
  if (!items?.length) return false;
  let sawVideo = false;
  for (const item of items) {
    const text = item.text.trim();
    if (!text) continue;
    const fromLink =
      item.link?.type === "external" ? parseYouTubeVideoId(item.link.url) : null;
    const fromText = parseYouTubeVideoId(text);
    if (!fromLink && !fromText) return false;
    sawVideo = true;
  }
  return sawVideo;
}

function annotatedText(item: Rich): React.ReactNode {
  let node: React.ReactNode = item.text;
  if (item.annotations?.code) node = <code>{node}</code>;
  if (item.annotations?.bold) node = <strong>{node}</strong>;
  if (item.annotations?.italic) node = <em>{node}</em>;
  if (item.annotations?.strikethrough) node = <s>{node}</s>;
  if (item.annotations?.underline) node = <u>{node}</u>;
  return node;
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
        const node = wrapLink(annotatedText(item), item.link, onInternal);
        return <React.Fragment key={index}>{node}</React.Fragment>;
      })}
    </>
  );
}

function InlineInput({
  fieldKey,
  width,
  placeholder,
  value,
  onChange,
  onCommit,
}: {
  fieldKey: string;
  width: number;
  placeholder: string;
  value: string;
  onChange?: (key: string, value: string) => void;
  onCommit?: (key: string, value: string) => void;
}) {
  const localRef = useRef(value);
  useEffect(() => {
    localRef.current = value;
  }, [value]);
  const chars = Math.max(1, Math.min(120, width));
  return (
    <input
      type="text"
      className="pmg-field-input"
      style={{ width: `calc(${chars}ch + 1.1rem)` }}
      placeholder={placeholder}
      value={value}
      maxLength={2000}
      disabled={!onChange}
      aria-label={placeholder || "Поле ввода"}
      onChange={(event) => {
        localRef.current = event.target.value;
        onChange?.(fieldKey, event.target.value);
      }}
      onBlur={() => onCommit?.(fieldKey, localRef.current)}
    />
  );
}

function InlineCheckbox({
  fieldKey,
  checked,
  onChange,
}: {
  fieldKey: string;
  checked: boolean;
  onChange?: (key: string, value: string) => void;
}) {
  return (
    <label className={`pmg-field-cb ${checked ? "is-checked" : ""}`}>
      <input
        type="checkbox"
        className="pmg-field-cb-input"
        checked={checked}
        disabled={!onChange}
        onChange={(event) => onChange?.(fieldKey, event.target.checked ? "true" : "false")}
      />
      <span className={checked ? "check done" : "check"} aria-hidden>
        {checked ? "✓" : ""}
      </span>
    </label>
  );
}

export function FieldRuns({
  runs,
  fallback,
  fields,
  onInternal,
  onFieldChange,
  onFieldCommit,
}: {
  runs?: FieldRun[];
  fallback?: Rich[];
  fields: Record<string, string>;
  onInternal: (id: string) => void;
  onFieldChange?: (key: string, value: string) => void;
  onFieldCommit?: (key: string, value: string) => void;
}) {
  if (!runs?.length) {
    return <RichText items={fallback} onInternal={onInternal} />;
  }
  return (
    <>
      {runs.map((run, index) => {
        if (run.type === "nav_label") {
          return null;
        }
        if (run.type === "text") {
          const node = wrapLink(annotatedText(run), run.link, onInternal);
          return <React.Fragment key={index}>{node}</React.Fragment>;
        }
        if (run.type === "input") {
          return (
            <InlineInput
              key={run.key}
              fieldKey={run.key}
              width={run.width}
              placeholder={run.placeholder}
              value={fields[run.key] ?? run.default ?? ""}
              onChange={onFieldChange}
              onCommit={onFieldCommit}
            />
          );
        }
        const checked = (fields[run.key] ?? run.default) === "true";
        return (
          <InlineCheckbox
            key={run.key}
            fieldKey={run.key}
            checked={checked}
            onChange={(key, value) => {
              if (onFieldCommit) onFieldCommit(key, value);
              else onFieldChange?.(key, value);
            }}
          />
        );
      })}
    </>
  );
}

function YouTubeStack({ ids, caption }: { ids: string[]; caption?: string }) {
  if (!ids.length) return null;
  return (
    <div className="youtube-stack">
      {ids.map((id) => (
        <YouTubeEmbed key={id} videoId={id} title={caption || "Видео YouTube"} />
      ))}
    </div>
  );
}

function BlockWithOptionalVideos({
  children,
  items,
  wrapClass,
}: {
  children: React.ReactNode;
  items?: Rich[];
  wrapClass?: string;
}) {
  const ids = collectYouTubeIds(richYouTubeUrls(items));
  const onlyVideo = isYouTubeOnlyRich(items);
  if (onlyVideo && ids.length) {
    return <YouTubeStack ids={ids} />;
  }
  return (
    <div className={wrapClass}>
      {children}
      <YouTubeStack ids={ids} />
    </div>
  );
}

function renderContentBlock(
  block: Block,
  groupIndex: number,
  imageUrls: Record<string, string>,
  flag: string | undefined,
  onInternal: (id: string) => void,
  rich: (block: Block) => React.ReactNode,
  fields: Record<string, string>,
  onFieldChange?: (key: string, value: string) => void,
  onFieldCommit?: (key: string, value: string) => void,
): React.ReactNode {
  if (block.type === "youtube" || block.type === "video") {
    const id = block.video_id || parseYouTubeVideoId(block.url);
    if (!id) return null;
    return (
      <YouTubeEmbed key={groupIndex} videoId={id} title={block.caption || "Видео YouTube"} />
    );
  }
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
  if (block.type === "table") {
    const rows = block.rows ?? [];
    if (!rows.length) return null;
    return (
      <div key={groupIndex} className="notion-table-wrap">
        <table className="notion-table">
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {row.map((cell, cellIndex) => {
                  const header =
                    (block.has_column_header && rowIndex === 0) ||
                    (block.has_row_header && cellIndex === 0);
                  const CellTag = header ? "th" : "td";
                  const normalized = normalizeCell(cell);
                  const cellId =
                    !Array.isArray(cell) && cell.nav_anchor
                      ? navDomId(cell.nav_anchor)
                      : undefined;
                  return (
                    <CellTag key={cellIndex} id={cellId}>
                      <FieldRuns
                        runs={normalized.runs}
                        fallback={normalized.rich_text}
                        fields={fields}
                        onInternal={onInternal}
                        onFieldChange={onFieldChange}
                        onFieldCommit={onFieldCommit}
                      />
                    </CellTag>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  if (block.type === "divider") return <hr key={groupIndex} className="notion-divider" />;
  if (block.type === "code") {
    return (
      <pre key={groupIndex} className="notion-code">
        <code>{block.rich_text?.map((item) => item.text).join("")}</code>
      </pre>
    );
  }
  if (block.type === "callout") {
    return (
      <BlockWithOptionalVideos key={groupIndex} items={block.rich_text}>
        <aside id={blockDomId(block)} className="notion-callout">
          <span className="callout-icon" aria-hidden>
            {block.icon || "💡"}
          </span>
          <div className="callout-body">{rich(block)}</div>
        </aside>
      </BlockWithOptionalVideos>
    );
  }
  if (block.type === "quote") {
    return (
      <BlockWithOptionalVideos key={groupIndex} items={block.rich_text}>
        <blockquote id={blockDomId(block)} className="notion-quote">
          {rich(block)}
        </blockquote>
      </BlockWithOptionalVideos>
    );
  }
  if (block.type.startsWith("heading_")) {
    const level = Number(block.type.at(-1) ?? "2");
    const Tag = (`h${Math.min(Math.max(level, 1), 4)}` as "h1" | "h2" | "h3" | "h4");
    return (
      <BlockWithOptionalVideos key={groupIndex} items={block.rich_text}>
        <Tag id={blockDomId(block)} className={`notion-h notion-h${level}`}>
          {rich(block)}
        </Tag>
      </BlockWithOptionalVideos>
    );
  }
  return (
    <BlockWithOptionalVideos
      key={groupIndex}
      items={block.rich_text}
      wrapClass="notion-p-wrap"
    >
      <p id={blockDomId(block)} className="notion-p">
        {rich(block)}
      </p>
    </BlockWithOptionalVideos>
  );
}

export function DocumentBody({
  blocks,
  imageUrls,
  flag,
  onInternal,
  fields = {},
  onFieldChange,
  onFieldCommit,
}: {
  blocks: Block[];
  imageUrls: Record<string, string>;
  flag?: string;
  onInternal: (id: string) => void;
  fields?: Record<string, string>;
  onFieldChange?: (key: string, value: string) => void;
  onFieldCommit?: (key: string, value: string) => void;
}) {
  const rich = (block: Block) => (
    <FieldRuns
      runs={block.runs}
      fallback={block.rich_text}
      fields={fields}
      onInternal={onInternal}
      onFieldChange={onFieldChange}
      onFieldCommit={onFieldCommit}
    />
  );

  return (
    <article className="article-body notion-doc">
      {groupBlocks(blocks).map((group, groupIndex) => {
        if (group.kind === "list") {
          const ListTag = group.listType === "numbered_list_item" ? "ol" : "ul";
          return (
            <ListTag key={groupIndex} className={`notion-list ${group.listType}`}>
              {group.items.map((item, itemIndex) => {
                const ids = collectYouTubeIds(richYouTubeUrls(item.rich_text));
                const onlyVideo = isYouTubeOnlyRich(item.rich_text);
                return (
                  <li key={itemIndex} id={blockDomId(item)}>
                    {onlyVideo && ids.length ? null : rich(item)}
                    <YouTubeStack ids={ids} />
                  </li>
                );
              })}
            </ListTag>
          );
        }
        return renderContentBlock(
          group.block,
          groupIndex,
          imageUrls,
          flag,
          onInternal,
          rich,
          fields,
          onFieldChange,
          onFieldCommit,
        );
      })}
    </article>
  );
}
