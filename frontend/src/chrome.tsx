import { useEffect, useState } from "react";

import type { Child, CountryListItem } from "./content-api";
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
      <span className={`access hero-access ${paid ? "is-paid" : "is-free"}`}>{accessLabel}</span>
      <div className="hero-copy">
        <h1>{title}</h1>
        {lede ? <p className="hero-lede">{lede}</p> : null}
      </div>
    </header>
  );
}

export function ContentsNav({
  items,
  onSelect,
}: {
  items: { id: string; title: string }[];
  onSelect: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
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

  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!items.length) return null;

  return (
    <>
      {open ? null : (
        <button
          type="button"
          className="toc-fab"
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={open}
        >
          <Icon name="list" />
          <span>Содержание</span>
        </button>
      )}
      {open ? (
        <div className="toc-layer">
          <button type="button" className="toc-backdrop" aria-label="Закрыть содержание" onClick={() => setOpen(false)} />
          <div className="toc-sheet" role="dialog" aria-modal="true" aria-labelledby="toc-title">
            <div className="toc-sheet-head">
              <h2 id="toc-title">Содержание</h2>
              <button type="button" className="toc-sheet-close" onClick={() => setOpen(false)}>
                Закрыть
              </button>
            </div>
            <nav className="toc-sheet-list" aria-label="Разделы на странице">
              {items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`toc-sheet-item ${selected === item.id ? "is-active" : ""}`}
                  onClick={() => {
                    setActive(item.id);
                    setOpen(false);
                    onSelect(item.id);
                  }}
                >
                  {item.title}
                </button>
              ))}
            </nav>
          </div>
        </div>
      ) : null}
    </>
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
    <section className="child-section">
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

const LOADER_DELAY_MS = 300;

export function PageLoader({
  label = "Загружаем…",
  delayMs = LOADER_DELAY_MS,
}: {
  label?: string;
  delayMs?: number;
}) {
  const [visible, setVisible] = useState(delayMs <= 0);

  useEffect(() => {
    if (delayMs <= 0) {
      setVisible(true);
      return;
    }
    setVisible(false);
    const timer = window.setTimeout(() => setVisible(true), delayMs);
    return () => window.clearTimeout(timer);
  }, [delayMs]);

  if (!visible) return null;

  return (
    <div className="page-loader" role="status" aria-live="polite" aria-busy="true">
      <div className="page-loader-mark" aria-hidden="true">
        <img className="page-loader-logo" src="/app-logo.svg" width={84} height={84} alt="" />
      </div>
      <span className="page-loader-label">{label}</span>
    </div>
  );
}

export function CountryHome({
  items,
  loading,
  error,
  onOpen,
  onRetry,
  onClose,
}: {
  items: CountryListItem[];
  loading: boolean;
  error: string;
  onOpen: (slug: string) => void;
  onRetry: () => void;
  onClose: () => void;
}) {
  return (
    <main className="shell">
      <header className="home-head">
        <button type="button" className="nav-btn" onClick={onClose} aria-label="Закрыть">
          Закрыть
        </button>
        <p className="kicker">Помогатор</p>
        <h1>Страны</h1>
        <p className="lede">Выберите направление — откроется путеводитель по стране.</p>
      </header>
      {error ? (
        <div className="state">
          <p className="form-error" role="alert">
            {error}
          </p>
          <button type="button" className="btn" onClick={onRetry}>
            Повторить
          </button>
        </div>
      ) : null}
      {!loading && !error && !items.length ? (
        <p className="muted">Пока нет доступных стран.</p>
      ) : null}
      {items.length ? (
        <section className="child-section">
          <ul className="child-list">
            {items.map((item, index) => (
              <li key={item.slug}>
                <button type="button" className="child-row" onClick={() => onOpen(item.slug)}>
                  <span className={`icon-chip tone-${chipTone(index)}`} aria-hidden>
                    {item.flag}
                  </span>
                  <span className="child-copy">
                    <span className="child-title">{item.title}</span>
                    <span className="child-meta">
                      {item.paid ? "Полный доступ" : "Базовый доступ"}
                    </span>
                  </span>
                  <Icon name="chevron" className="child-chevron" />
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </main>
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
