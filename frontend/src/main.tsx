import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  DocumentBody,
  buildOutline,
  scrollToSection,
  withHeadingAnchors,
} from "./document";
import {
  ApiError,
  downloadPagePdf,
  flushFieldQueue,
  getCountry,
  getImageBlob,
  getPage,
  prefetchCountryTree,
  purchaseCountry,
  registerOfflineShellWorker,
  requestCountrySync,
  setPageField,
  waitForCountrySync,
  type Country,
  type Page,
} from "./offline/content-api";
import {
  classifySessionError,
  clearBoundSession,
  hasTelegramSession,
  type SessionFailure,
} from "./session";
import { applyTheme, bindThemeListeners } from "./theme";
import "./style.css";

type Child = { id: string; title: string; locked: boolean };
type HistoryItem = { id: string; title: string };
type NavState = { pageId: string; history: HistoryItem[] };

function navStorageKey(slug: string): string {
  return `pomogator:nav:${slug}`;
}

function readQueryPageId(): string | null {
  const value = new URLSearchParams(location.search).get("page")?.trim();
  return value || null;
}

function writeQueryPageId(slug: string, pageId: string | null): void {
  const params = new URLSearchParams(location.search);
  params.set("country", slug);
  if (pageId) params.set("page", pageId);
  else params.delete("page");
  const query = params.toString();
  const next = `${location.pathname}${query ? `?${query}` : ""}${location.hash}`;
  if (`${location.pathname}${location.search}${location.hash}` === next) return;
  window.history.replaceState(null, "", next);
}

function readStoredNav(slug: string): NavState | null {
  try {
    const raw = sessionStorage.getItem(navStorageKey(slug));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as NavState;
    if (typeof parsed?.pageId !== "string" || !Array.isArray(parsed.history)) return null;
    const history = parsed.history.filter(
      (item): item is HistoryItem =>
        !!item && typeof item.id === "string" && typeof item.title === "string",
    );
    return history.length ? { pageId: parsed.pageId, history } : null;
  } catch {
    return null;
  }
}

function writeStoredNav(slug: string, pageId: string, history: HistoryItem[]): void {
  try {
    sessionStorage.setItem(navStorageKey(slug), JSON.stringify({ pageId, history }));
  } catch {
    // Ignore quota / private mode failures.
  }
}

function restoreHistoryForPage(
  targetId: string,
  title: string,
  stored: NavState | null,
  root?: { id: string; title: string },
): HistoryItem[] {
  if (stored) {
    const index = stored.history.findIndex((item) => item.id === targetId);
    if (index >= 0) return stored.history.slice(0, index + 1);
  }
  if (root && root.id !== targetId) return [root, { id: targetId, title }];
  return [{ id: targetId, title }];
}

applyTheme();
registerOfflineShellWorker();

const tg = window.Telegram?.WebApp;

function SessionBlocked({ reason }: { reason: SessionFailure }) {
  const title =
    reason === "expired"
      ? "Сессия Telegram истекла"
      : reason === "mismatch"
        ? "Сессия Telegram изменилась"
        : "Нужен вход через Telegram";
  const detail =
    reason === "expired"
      ? "Откройте путеводитель заново из бота — доступ из браузера без актуальной сессии закрыт."
      : reason === "mismatch"
        ? "Эта страница привязана к другой Telegram-сессии. Откройте материал из бота."
        : "Путеводитель открывается только из Telegram Mini App. Скопированная ссылка в браузере не работает.";
  return (
    <main className="shell state" role="alert">
      <p className="kicker">Помогатор</p>
      <h1>{title}</h1>
      <p className="muted">{detail}</p>
    </main>
  );
}

function ScrollTopButton() {
  return (
    <button
      type="button"
      className="scroll-top"
      aria-label="Наверх"
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
    >
      ↑
    </button>
  );
}

