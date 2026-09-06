interface TelegramThemeParams {
  bg_color?: string;
  text_color?: string;
  hint_color?: string;
  link_color?: string;
  button_color?: string;
  button_text_color?: string;
  secondary_bg_color?: string;
}

interface TelegramWebApp {
  initData: string;
  colorScheme: "light" | "dark";
  themeParams?: TelegramThemeParams;
  ready(): void;
  expand(): void;
  close(): void;
  onEvent?(event: string, callback: () => void): void;
  offEvent?(event: string, callback: () => void): void;
  BackButton: {
    show(): void;
    hide(): void;
    onClick(fn: () => void): void;
    offClick(fn: () => void): void;
  };
  HapticFeedback: { impactOccurred(style: string): void };
  downloadFile?(
    params: { url: string; file_name: string },
    callback?: (accepted: boolean) => void,
  ): void;
  openLink?(url: string, options?: { try_instant_view?: boolean }): void;
}

interface Window {
  Telegram?: { WebApp: TelegramWebApp };
}
