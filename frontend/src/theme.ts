/** Apply Telegram + OS color scheme to document CSS variables. */

type ThemeParams = Partial<{
  bg_color: string;
  text_color: string;
  hint_color: string;
  link_color: string;
  button_color: string;
  button_text_color: string;
  secondary_bg_color: string;
}>;

function readOsScheme(): "light" | "dark" {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function fallbackPalette(scheme: "light" | "dark"): Required<ThemeParams> {
  if (scheme === "dark") {
    return {
      bg_color: "#16181d",
      text_color: "#f2f4f7",
      hint_color: "#9aa3b2",
      link_color: "#6ee7b0",
      button_color: "#1db978",
      button_text_color: "#ffffff",
      secondary_bg_color: "#1e2229",
    };
  }
  return {
    bg_color: "#f3f5f8",
    text_color: "#1c2430",
    hint_color: "#8b94a3",
    link_color: "#1b8f6a",
    button_color: "#1db978",
    button_text_color: "#ffffff",
    secondary_bg_color: "#ffffff",
  };
}

function mergeTheme(params: ThemeParams | undefined, scheme: "light" | "dark"): Required<ThemeParams> {
  const base = fallbackPalette(scheme);
  return {
    bg_color: params?.bg_color || base.bg_color,
    text_color: params?.text_color || base.text_color,
    hint_color: params?.hint_color || base.hint_color,
    link_color: params?.link_color || base.link_color,
    button_color: params?.button_color || base.button_color,
    button_text_color: params?.button_text_color || base.button_text_color,
    secondary_bg_color: params?.secondary_bg_color || base.secondary_bg_color,
  };
}

export function applyTheme(): "light" | "dark" {
  const tg = window.Telegram?.WebApp;
  const scheme = (tg?.colorScheme as "light" | "dark" | undefined) ?? readOsScheme();
  const theme = mergeTheme(tg?.themeParams, scheme);
  const root = document.documentElement;
  root.dataset.theme = scheme;
  root.style.colorScheme = scheme;
  root.style.setProperty("--tg-theme-bg-color", theme.bg_color);
  root.style.setProperty("--tg-theme-text-color", theme.text_color);
  root.style.setProperty("--tg-theme-hint-color", theme.hint_color);
  root.style.setProperty("--tg-theme-link-color", theme.link_color);
  root.style.setProperty("--tg-theme-button-color", theme.button_color);
  root.style.setProperty("--tg-theme-button-text-color", theme.button_text_color);
  root.style.setProperty("--tg-theme-secondary-bg-color", theme.secondary_bg_color);
  return scheme;
}

export function bindThemeListeners(onChange?: (scheme: "light" | "dark") => void): () => void {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const refresh = () => {
    const scheme = applyTheme();
    onChange?.(scheme);
  };
  media.addEventListener("change", refresh);
  const tg = window.Telegram?.WebApp;
  tg?.onEvent?.("themeChanged", refresh);
  return () => {
    media.removeEventListener("change", refresh);
    tg?.offEvent?.("themeChanged", refresh);
  };
}
