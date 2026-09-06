/** Parse and build YouTube embed / thumbnail URLs. */

const VIDEO_ID = /^[\w-]{11}$/;

export function parseYouTubeVideoId(raw: string | null | undefined): string | null {
  if (!raw) return null;
  let parsed: URL;
  try {
    parsed = new URL(raw.trim());
  } catch {
    return null;
  }
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return null;
  const host = parsed.hostname.replace(/^www\./, "").toLowerCase();

  if (host === "youtu.be") {
    const id = parsed.pathname.split("/").filter(Boolean)[0] ?? "";
    return VIDEO_ID.test(id) ? id : null;
  }

  if (
    host === "youtube.com" ||
    host === "m.youtube.com" ||
    host === "music.youtube.com" ||
    host === "youtube-nocookie.com"
  ) {
    const watch = parsed.searchParams.get("v");
    if (watch && VIDEO_ID.test(watch)) return watch;

    const parts = parsed.pathname.split("/").filter(Boolean);
    if (parts[0] === "embed" || parts[0] === "shorts" || parts[0] === "live" || parts[0] === "v") {
      const id = parts[1] ?? "";
      return VIDEO_ID.test(id) ? id : null;
    }
  }

  return null;
}

export function youtubeThumbnailUrl(videoId: string): string {
  return `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`;
}

export function youtubeEmbedUrl(videoId: string, autoplay = false): string {
  const params = new URLSearchParams({
    rel: "0",
    modestbranding: "1",
    playsinline: "1",
  });
  if (autoplay) params.set("autoplay", "1");
  return `https://www.youtube-nocookie.com/embed/${videoId}?${params.toString()}`;
}

export function youtubeWatchUrl(videoId: string): string {
  return `https://www.youtube.com/watch?v=${videoId}`;
}
