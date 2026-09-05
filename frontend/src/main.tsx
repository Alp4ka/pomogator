import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

type Link = { type: "external"; url: string } | { type: "internal"; page_id: string };
type Rich = { text: string; annotations?: Record<string, boolean>; link?: Link };
type Block = { type: string; rich_text?: Rich[]; image_id?: string; caption?: string; checked?: boolean; language?: string; icon?: string };
type Child = { id: string; title: string; locked: boolean };
type Page = { id: string; title: string; document: Block[]; children: Child[] };
type Country = { title: string; flag: string; root_page_id: string | null; paid: boolean };
type HistoryItem = { id: string; title: string };

const tg = window.Telegram?.WebApp;
const headers = (): HeadersInit => ({ Authorization: `tma ${tg?.initData ?? ""}` });

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { ...headers(), ...init?.headers } });
  if (response.status === 402) throw new Error("paid");
  if (!response.ok) throw new Error(`http:${response.status}`);
  return response.json() as Promise<T>;
}

function RichText({ items = [], onInternal }: { items?: Rich[]; onInternal: (id: string) => void }) {
  return <>{items.map((item, index) => {
    let node: React.ReactNode = item.text;
    if (item.annotations?.code) node = <code>{node}</code>;
    if (item.annotations?.bold) node = <strong>{node}</strong>;
    if (item.annotations?.italic) node = <em>{node}</em>;
    if (item.annotations?.strikethrough) node = <s>{node}</s>;
    if (item.annotations?.underline) node = <u>{node}</u>;
    if (item.link?.type === "external") node = <a href={item.link.url} target="_blank" rel="noopener noreferrer">{node}</a>;
    if (item.link?.type === "internal") { const pageId = item.link.page_id; node = <button className="text-link" onClick={() => onInternal(pageId)}>{node}</button>; }
    return <React.Fragment key={index}>{node}</React.Fragment>;
  })}</>;
}

function Paywall({ title, onBuy, onBack, busy }: { title: string; onBuy: () => void; onBack: () => void; busy: boolean }) {
  return <main className="paywall" aria-live="polite">
    <button className="back-link" onClick={onBack}>← Вернуться к путеводителю</button>
    <section className="paywall-card">
      <div className="premium-mark">✦ Полный доступ</div>
      <h1>{title}</h1>
      <p className="lead">Эта статья входит в полный путеводитель по стране.</p>
      <div className="preview"><span>Внутри</span><ul><li>Проверенные контакты и практические рекомендации</li><li>Материалы без рекламных переходов в Notion</li><li>Все будущие обновления выбранной страны</li></ul></div>
      <div className="offer"><div><small>Тестовый режим оплаты</small><strong>0 ₽</strong></div><span><b>Все материалы по Бразилии</b><small>включая будущие обновления</small></span></div>
      <button className="primary" disabled={busy} onClick={onBuy}>{busy ? "Открываем доступ…" : "Открыть полный путеводитель"}</button>
      <p className="fineprint">Сейчас используется тестовая оплата: деньги не списываются. Перед запуском она будет заменена платёжной системой.</p>
    </section>
  </main>;
}

