export type IconName =
  | "pin"
  | "home"
  | "sun"
  | "plus"
  | "tree"
  | "heart"
  | "file"
  | "map"
  | "list"
  | "chat"
  | "lock"
  | "chevron"
  | "back"
  | "pdf"
  | "refresh"
  | "check"
  | "faq"
  | "plane"
  | "leaf"
  | "cart"
  | "baby"
  | "up";

const PATHS: Record<IconName, string> = {
  pin: "M12 21s7-5.4 7-11a7 7 0 1 0-14 0c0 5.6 7 11 7 11zm0-8.5a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5z",
  home: "M4 11.5 12 4l8 7.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1z",
  sun: "M12 5.2V3m0 18v-2.2M5.2 12H3m18 0h-2.2M6.4 6.4 4.9 4.9m14.2 14.2-1.5-1.5M17.6 6.4l1.5-1.5M4.9 19.1l1.5-1.5M12 8.2a3.8 3.8 0 1 1 0 7.6 3.8 3.8 0 0 1 0-7.6z",
  plus: "M12 7v10M7 12h10",
  tree: "M12 21V11m-5 10h10M12 4 7.5 11h9L12 4zm-2 7-3 5h10l-3-5",
  heart: "M12 20s-7-4.4-7-9.2A4.2 4.2 0 0 1 12 8a4.2 4.2 0 0 1 7 2.8C19 15.6 12 20 12 20z",
  file: "M7 4h7l4 4v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zm7 0v4h4",
  map: "M4 7.2 9.2 5l5.6 2.2L20 5v12.8L14.8 20l-5.6-2.2L4 20zm5.2-2.2v12.8m5.6-10.6v12.8",
  list: "M8 7h12M8 12h12M8 17h12M4.5 7h.01M4.5 12h.01M4.5 17h.01",
  chat: "M5 18.5 7.2 16H18a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v11.5z",
  lock: "M8 11V8.2a4 4 0 1 1 8 0V11M7 11h10v9H7z",
  chevron: "M9 6l6 6-6 6",
  back: "M14 6l-6 6 6 6",
  pdf: "M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm7 0v5h5M9 14h6M9 18h4",
  refresh:
    "M20 12a8 8 0 1 1-2.3-5.7M20 12V6m0 6h-6",
  check: "M6 12.5 10 16.5 18 8",
  faq: "M9.2 9a2.8 2.8 0 1 1 4.4 2.3c-.9.6-1.6 1.2-1.6 2.4M12 17.5h.01",
  plane: "M21 4 10.5 14.5M21 4l-7.2 17-3.3-6.5L4 11.2 21 4z",
  leaf: "M5 19s1-8 9.5-11.5C20 5 20 5 20 5s0 6.2-4.2 10.5C11.5 20 5 19 5 19zm0 0 5.5-5.5",
  cart: "M5 6h2l1.2 9h9.3l1.7-6H8M9 20.2a.9.9 0 1 1 0-1.8.9.9 0 0 1 0 1.8zm9 0a.9.9 0 1 1 0-1.8.9.9 0 0 1 0 1.8z",
  baby: "M12 8.2a2.4 2.4 0 1 0 0-4.8 2.4 2.4 0 0 0 0 4.8zM7 20c0-3.3 2.2-5.5 5-5.5s5 2.2 5 5.5M8.2 12.2c.8.6 1.9 1 3.8 1s3-.4 3.8-1",
  up: "M6 14l6-6 6 6",
};

const RULES: [RegExp, IconName][] = [
  [/климат|погод|солнц|лето|осень|зима|весн/i, "sun"],
  [/план|этап|шаг|подготов/i, "list"],
  [/карт/i, "map"],
  [/документ|виз|паспорт|pdf/i, "file"],
  [/faq|вопрос/i, "faq"],
  [/город|район|жуан|песоа/i, "home"],
  [/медиц|больниц|врач|родд|health/i, "plus"],
  [/парк|зелен|эколог/i, "tree"],
  [/семь|ребён|малыш|новорожд/i, "heart"],
  [/стоим|цен|оплат/i, "cart"],
  [/контакт|связ|чат/i, "chat"],
  [/переезд|авиа|самол|вылет/i, "plane"],
  [/жиль|квартир|дом/i, "home"],
];

export function pickIcon(title: string): IconName {
  for (const [pattern, name] of RULES) {
    if (pattern.test(title)) return name;
  }
  return "file";
}

export function Icon({ name, className }: { name: IconName; className?: string }) {
  const fill = name === "pin" || name === "heart" || name === "home" ? "currentColor" : "none";
  const filled = name === "pin" || name === "heart" || name === "home";
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill={filled ? fill : "none"}
      stroke="currentColor"
      strokeWidth={filled ? 0 : 1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
