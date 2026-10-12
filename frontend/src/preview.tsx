import { useMemo, useState } from "react";

import { BottomDock, ChildList, Hero, SectionTabs } from "./chrome";
import {
  DocumentBody,
  buildOutline,
  scrollToSection,
  splitPageChrome,
  withHeadingAnchors,
  type Block,
} from "./document";
import { Icon } from "./icons";
import { applyTheme } from "./theme";

applyTheme();

const HUB_BLOCKS: Block[] = [
  {
    type: "image",
    image_id: "hero",
    caption: "Жуан-Песоа",
  },
  {
    type: "paragraph",
    rich_text: [{ text: "Солнечный город на востоке Бразилии" }],
  },
  { type: "heading_2", rich_text: [{ text: "Почему выбирают Жуан" }] },
  {
    type: "callout",
    icon: "🏠",
    rich_text: [
      { text: "качество жизни", annotations: { bold: true } },
      { text: " спокойный, безопасный и комфортный город" },
    ],
  },
  {
    type: "callout",
    icon: "✚",
    rich_text: [
      { text: "больницы", annotations: { bold: true } },
      { text: " современная медицина и забота о маме и ребёнке" },
    ],
  },
  {
    type: "callout",
    icon: "☀",
    rich_text: [
      { text: "тёплый климат", annotations: { bold: true } },
      { text: " лето круглый год, +25…+30°C" },
    ],
  },
  {
    type: "callout",
    icon: "🌳",
    rich_text: [
      { text: "парки", annotations: { bold: true } },
      { text: " много зелени и мест для прогулок с детьми" },
    ],
  },
  { type: "heading_2", rich_text: [{ text: "Для семьи с новорождённым" }] },
  {
    type: "bulleted_list_item",
    rich_text: [{ text: "Качественная медицина — современные роддома и внимательные врачи" }],
  },
  {
    type: "bulleted_list_item",
    rich_text: [{ text: "Доступная стоимость жизни — больше возможностей для вашей семьи" }],
  },
  {
    type: "bulleted_list_item",
    rich_text: [{ text: "Комфортный ритм для малыша — спокойная атмосфера и дружелюбные люди" }],
  },
  {
    type: "bulleted_list_item",
    rich_text: [{ text: "Зелёный и экологичный город — чистый воздух, парки и близость к природе" }],
  },
  { type: "heading_2", rich_text: [{ text: "Климат" }] },
  {
    type: "callout",
    icon: "☀",
    rich_text: [
      { text: "Лето", annotations: { bold: true } },
      { text: " +25…+30°C" },
    ],
  },
  {
    type: "callout",
    icon: "🌤",
    rich_text: [
      { text: "Осень", annotations: { bold: true } },
      { text: " +25…+30°C" },
    ],
  },
  {
    type: "callout",
    icon: "🌦",
    rich_text: [
      { text: "Зима", annotations: { bold: true } },
      { text: " +25…+30°C" },
    ],
  },
  {
    type: "callout",
    icon: "🌧",
    rich_text: [
      { text: "Весна", annotations: { bold: true } },
      { text: " +25…+30°C" },
    ],
  },
  { type: "heading_2", rich_text: [{ text: "Краткий план" }] },
  {
    type: "numbered_list_item",
    rich_text: [{ text: "Изучить город и подготовиться. Собрать информацию, определиться с районом." }],
  },
  {
    type: "numbered_list_item",
    rich_text: [{ text: "Оформить документы. Виза, перевод документов, страховка." }],
  },
  {
    type: "numbered_list_item",
    rich_text: [{ text: "Найти жильё. Выбрать район и арендовать квартиру." }],
  },
  {
    type: "numbered_list_item",
    rich_text: [{ text: "Выбрать роддом и врача. Записаться на консультацию, заключить договор." }],
  },
  { type: "heading_2", rich_text: [{ text: "FAQ" }] },
  {
    type: "paragraph",
    rich_text: [{ text: "Ниже — ответы на частые вопросы по переезду. Это уже читалка: заголовки, списки и выноски остаются на месте." }],
  },
];

