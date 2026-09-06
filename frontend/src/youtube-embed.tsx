import { useState } from "react";

import {
  parseYouTubeVideoId,
  youtubeEmbedUrl,
  youtubeThumbnailUrl,
  youtubeWatchUrl,
} from "./youtube";

export function YouTubeEmbed({
  videoId,
  title = "Видео YouTube",
}: {
  videoId: string;
  title?: string;
}) {
  const [playing, setPlaying] = useState(false);

  if (playing) {
    return (
      <div className="youtube-embed is-playing">
        <iframe
          className="youtube-frame"
          src={youtubeEmbedUrl(videoId, true)}
          title={title}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
          referrerPolicy="strict-origin-when-cross-origin"
        />
      </div>
    );
  }

  return (
    <figure className="youtube-embed">
      <button
        type="button"
        className="youtube-poster"
        onClick={() => setPlaying(true)}
        aria-label={`Смотреть: ${title}`}
      >
        <img
          className="youtube-thumb"
          src={youtubeThumbnailUrl(videoId)}
          alt=""
          loading="lazy"
          decoding="async"
        />
        <span className="youtube-play" aria-hidden>
          ▶
        </span>
      </button>
      <figcaption className="youtube-caption">
        <a href={youtubeWatchUrl(videoId)} target="_blank" rel="noopener noreferrer">
          Открыть на YouTube
        </a>
      </figcaption>
    </figure>
  );
}

export function collectYouTubeIds(urls: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const ids: string[] = [];
  for (const url of urls) {
    const id = parseYouTubeVideoId(url);
    if (!id || seen.has(id)) continue;
    seen.add(id);
    ids.push(id);
  }
  return ids;
}
