import { describe, expect, it } from "vitest";

import { collectYouTubeIds } from "./youtube-embed";
import { parseYouTubeVideoId, youtubeEmbedUrl, youtubeThumbnailUrl } from "./youtube";

describe("parseYouTubeVideoId", () => {
  it("parses common YouTube URL shapes", () => {
    expect(parseYouTubeVideoId("https://www.youtube.com/watch?v=dQw4w9WgXcQ")).toBe("dQw4w9WgXcQ");
    expect(parseYouTubeVideoId("https://youtu.be/dQw4w9WgXcQ")).toBe("dQw4w9WgXcQ");
    expect(parseYouTubeVideoId("https://www.youtube.com/embed/dQw4w9WgXcQ")).toBe("dQw4w9WgXcQ");
    expect(parseYouTubeVideoId("https://www.youtube.com/shorts/dQw4w9WgXcQ")).toBe("dQw4w9WgXcQ");
    expect(parseYouTubeVideoId("https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=12")).toBe(
      "dQw4w9WgXcQ",
    );
  });

  it("rejects non-YouTube URLs", () => {
    expect(parseYouTubeVideoId("https://example.com/watch?v=dQw4w9WgXcQ")).toBeNull();
    expect(parseYouTubeVideoId("javascript:alert(1)")).toBeNull();
    expect(parseYouTubeVideoId("not a url")).toBeNull();
  });
});

describe("youtube helpers", () => {
  it("builds thumbnail and embed URLs", () => {
    expect(youtubeThumbnailUrl("dQw4w9WgXcQ")).toContain("dQw4w9WgXcQ");
    expect(youtubeEmbedUrl("dQw4w9WgXcQ", true)).toContain("youtube-nocookie.com");
    expect(youtubeEmbedUrl("dQw4w9WgXcQ", true)).toContain("autoplay=1");
  });

  it("dedupes collected ids", () => {
    expect(
      collectYouTubeIds([
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://example.com",
      ]),
    ).toEqual(["dQw4w9WgXcQ"]);
  });
});