function App() {
  const slug = useMemo(() => new URLSearchParams(location.search).get("country") ?? "brazil", []);
  const [country, setCountry] = useState<Country>();
  const [page, setPage] = useState<Page>();
  const [pageId, setPageId] = useState<string>();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [buying, setBuying] = useState(false);
  const [locked, setLocked] = useState<Child>();
  const [imageUrls, setImageUrls] = useState<Record<string, string>>({});

  const loadPage = useCallback(async (id: string) => {
    setLoading(true); setError("");
    try {
      const next = await api<Page>(`/api/pages/${id}`);
      setPage(next); setPageId(id); setLocked(undefined);
      setHistory((items) => items.at(-1)?.id === next.id ? items : [...items, { id: next.id, title: next.title }]);
    } catch (reason) { setError(reason instanceof Error && reason.message === "paid" ? "Для статьи нужен полный доступ" : "Не удалось загрузить статью"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    tg?.ready(); tg?.expand();
    api<Country>(`/api/countries/${slug}`).then((value) => { setCountry(value); if (value.root_page_id) void loadPage(value.root_page_id); else setError("Материалы ещё индексируются"); }).catch(() => setError("Не удалось открыть страну")).finally(() => setLoading(false));
  }, [loadPage, slug]);

  useEffect(() => {
    const ids = page?.document.flatMap((block) => block.image_id ? [block.image_id] : []) ?? [];
    const createdUrls: string[] = []; let active = true;
    Promise.all(ids.map(async (id) => { const response = await fetch(`/api/images/${id}`, { headers: headers() }); if (!response.ok) throw new Error(); const objectUrl = URL.createObjectURL(await response.blob()); createdUrls.push(objectUrl); return [id, objectUrl] as const; }))
      .then((entries) => { if (active) setImageUrls(Object.fromEntries(entries)); }).catch(() => undefined);
    return () => { active = false; createdUrls.forEach(URL.revokeObjectURL); };
  }, [page]);

  const goBack = useCallback(() => { if (history.length > 1) { const next = history.at(-2)!; setHistory((items) => items.slice(0, -1)); setPageId(next.id); } }, [history]);
  useEffect(() => { if (history.length > 1) tg?.BackButton.show(); else tg?.BackButton.hide(); tg?.BackButton.onClick(goBack); return () => tg?.BackButton.offClick(goBack); }, [goBack, history.length]);

  async function buy() {
    if (!locked) return; setBuying(true);
    try { await api(`/api/countries/${slug}/purchase`, { method: "POST" }); setCountry((value) => value ? { ...value, paid: true } : value); await loadPage(locked.id); }
    catch { setError("Не удалось выдать тестовый доступ. Попробуйте ещё раз."); }
    finally { setBuying(false); }
  }

  if (locked) return <Paywall title={locked.title} onBuy={() => void buy()} onBack={() => setLocked(undefined)} busy={buying} />;
  if (loading && !page) return <main className="loading" role="status"><div className="spinner" />Загружаем путеводитель…</main>;
  if (error) return <main className="state" role="alert"><div className="state-icon">!</div><h1>Что-то пошло не так</h1><p>{error}</p><button className="primary" onClick={() => pageId && void loadPage(pageId)}>Повторить</button></main>;
  if (!page) return <main className="state"><h1>Материалы не найдены</h1></main>;
  const open = (id: string) => { tg?.HapticFeedback.impactOccurred("light"); void loadPage(id); };
  const rich = (block: Block) => <RichText items={block.rich_text} onInternal={open} />;
  const isRoot = history.length <= 1;

  return <main className="app-shell">
    {isRoot ? <header className="hero"><div className="hero-top"><div className="flag">{country?.flag ?? "🌍"}</div><span className={country?.paid ? "access paid" : "access free"}>{country?.paid ? "Полный доступ" : "Базовый доступ"}</span></div><p className="eyebrow">Путеводитель по переезду</p><h1>{page.title}</h1><p className="hero-copy">Спокойный маршрут от подготовки документов до первых недель в новой стране.</p><div className="trust-row"><span>✓ Проверено редакцией</span><span>↻ Обновляем материалы</span></div></header> : <header className="article-header"><button className="back-link" onClick={goBack}>← {history.at(-2)?.title ?? "Путеводитель"}</button><p className="eyebrow">{country?.flag} {country?.title}</p><h1>{page.title}</h1><div className="article-meta"><span>Материал путеводителя</span><span>•</span><span>Доступ проверен</span></div></header>}
    <article className="article-body">{page.document.map((block, index) => {
      if (block.type === "image") return <figure key={index}><div className="image-frame">{imageUrls[block.image_id ?? ""] ? <img src={imageUrls[block.image_id ?? ""]} alt={block.caption || "Иллюстрация к материалу"} /> : <div className="image-placeholder">{country?.flag}</div>}</div>{block.caption && <figcaption>{block.caption}</figcaption>}</figure>;
      if (block.type === "divider") return <hr key={index} />;
      if (block.type === "to_do") return <div className="requirement" key={index}><span className={block.checked ? "check done" : "check"}>{block.checked ? "✓" : "•"}</span><span>{rich(block)}</span></div>;
      if (block.type === "code") return <pre key={index}><code>{block.rich_text?.map((item) => item.text).join("")}</code></pre>;
      if (block.type === "callout") return <aside key={index}><span>{block.icon}</span><div>{rich(block)}</div></aside>;
      const tag = block.type.startsWith("heading_") ? `h${block.type.at(-1)}` : block.type.includes("list_item") ? "li" : block.type === "quote" ? "blockquote" : "p";
      return React.createElement(tag, { key: index }, rich(block));
    })}</article>
    {page.children.length > 0 && <section className="guide-section"><div className="section-heading"><div><p className="eyebrow">Следующие шаги</p><h2>Материалы путеводителя</h2></div><span>{page.children.length}</span></div><nav>{page.children.map((child, index) => <button className="article-card" key={child.id} onClick={() => child.locked ? setLocked(child) : open(child.id)}><span className="card-icon">{child.locked ? "◆" : index + 1}</span><span className="card-copy"><strong>{child.title}</strong><small>{child.locked ? "Контакты · полный доступ" : `Инструкция · ${Math.max(3, child.title.length % 8)} мин`}</small></span><span className={child.locked ? "badge locked" : "badge open"}>{child.locked ? "Закрыто" : "Читать"}</span><span className="chevron">›</span></button>)}</nav></section>}
    <footer><strong>Помогатор</strong><span>Материалы для уверенного переезда</span></footer>
  </main>;
}

createRoot(document.getElementById("root")!).render(<App />);