const READER_BLOCKS: Block[] = [
  { type: "heading_2", rich_text: [{ text: "Что подготовить заранее" }] },
  {
    type: "paragraph",
    rich_text: [
      { text: "Соберите цифровые копии документов и проверьте срок действия паспорта. " },
      { text: "Апостиль", annotations: { bold: true } },
      { text: " лучше сделать до вылета." },
    ],
  },
  {
    type: "callout",
    icon: "💡",
    rich_text: [{ text: "Храните сканы отдельно от оригиналов — в облаке и на флешке." }],
  },
  {
    type: "bulleted_list_item",
    rich_text: [{ text: "Загранпаспорт и нотариальные переводы" }],
  },
  {
    type: "bulleted_list_item",
    rich_text: [{ text: "Свидетельство о рождении ребёнка" }],
  },
  { type: "heading_2", rich_text: [{ text: "На месте" }] },
  {
    type: "numbered_list_item",
    rich_text: [{ text: "Открыть счёт и получить CPF" }],
  },
  {
    type: "numbered_list_item",
    rich_text: [{ text: "Заключить договор аренды" }],
  },
  {
    type: "quote",
    rich_text: [{ text: "Не откладывайте страховку на первую неделю — она нужна уже в аэропорту." }],
  },
];

const HERO_SRC =
  "https://images.unsplash.com/photo-1483729558449-99ef03a8a857?auto=format&fit=crop&w=1400&q=80";

export function PreviewApp() {
  const [view, setView] = useState<"hub" | "reader">("hub");
  const blocks = useMemo(
    () => withHeadingAnchors(view === "hub" ? HUB_BLOCKS : READER_BLOCKS),
    [view],
  );
  const chrome = splitPageChrome(blocks);
  const outline = buildOutline(chrome.rest);
  const images = chrome.hero?.image_id ? { [chrome.hero.image_id]: HERO_SRC } : {};

  return (
    <main className={`shell ${view === "reader" ? "is-reader" : ""}`}>
      {view === "hub" ? (
        <Hero
          title="Жуан-Песоа"
          lede={chrome.lede}
          location="🇧🇷 Бразилия"
          imageUrl={images.hero}
          placeholder="🇧🇷"
          accessLabel="Полный доступ"
          paid
          onBack={() => undefined}
          backLabel="Назад"
        />
      ) : (
        <header className="reader-head">
          <button type="button" className="hero-back" onClick={() => setView("hub")} aria-label="Назад">
            <Icon name="back" />
          </button>
          <nav className="breadcrumb" aria-label="Путь">
            <button type="button" className="breadcrumb-link" onClick={() => setView("hub")}>
              🇧🇷 Бразилия
            </button>
            <span className="breadcrumb-step">
              <span className="sep">/</span>
              <span className="breadcrumb-current">Документы</span>
            </span>
          </nav>
          <div className="title-row">
            <h1>Этап 2. Сбор документов</h1>
            <span className="access is-paid">Полный доступ</span>
          </div>
        </header>
      )}
      <SectionTabs items={outline.filter((item) => item.level <= 2)} onSelect={scrollToSection} />
      {view === "hub" ? (
        <ChildList
          title="Разделы"
          items={[
            { id: "docs", title: "Документы", locked: false },
            { id: "cost", title: "Стоимость жизни", locked: false },
            { id: "faq", title: "FAQ", locked: true },
          ]}
          onOpen={() => setView("reader")}
          onPaywall={() => undefined}
        />
      ) : null}
      <DocumentBody
        blocks={chrome.rest}
        imageUrls={images}
        flag="🇧🇷"
        onInternal={() => setView("reader")}
      />
      <BottomDock
        onHome={() => setView("hub")}
        onPdf={() => undefined}
        onRefresh={() => undefined}
        onPay={view === "hub" ? () => undefined : undefined}
        pdfBusy={false}
        syncBusy={false}
        showPay={view === "hub"}
      />
    </main>
  );
}
