import { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { DocumentBody } from "./document";
import { applyTheme, bindThemeListeners } from "./theme";
import "./style.css";

type Child = { id: string; title: string; locked: boolean };
type Page = { id: string; title: string; document: import("./document").Block[]; children: Child[] };
type Country = { title: string; flag: string; root_page_id: string | null; paid: boolean; slug?: string };
type HistoryItem = { id: string; title: string };

applyTheme();

const tg = window.Telegram?.WebApp;
const headers = (): HeadersInit => ({ Authorization: `tma ${tg?.initData ?? ""}` });

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { ...headers(), ...init?.headers } });
  if (response.status === 402) throw new Error("paid");
  if (!response.ok) throw new Error(`http:${response.status}`);
  return response.json() as Promise<T>;
}

function SiteNav({
  onBack,
  onHome,
  backLabel,
}: {
  onBack: () => void;
  onHome: () => void;
  backLabel: string;
}) {
  return (
    <nav className="site-nav" aria-label="Навигация">
      <button type="button" className="nav-btn" onClick={onBack} aria-label={backLabel}>
        ← Назад
      </button>
      <button type="button" className="nav-btn" onClick={onHome} aria-label="На главную">
        На главную
      </button>
    </nav>
  );
}

function Paywall({
  title,
  countryTitle,
  onBuy,
  onBack,
  onHome,
  busy,
  error,
}: {
  title: string;
  countryTitle: string;
  onBuy: () => void;
  onBack: () => void;
  onHome: () => void;
  busy: boolean;
  error?: string;
}) {
  return (
    <main className="shell" aria-live="polite">
      <SiteNav onBack={onBack} onHome={onHome} backLabel="Назад" />
      <section className="paywall">
        <p className="kicker">Полный доступ</p>
        <h1>{title}</h1>
        <p className="lede">
          Все закрытые этапы и обновления по стране <strong>{countryTitle}</strong>.
        </p>
        <ul className="plain-list">
          <li>Закрытые этапы и чек-листы</li>
          <li>Контакты без рекламных переходов</li>
          <li>Будущие обновления этой страны</li>
        </ul>
        <div className="price-row">
          <div>
            <span className="muted">Тестовая оплата</span>
            <strong className="price">0 ₽</strong>
          </div>
          <button type="button" className="btn" disabled={busy} onClick={onBuy}>
            {busy ? "Открываем…" : "Оплатить полный доступ"}
          </button>
        </div>
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        <p className="fineprint">Деньги не списываются. Позже подключим боевую оплату.</p>
      </section>
    </main>
  );
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
  const [buyError, setBuyError] = useState("");
  const [paywall, setPaywall] = useState<{ title: string; resumeId?: string }>();
  const [imageUrls, setImageUrls] = useState<Record<string, string>>({});

  const loadPage = useCallback(async (id: string, options?: { history?: "push" | "none" | "reset" }) => {
    const historyMode = options?.history ?? "push";
    setLoading(true);
    setError("");
    try {
      const next = await api<Page>(`/api/pages/${id}`);
      setPage(next);
      setPageId(id);
      setPaywall(undefined);
      setBuyError("");
      if (historyMode === "reset") setHistory([{ id: next.id, title: next.title }]);
      else if (historyMode === "push") {
        setHistory((items) =>
          items.at(-1)?.id === next.id ? items : [...items, { id: next.id, title: next.title }],
        );
      }
    } catch (reason) {
      if (reason instanceof Error && reason.message === "paid") {
        setPaywall({ title: "Материал полного доступа", resumeId: id });
        return;
      }
      setError("Не удалось загрузить статью");
    } finally {
      setLoading(false);
    }
  }, []);

  const bootstrapCountry = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const value = await api<Country>(`/api/countries/${slug}`);
      setCountry(value);
      if (value.root_page_id) await loadPage(value.root_page_id, { history: "reset" });
      else setError("Материалы ещё индексируются");
    } catch {
      setError("Не удалось открыть страну");
    } finally {
      setLoading(false);
    }
  }, [loadPage, slug]);

  const goHome = useCallback(() => {
    const rootId = country?.root_page_id;
    if (!rootId) return;
    tg?.HapticFeedback.impactOccurred("light");
    setPaywall(undefined);
    setBuyError("");
    void loadPage(rootId, { history: "reset" });
  }, [country?.root_page_id, loadPage]);

  const goBack = useCallback(() => {
    if (paywall) {
      setPaywall(undefined);
      setBuyError("");
      return;
    }
    if (history.length <= 1) {
      tg?.close?.();
      return;
    }
    const previous = history.at(-2)!;
    setHistory((items) => items.slice(0, -1));
    void loadPage(previous.id, { history: "none" });
  }, [history, loadPage, paywall]);

  useEffect(() => {
    tg?.ready();
    tg?.expand();
    return bindThemeListeners();
  }, []);

  useEffect(() => {
    void bootstrapCountry();
  }, [bootstrapCountry]);

  useEffect(() => {
    const ids = page?.document.flatMap((block) => (block.image_id ? [block.image_id] : [])) ?? [];
    const createdUrls: string[] = [];
    let active = true;
    Promise.all(
      ids.map(async (id) => {
        const response = await fetch(`/api/images/${id}`, { headers: headers() });
        if (!response.ok) throw new Error();
        const objectUrl = URL.createObjectURL(await response.blob());
        createdUrls.push(objectUrl);
        return [id, objectUrl] as const;
      }),
    )
      .then((entries) => {
        if (active) setImageUrls(Object.fromEntries(entries));
      })
      .catch(() => undefined);
    return () => {
      active = false;
      createdUrls.forEach(URL.revokeObjectURL);
    };
  }, [page]);

  useEffect(() => {
    tg?.BackButton.show();
    tg?.BackButton.onClick(goBack);
    return () => tg?.BackButton.offClick(goBack);
  }, [goBack]);

  async function buy() {
    setBuying(true);
    setBuyError("");
    try {
      await api(`/api/countries/${slug}/purchase`, { method: "POST" });
      setCountry((value) => (value ? { ...value, paid: true } : value));
      const resume = paywall?.resumeId ?? pageId;
      setPaywall(undefined);
      if (resume) await loadPage(resume, { history: "none" });
    } catch {
      setBuyError("Не удалось выдать тестовый доступ. Попробуйте ещё раз.");
    } finally {
      setBuying(false);
    }
  }

  const open = (id: string) => {
    tg?.HapticFeedback.impactOccurred("light");
    void loadPage(id);
  };

  const openPaywall = (title: string, resumeId?: string) => {
    tg?.HapticFeedback.impactOccurred("medium");
    setBuyError("");
    setPaywall({ title, resumeId });
  };

  const nav = (
    <SiteNav
      onBack={goBack}
      onHome={goHome}
      backLabel={history.length > 1 || paywall ? "Назад" : "Закрыть"}
    />
  );

  if (paywall) {
    return (
      <Paywall
        title={paywall.title}
        countryTitle={country?.title ?? "страна"}
        onBuy={() => void buy()}
        onBack={goBack}
        onHome={goHome}
        busy={buying}
        error={buyError}
      />
    );
  }
  if (loading && !page) {
    return (
      <main className="shell state">
        {nav}
        <p className="muted">Загружаем путеводитель…</p>
      </main>
    );
  }
  if (error) {
    return (
      <main className="shell state" role="alert">
        {nav}
        <h1>Не удалось открыть</h1>
        <p className="muted">{error}</p>
        <button
          type="button"
          className="btn"
          onClick={() => void (pageId ? loadPage(pageId) : bootstrapCountry())}
        >
          Повторить
        </button>
      </main>
    );
  }
  if (!page) {
    return (
      <main className="shell state">
        {nav}
        <h1>Материалы не найдены</h1>
      </main>
    );
  }

  const isRoot = history.length <= 1;
  const lockedCount = page.children.filter((child) => child.locked).length;

  return (
    <main className="shell">
      {nav}
      <header className="page-header">
        <p className="breadcrumb">
          <span>
            {country?.flag} {country?.title ?? "Страна"}
          </span>
          {!isRoot && history.length > 1 ? (
            <>
              <span className="sep">/</span>
              <span>{history.at(-2)?.title}</span>
            </>
          ) : null}
        </p>
        <div className="title-row">
          <h1>{page.title}</h1>
          <span className={`access ${country?.paid ? "is-paid" : "is-free"}`}>
            {country?.paid ? "Полный доступ" : "Базовый доступ"}
          </span>
        </div>
        {!country?.paid && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() =>
              openPaywall(`Полный доступ: ${country?.title ?? page.title}`, page.id)
            }
          >
            Оплатить полный доступ
          </button>
        )}
      </header>

      <DocumentBody
        blocks={page.document}
        imageUrls={imageUrls}
        flag={country?.flag}
        onInternal={open}
      />

      {page.children.length > 0 && (
        <section className="toc">
          <div className="toc-head">
            <h2>Содержание</h2>
            <span className="muted">{page.children.length}</span>
          </div>
          {!country?.paid && lockedCount > 0 && (
            <button
              type="button"
              className="btn btn-secondary toc-pay"
              onClick={() =>
                openPaywall(
                  `Полный доступ · ${country?.title ?? "страна"}`,
                  page.children.find((child) => child.locked)?.id,
                )
              }
            >
              Открыть {lockedCount} закрытых материалов
            </button>
          )}
          <ul className="toc-list">
            {page.children.map((child) => (
              <li key={child.id}>
                <button
                  type="button"
                  className="toc-item"
                  onClick={() =>
                    child.locked ? openPaywall(child.title, child.id) : open(child.id)
                  }
                >
                  <span className="toc-title">{child.title}</span>
                  <span className="toc-meta">{child.locked ? "Закрыто" : "Открыть"}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