function PageLoader({ label = "Загружаем…" }: { label?: string }) {
  return (
    <div className="page-loader" role="status" aria-live="polite" aria-busy="true">
      <div className="page-loader-orbit" aria-hidden="true">
        <span className="page-loader-ring" />
        <span className="page-loader-ring is-inner" />
        <span className="page-loader-dot" />
      </div>
      <p className="page-loader-label">{label}</p>
      <div className="page-loader-skeleton" aria-hidden="true">
        <span className="page-loader-line is-title" />
        <span className="page-loader-line" />
        <span className="page-loader-line is-mid" />
        <span className="page-loader-line is-short" />
      </div>
    </div>
  );
}

function PageOutline({
  sections,
  childrenPages,
  onOpenChild,
  onOpenPaywall,
}: {
  sections: { id: string; level: number; title: string }[];
  childrenPages: Child[];
  onOpenChild: (id: string) => void;
  onOpenPaywall: (title: string, resumeId?: string) => void;
}) {
  const [open, setOpen] = useState(false);
  if (!sections.length && !childrenPages.length) return null;
  const count = sections.length + childrenPages.length;
  return (
    <nav className={`page-outline ${open ? "is-open" : "is-collapsed"}`} aria-label="Оглавление">
      <button
        type="button"
        className="page-outline-toggle"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="page-outline-toggle-label">
          <h2>Оглавление</h2>
          <span className="muted">{count}</span>
        </span>
        <span className="page-outline-chevron" aria-hidden>
          {open ? "▾" : "▸"}
        </span>
      </button>
      {open ? (
        <div className="page-outline-body">
          {sections.length > 0 ? (
            <ol className="page-outline-list">
              {sections.map((item) => (
                <li key={item.id} data-level={item.level}>
                  <button
                    type="button"
                    className="page-outline-link"
                    onClick={() => scrollToSection(item.id)}
                  >
                    {item.title}
                  </button>
                </li>
              ))}
            </ol>
          ) : null}
          {childrenPages.length > 0 ? (
            <ul className="toc-list page-outline-children">
              {childrenPages.map((child) => (
                <li key={child.id}>
                  <button
                    type="button"
                    className="toc-item"
                    onClick={() =>
                      child.locked ? onOpenPaywall(child.title, child.id) : onOpenChild(child.id)
                    }
                  >
                    <span className="toc-title">{child.title}</span>
                    <span className="toc-meta">{child.locked ? "Закрыто" : "Открыть"}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </nav>
  );
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
  const [sessionFailure, setSessionFailure] = useState<SessionFailure | null>(() =>
    hasTelegramSession() ? null : "missing",
  );
  const [country, setCountry] = useState<Country>();
  const [page, setPage] = useState<Page>();
  const [pageId, setPageId] = useState<string>();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [buying, setBuying] = useState(false);
  const [buyError, setBuyError] = useState("");
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [syncProgress, setSyncProgress] = useState(0);
  const [syncPhase, setSyncPhase] = useState("");
  const [syncError, setSyncError] = useState("");
  const [syncNotice, setSyncNotice] = useState("");
  const [paywall, setPaywall] = useState<{ title: string; resumeId?: string }>();
  const [imageUrls, setImageUrls] = useState<Record<string, string>>({});
  const [fields, setFields] = useState<Record<string, string>>({});
  const [offlineMode, setOfflineMode] = useState(false);
  const fieldTimers = useRef<Map<string, number>>(new Map());
  const savedFields = useRef<Record<string, string>>({});
  const pageIdRef = useRef(page?.id);
  pageIdRef.current = page?.id;
  const documentBlocks = useMemo(
    () => (page ? withHeadingAnchors(page.document) : []),
    [page],
  );
  const outline = useMemo(() => buildOutline(documentBlocks), [documentBlocks]);

  const revokeSession = useCallback((reason: SessionFailure) => {
    clearBoundSession();
    setSessionFailure(reason);
    setCountry(undefined);
    setPage(undefined);
    setPageId(undefined);
    setHistory([]);
    setPaywall(undefined);
    setImageUrls({});
    setFields({});
    savedFields.current = {};
    setError("");
    setExportError("");
    setBuyError("");
    setSyncError("");
    setSyncNotice("");
    setLoading(false);
  }, []);

  const handleSessionFailure = useCallback(
    (reason: unknown): boolean => {
      const failure = classifySessionError(reason);
      if (!failure) return false;
      revokeSession(failure);
      return true;
    },
    [revokeSession],
  );

  const loadPage = useCallback(
    async (
      id: string,
      options?: { history?: "push" | "none" | "reset" },
    ): Promise<Page | null> => {
      const historyMode = options?.history ?? "push";
      setLoading(true);
      setError("");
      try {
        const { data: next, meta } = await getPage(id);
        setOfflineMode(meta.fromCache);
        setPage(next);
        setFields(next.fields ?? {});
        savedFields.current = { ...(next.fields ?? {}) };
        setPageId(id);
        setPaywall(undefined);
        setBuyError("");
        writeQueryPageId(slug, next.id);
        if (historyMode === "reset") {
          const trail = [{ id: next.id, title: next.title }];
          setHistory(trail);
          writeStoredNav(slug, next.id, trail);
        } else if (historyMode === "push") {
          setHistory((items) => {
            const trail =
              items.at(-1)?.id === next.id
                ? items
                : [...items, { id: next.id, title: next.title }];
            writeStoredNav(slug, next.id, trail);
            return trail;
          });
        } else {
          setHistory((items) => {
            const trail = items.length ? items : [{ id: next.id, title: next.title }];
            writeStoredNav(slug, next.id, trail);
            return trail;
          });
        }
        return next;
      } catch (reason) {
        if (handleSessionFailure(reason)) return null;
        if (reason instanceof ApiError && reason.status === 402) {
          writeQueryPageId(slug, id);
          setPaywall({ title: "Материал полного доступа", resumeId: id });
          return null;
        }
        if (reason instanceof Error && reason.message === "paid") {
          writeQueryPageId(slug, id);
          setPaywall({ title: "Материал полного доступа", resumeId: id });
          return null;
        }
        setError(
          !navigator.onLine
            ? "Нет сети и страница ещё не сохранена офлайн. Откройте миниапп онлайн один раз."
            : "Не удалось загрузить статью",
        );
        return null;
      } finally {
        setLoading(false);
      }
    },
    [handleSessionFailure, slug],
  );

  const bootstrapCountry = useCallback(async () => {
    if (!hasTelegramSession()) {
      revokeSession("missing");
      return;
    }
    setLoading(true);
    setError("");
    try {
      void flushFieldQueue();
      const { data: value, meta } = await getCountry(slug);
      setOfflineMode(meta.fromCache);
      setCountry(value);
      if (!value.root_page_id) {
        setError("Материалы ещё индексируются");
        return;
      }
      const stored = readStoredNav(slug);
      const targetId = readQueryPageId() || stored?.pageId || value.root_page_id;
      const loaded = await loadPage(targetId, { history: "none" });
      if (loaded) {
        const root =
          value.root_page_id === loaded.id
            ? undefined
            : { id: value.root_page_id, title: value.title };
        const trail = restoreHistoryForPage(loaded.id, loaded.title, stored, root);
        setHistory(trail);
        writeStoredNav(slug, loaded.id, trail);
      } else if (targetId !== value.root_page_id) {
        // Deep link failed (offline miss / deleted) — fall back to country root.
        const root = await loadPage(value.root_page_id, { history: "reset" });
        if (!root) setError("Не удалось открыть страну");
      }
      if (!meta.fromCache) void prefetchCountryTree(value.root_page_id);
    } catch (reason) {
      if (handleSessionFailure(reason)) return;
      setError(
        !navigator.onLine
          ? "Нет сети и страна ещё не сохранена офлайн. Откройте миниапп онлайн один раз."
          : "Не удалось открыть страну",
      );
    } finally {
      setLoading(false);
    }
  }, [handleSessionFailure, loadPage, revokeSession, slug]);

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
    const onOnline = () => {
      setOfflineMode(false);
      void flushFieldQueue();
    };
    const onOffline = () => setOfflineMode(true);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    const unbindTheme = bindThemeListeners();
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
      unbindTheme();
    };
  }, []);

  useEffect(() => {
    if (sessionFailure) return;
    const timer = window.setTimeout(() => {
      void bootstrapCountry();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [bootstrapCountry, sessionFailure]);

  useEffect(() => {
    if (sessionFailure || !page) return;
    const ids = page.document.flatMap((block) => (block.image_id ? [block.image_id] : []));
    const createdUrls: string[] = [];
    let active = true;
    Promise.all(
      ids.map(async (id) => {
        const { blob, meta } = await getImageBlob(id);
        if (meta.fromCache) setOfflineMode(true);
        const objectUrl = URL.createObjectURL(blob);
        createdUrls.push(objectUrl);
        return [id, objectUrl] as const;
      }),
    )
      .then((entries) => {
        if (active) setImageUrls(Object.fromEntries(entries));
      })
      .catch((reason) => {
        if (handleSessionFailure(reason)) return;
      });
    return () => {
      active = false;
      createdUrls.forEach(URL.revokeObjectURL);
    };
  }, [handleSessionFailure, page, sessionFailure]);

  useEffect(() => {
    if (sessionFailure) {
      tg?.BackButton.hide();
      return;
    }
    tg?.BackButton.show();
    tg?.BackButton.onClick(goBack);
    return () => tg?.BackButton.offClick(goBack);
  }, [goBack, sessionFailure]);

  async function buy() {
    setBuying(true);
    setBuyError("");
    try {
      await purchaseCountry(slug);
      setCountry((value) => (value ? { ...value, paid: true } : value));
      const resume = paywall?.resumeId ?? pageId;
      setPaywall(undefined);
      if (resume) await loadPage(resume, { history: "none" });
    } catch (reason) {
      if (handleSessionFailure(reason)) return;
      setBuyError(
        !navigator.onLine
          ? "Оплата недоступна офлайн. Подключите интернет."
          : "Не удалось выдать тестовый доступ. Попробуйте ещё раз.",
      );
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

  async function exportPdf() {
    if (!page) return;
    setExporting(true);
    setExportError("");
    try {
      await downloadPagePdf(page.id, page.title);
      tg?.HapticFeedback.impactOccurred("light");
    } catch (reason) {
      if (handleSessionFailure(reason)) return;
      if (reason instanceof ApiError && reason.status === 402) {
        openPaywall("Материал полного доступа", page.id);
        return;
      }
      setExportError(
        !navigator.onLine
          ? "PDF недоступен офлайн. Подключите интернет."
          : reason instanceof ApiError && reason.message === "download denied"
            ? "Скачивание отклонено. Разрешите сохранение файла в Telegram."
            : "Не удалось сохранить PDF. Попробуйте ещё раз.",
      );
    } finally {
      setExporting(false);
    }
  }

  async function refreshFromNotion() {
    if (!navigator.onLine) {
      setSyncError("Нужен интернет, чтобы обновить материалы.");
      return;
    }
    setSyncing(true);
    setSyncProgress(4);
    setSyncPhase("Готовим обновление…");
    setSyncError("");
    setSyncNotice("");
    const resumePageId = pageIdRef.current;
    try {
      await flushFieldQueue();
      setSyncProgress(12);
      setSyncPhase("Отправляем запрос на обновление…");
      const baseline = country?.content_version ?? 0;
      const started = await requestCountrySync(slug);
      setSyncProgress(22);
      setSyncPhase("Загружаем материалы…");
      const result = await waitForCountrySync(slug, started.content_version ?? baseline, {
        onTick: ({ elapsedMs, status }) => {
          // Asymptotic climb toward ~88% while waiting for the worker.
          const waited = Math.min(1, elapsedMs / 90_000);
          const base = status.status === "running" || status.status === "queued" ? 28 : 22;
          const next = Math.min(88, Math.round(base + waited * 60));
          setSyncProgress((value) => Math.max(value, next));
          setSyncPhase(
            status.status === "running"
              ? "Идёт загрузка материалов…"
              : status.status === "queued"
                ? "В очереди на обновление…"
                : "Проверяем готовность…",
          );
        },
      });
      if (result.status === "failed") {
        setSyncError(
          "Не удалось обновить материалы. Подождите пару минут и попробуйте снова.",
        );
        return;
      }
      setSyncProgress(92);
      setSyncPhase("Обновляем страницу…");
      const { data: nextCountry } = await getCountry(slug);
      setCountry(nextCountry);
      setOfflineMode(false);
      const targetId = resumePageId || nextCountry.root_page_id;
      if (targetId) {
        await loadPage(targetId, { history: "none" });
        void prefetchCountryTree(nextCountry.root_page_id ?? targetId);
      }
      setSyncProgress(100);
      setSyncPhase("Готово");
      setSyncNotice("Материалы обновлены. Ваши ответы в полях сохранены.");
      tg?.HapticFeedback.impactOccurred("light");
      await new Promise((resolve) => window.setTimeout(resolve, 400));
    } catch (reason) {
      if (handleSessionFailure(reason)) return;
      setSyncError(
        reason instanceof ApiError && reason.status === 408
          ? "Обновление занимает слишком много времени. Попробуйте позже."
          : "Не удалось обновить материалы. Попробуйте ещё раз.",
      );
    } finally {
      setSyncing(false);
      setSyncProgress(0);
      setSyncPhase("");
    }
  }

  async function persistField(fieldKey: string, value: string) {
    const pageId = pageIdRef.current;
    if (!pageId) return;
    if (savedFields.current[fieldKey] === value) return;
    try {
      const { fields: next, meta } = await setPageField(pageId, fieldKey, value);
      if (pageIdRef.current !== pageId) return;
      setFields(next);
      savedFields.current = { ...savedFields.current, ...next };
      if (meta.fromCache) setOfflineMode(true);
    } catch (reason) {
      if (handleSessionFailure(reason)) return;
    }
  }

  function onFieldChange(fieldKey: string, value: string) {
    setFields((current) => ({ ...current, [fieldKey]: value }));
    const existing = fieldTimers.current.get(fieldKey);
    if (existing) window.clearTimeout(existing);
    // Debounce text input autosave to avoid hammering the API.
    const timer = window.setTimeout(() => {
      fieldTimers.current.delete(fieldKey);
      void persistField(fieldKey, value);
    }, 500);
    fieldTimers.current.set(fieldKey, timer);
  }

  function onFieldCommit(fieldKey: string, value: string) {
    const existing = fieldTimers.current.get(fieldKey);
    if (existing) {
      window.clearTimeout(existing);
      fieldTimers.current.delete(fieldKey);
    }
    setFields((current) => ({ ...current, [fieldKey]: value }));
    void persistField(fieldKey, value);
  }

  useEffect(() => {
    for (const timer of fieldTimers.current.values()) window.clearTimeout(timer);
    fieldTimers.current.clear();
  }, [page?.id]);

  useEffect(() => {
    return () => {
      for (const timer of fieldTimers.current.values()) window.clearTimeout(timer);
      fieldTimers.current.clear();
    };
  }, []);

  if (sessionFailure) {
    return <SessionBlocked reason={sessionFailure} />;
  }

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
      <main className="shell state is-loading" aria-busy="true">
        {nav}
        <PageLoader label="Загружаем путеводитель…" />
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

  const lockedCount = page.children.filter((child) => child.locked).length;
  const breadcrumbTrail = history.filter((item, index) => {
    if (index === 0 && country?.title && item.title === country.title) return false;
    return true;
  });

  if (loading) {
    return (
      <main className="shell is-loading" aria-busy="true">
        {nav}
        <PageLoader label="Открываем раздел…" />
      </main>
    );
  }

  return (
    <main className="shell">
      {nav}
      {offlineMode || !navigator.onLine ? (
        <p className="offline-banner" role="status">
          Офлайн-режим: показана последняя сохранённая версия. Навигация по уже открытым разделам
          работает.
        </p>
      ) : null}
      <header className="page-header">
        <nav className="breadcrumb" aria-label="Путь">
          <button type="button" className="breadcrumb-link" onClick={goHome}>
            {country?.flag} {country?.title ?? "Страна"}
          </button>
          {breadcrumbTrail.map((item, index) => {
            const isLast = index === breadcrumbTrail.length - 1;
            return (
              <span key={`${item.id}-${index}`} className="breadcrumb-step">
                <span className="sep" aria-hidden>
                  /
                </span>
                {isLast ? (
                  <span className="breadcrumb-current" aria-current="page">
                    {item.title}
                  </span>
                ) : (
                  <button
                    type="button"
                    className="breadcrumb-link"
                    onClick={() => {
                      const position = history.findIndex((entry) => entry.id === item.id);
                      if (position >= 0) {
                        setHistory((items) => items.slice(0, position + 1));
                      }
                      void loadPage(item.id, { history: "none" });
                    }}
                  >
                    {item.title}
                  </button>
                )}
              </span>
            );
          })}
        </nav>
        <div className="title-row">
          <h1>{page.title}</h1>
          <span className={`access ${country?.paid ? "is-paid" : "is-free"}`}>
            {country?.paid ? "Полный доступ" : "Базовый доступ"}
          </span>
        </div>
        <div className="action-row">
          <button
            type="button"
            className="btn btn-secondary"
            disabled={syncing || exporting}
            onClick={() => void refreshFromNotion()}
          >
            {syncing ? "Обновляем…" : "Обновить статью"}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={exporting || syncing}
            onClick={() => void exportPdf()}
          >
            {exporting ? "Готовим PDF…" : "Скачать PDF"}
          </button>
          {!country?.paid && (
            <button
              type="button"
              className="btn btn-secondary"
              disabled={syncing}
              onClick={() =>
                openPaywall(`Полный доступ: ${country?.title ?? page.title}`, page.id)
              }
            >
              Оплатить полный доступ
            </button>
          )}
        </div>
        {syncing ? (
          <div className="sync-banner sync-progress" role="status" aria-live="polite">
            <div className="sync-progress-head">
              <span>{syncPhase || "Обновляем материалы…"}</span>
              <span className="sync-progress-pct">{syncProgress}%</span>
            </div>
            <div
              className="sync-progress-track"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={syncProgress}
              aria-label="Прогресс обновления"
            >
              <div className="sync-progress-fill" style={{ width: `${syncProgress}%` }} />
            </div>
            <p className="sync-progress-hint">Поля и галочки сохраняются.</p>
          </div>
        ) : null}
        {syncNotice ? (
          <p className="sync-banner is-ok" role="status">
            {syncNotice}
          </p>
        ) : null}
        {syncError ? (
          <p className="form-error" role="alert">
            {syncError}
          </p>
        ) : null}
        {exportError ? (
          <p className="form-error" role="alert">
            {exportError}
          </p>
        ) : null}
      </header>

      <PageOutline
        key={page.id}
        sections={outline}
        childrenPages={page.children}
        onOpenChild={open}
        onOpenPaywall={openPaywall}
      />
      {!country?.paid && lockedCount > 0 ? (
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
      ) : null}

      <DocumentBody
        blocks={documentBlocks}
        imageUrls={imageUrls}
        flag={country?.flag}
        onInternal={open}
        fields={fields}
        onFieldChange={onFieldChange}
        onFieldCommit={onFieldCommit}
      />

      <ScrollTopButton />
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
