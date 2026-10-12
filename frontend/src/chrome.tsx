import { useEffect, useState } from "react";

import type { Child } from "./offline/content-api";
import { Icon, pickIcon, type IconName } from "./icons";

const TONES = 4;

export function chipTone(index: number): number {
  return (index % TONES) + 1;
}

export function Hero({
  title,
  lede,
  location,
  imageUrl,
  placeholder,
  accessLabel,
  paid,
  onBack,
  backLabel,
}: {
  title: string;
  lede?: string;
  location?: string;
  imageUrl?: string;
  placeholder?: string;
  accessLabel: string;
  paid: boolean;
  onBack: () => void;
  backLabel: string;
}) {
  return (
    <header className={`hero ${imageUrl ? "has-image" : "is-plain"}`}>
      {imageUrl ? (
        <img className="hero-image" src={imageUrl} alt="" />
      ) : (
        <div className="hero-fallback" aria-hidden>
          <span>{placeholder}</span>
        </div>
      )}
      <div className="hero-shade" />
      <button type="button" className="hero-back" onClick={onBack} aria-label={backLabel}>
        <Icon name="back" />
      </button>
      {location ? (
        <p className="hero-location">
          <Icon name="pin" />
          <span>{location}</span>
        </p>
      ) : null}
      <div className="hero-copy">
        <h1>{title}</h1>
        {lede ? <p className="hero-lede">{lede}</p> : null}
        <span className={`access ${paid ? "is-paid" : "is-free"}`}>{accessLabel}</span>
      </div>
    </header>
  );
}

export function SectionTabs({
  items,
  onSelect,
}: {
  items: { id: string; title: string }[];
  onSelect: (id: string) => void;
}) {
  const [active, setActive] = useState(items[0]?.id ?? "");
  const itemKey = items.map((item) => item.id).join("|");
  const selected = items.some((item) => item.id === active) ? active : (items[0]?.id ?? "");

  useEffect(() => {
    if (!items.length) return;
    const nodes = items
      .map((item) => document.getElementById(item.id))
      .filter((node): node is HTMLElement => Boolean(node));
    if (!nodes.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        const id = visible?.target.id;
        if (id) setActive(id);
      },
      { rootMargin: "-20% 0px -65% 0px", threshold: [0.1, 0.4, 0.8] },
    );
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, [itemKey, items]);

  if (!items.length) return null;

  return (
    <nav className="section-tabs" aria-label="Разделы на странице">
      <div className="section-tabs-scroller">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`section-tab ${selected === item.id ? "is-active" : ""}`}
            onClick={() => {
              setActive(item.id);
              onSelect(item.id);
            }}
          >
            {item.title}
          </button>
        ))}
      </div>
    </nav>
  );
}

export function ChildList({
  title,
  items,
  onOpen,
  onPaywall,
}: {
  title?: string;
  items: Child[];
  onOpen: (id: string) => void;
  onPaywall: (title: string, resumeId?: string) => void;
}) {
  if (!items.length) return null;
  return (
    <section className="section-card child-section">
      {title ? <h2 className="section-title">{title}</h2> : null}
      <ul className="child-list">
        {items.map((child, index) => (
          <li key={child.id}>
            <button
              type="button"
              className="child-row"
              onClick={() =>
                child.locked ? onPaywall(child.title, child.id) : onOpen(child.id)
              }
            >
              <span className={`icon-chip tone-${chipTone(index)}`} aria-hidden>
                <Icon name={child.locked ? "lock" : pickIcon(child.title)} />
              </span>
              <span className="child-copy">
                <span className="child-title">{child.title}</span>
                <span className="child-meta">{child.locked ? "Закрыто" : "Открыть раздел"}</span>
              </span>
              <Icon name="chevron" className="child-chevron" />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function BottomDock({
  onHome,
  onPdf,
  onRefresh,
  onPay,
  pdfBusy,
  syncBusy,
  showPay,
}: {
  onHome: () => void;
  onPdf: () => void;
  onRefresh: () => void;
  onPay?: () => void;
  pdfBusy: boolean;
  syncBusy: boolean;
  showPay: boolean;
}) {
  const item = (label: string, icon: IconName, onClick: () => void, busy?: boolean) => (
    <button type="button" className="dock-item" disabled={busy} onClick={onClick}>
      <Icon name={icon} />
      <span>{busy ? "…" : label}</span>
    </button>
  );
  return (
    <nav className="dock" aria-label="Действия">
      {item("Главная", "home", onHome)}
      {item("PDF", "pdf", onPdf, pdfBusy)}
      {item("Обновить", "refresh", onRefresh, syncBusy)}
      {showPay && onPay ? (
        <button type="button" className="dock-cta" onClick={onPay}>
          <Icon name="chat" />
          <span>Оплатить</span>
        </button>
      ) : null}
    </nav>
  );
}
