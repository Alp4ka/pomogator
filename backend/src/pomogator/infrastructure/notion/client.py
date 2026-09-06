import base64
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

import httpx

from pomogator.domain.content import AccessLevel, parse_access_title

NOTION_API = "https://api.notion.com/v1"
_PAGE_ID = re.compile(r"([0-9a-f]{32})", re.IGNORECASE)
_YOUTUBE_HOSTS = {
    "youtu.be",
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
_YOUTUBE_ID = re.compile(r"^[\w-]{11}$")


@dataclass(slots=True)
class ImportedImage:
    sha256: str
    mime_type: str
    data: bytes


@dataclass(slots=True)
class ImportedPage:
    notion_page_id: str
    title: str
    access_level: AccessLevel
    document: list[dict[str, Any]]
    children: list["ImportedPage"] = field(default_factory=list)


@dataclass(slots=True)
class ImportedCountry:
    page_id: str
    slug: str
    flag: str
    root: ImportedPage
    images: list[ImportedImage]


class NotionClient:
    def __init__(self, token: str, http: httpx.AsyncClient | None = None):
        self.http = http or httpx.AsyncClient(timeout=30, follow_redirects=True)
        self.headers = {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"}
        self.images: dict[str, ImportedImage] = {}

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self.http.get(f"{NOTION_API}{path}", headers=self.headers, params=params)
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def _all_blocks(self, block_id: str) -> list[dict[str, Any]]:
        results, cursor = [], None
        while True:
            payload = await self._get(
                f"/blocks/{block_id}/children",
                {"page_size": 100, "start_cursor": cursor} if cursor else {"page_size": 100},
            )
            results.extend(payload["results"])
            if not payload.get("has_more"):
                return results
            cursor = payload["next_cursor"]

    @staticmethod
    def _plain(rich: list[dict[str, Any]]) -> str:
        return "".join(part.get("plain_text", "") for part in rich)

    @staticmethod
    def notion_page_id(url: str) -> str | None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return None
        host = (parsed.hostname or "").lower()
        if host not in {
            "notion.so",
            "www.notion.so",
            "notion.site",
            "www.notion.site",
        } and not host.endswith(".notion.site"):
            return None
        match = _PAGE_ID.search(parsed.path.replace("-", ""))
        return match.group(1).lower() if match else None

    @staticmethod
    def safe_external_url(url: str) -> str | None:
        if any(ord(char) < 32 for char in url):
            return None
        parsed = urlparse(url)
        if (
            parsed.scheme == "https"
            and parsed.hostname
            and not parsed.username
            and not parsed.password
        ):
            return url
        if parsed.scheme in {"mailto", "tel"}:
            return url
        return None

    @staticmethod
    def youtube_video_id(url: str) -> str | None:
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        host = parsed.hostname.lower()
        if host not in _YOUTUBE_HOSTS:
            return None
        if host == "youtu.be":
            candidate = parsed.path.strip("/").split("/", 1)[0]
            return candidate if _YOUTUBE_ID.match(candidate) else None
        query_id = (parse_qs(parsed.query).get("v") or [""])[0]
        if _YOUTUBE_ID.match(query_id):
            return query_id
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"embed", "shorts", "live", "v"}:
            candidate = parts[1]
            return candidate if _YOUTUBE_ID.match(candidate) else None
        return None

    def _youtube_block(self, url: str, caption: str = "") -> dict[str, Any] | None:
        safe = self.safe_external_url(url)
        if not safe:
            return None
        video_id = self.youtube_video_id(safe)
        if not video_id:
            return None
        item: dict[str, Any] = {"type": "youtube", "video_id": video_id, "url": safe}
        if caption:
            item["caption"] = caption
        return item

    def _media_url_block(self, block: dict[str, Any]) -> dict[str, Any] | None:
        kind = block["type"]
        value = block.get(kind, {})
        if kind == "video":
            source = value.get(value.get("type"), {}) if value.get("type") else {}
            url = source.get("url", "")
            caption = self._plain(value.get("caption", []))
            return self._youtube_block(url, caption)
        if kind == "embed":
            return self._youtube_block(value.get("url", ""))
        if kind == "bookmark":
            caption = self._plain(value.get("caption", []))
            return self._youtube_block(value.get("url", ""), caption)
        return None

    async def _table(self, block: dict[str, Any]) -> dict[str, Any]:
        value = block.get("table", {})
        rows: list[list[list[dict[str, Any]]]] = []
        for child in await self._all_blocks(block["id"]):
            if child.get("type") != "table_row":
                continue
            cells = child.get("table_row", {}).get("cells", [])
            rows.append([await self._rich(cell) for cell in cells])
        return {
            "type": "table",
            "has_column_header": bool(value.get("has_column_header")),
            "has_row_header": bool(value.get("has_row_header")),
            "rows": rows,
        }

    async def _rich(self, rich: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output = []
        for part in rich:
            text = part.get("plain_text", "")
            href = part.get("href")
            item: dict[str, Any] = {"text": text, "annotations": part.get("annotations", {})}
            if href:
                notion_id = self.notion_page_id(href)
                if notion_id:
                    item["link"] = {"type": "internal", "notion_page_id": notion_id}
                elif safe_url := self.safe_external_url(href):
                    item["link"] = {"type": "external", "url": safe_url}
            output.append(item)
        return output

    async def _image(self, block: dict[str, Any]) -> dict[str, Any]:
        data = block["image"]
        url = data[data["type"]]["url"]
        if ";base64," in url and (url.startswith("data:") or url.startswith("/image/")):
            header, encoded = url.split(";base64,", 1)
            raw = base64.b64decode(encoded, validate=True)
            mime = header.removeprefix("data:").removeprefix("/")
        else:
            response = await self.http.get(url)
            response.raise_for_status()
            raw = response.content
            mime = response.headers.get("content-type", "application/octet-stream").split(";")[0]
        if len(raw) > 10 * 1024 * 1024:
            raise ValueError("Notion image exceeds 10 MiB")
        if not mime.startswith("image/"):
            raise ValueError("Notion asset is not an image")
        digest = hashlib.sha256(raw).hexdigest()
        self.images[digest] = ImportedImage(digest, mime, raw)
        return {
            "type": "image",
            "image_id": digest,
            "caption": self._plain(data.get("caption", [])),
        }

    async def _database_pages(self, database_id: str) -> list[str]:
        page_ids: list[str] = []
        cursor: str | None = None
        while True:
            body: dict[str, Any] = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            response = await self.http.post(
                f"{NOTION_API}/databases/{database_id}/query",
                headers=self.headers,
                json=body,
            )
            response.raise_for_status()
            payload = cast(dict[str, Any], response.json())
            page_ids.extend(item["id"] for item in payload.get("results", []))
            if not payload.get("has_more"):
                return page_ids
            cursor = payload.get("next_cursor")

    async def _blocks_document(self, block_id: str) -> list[dict[str, Any]]:
        document: list[dict[str, Any]] = []
        for block in await self._all_blocks(block_id):
            kind = block["type"]
            value = block.get(kind, {})
            if kind == "image":
                document.append(await self._image(block))
            elif kind == "table":
                document.append(await self._table(block))
            elif kind == "table_row":
                continue
            elif kind in {"video", "embed", "bookmark"}:
                media = self._media_url_block(block)
                if media:
                    document.append(media)
            else:
                rich = value.get("rich_text", [])
                if rich or kind in {"divider", "to_do", "code", "callout"}:
                    item: dict[str, Any] = {
                        "type": kind,
                        "rich_text": await self._rich(rich),
                        "checked": value.get("checked"),
                    }
                    if kind == "code":
                        item["language"] = value.get("language", "plain text")
                    if kind == "callout":
                        item["icon"] = (value.get("icon") or {}).get("emoji")
                    document.append(item)
            if block.get("has_children") and kind not in {"table", "table_row"}:
                document.extend(await self._blocks_document(block["id"]))
        return document

    async def _page(self, page_id: str, inherited: AccessLevel) -> ImportedPage:
        meta = await self._get(f"/pages/{page_id}")
        title_rich: list[dict[str, Any]] = next(
            (
                v.get("title", [])
                for v in meta.get("properties", {}).values()
                if v.get("type") == "title"
            ),
            [],
        )
        title, level = parse_access_title(self._plain(title_rich) or "Без названия", inherited)
        document, children = [], []
        for block in await self._all_blocks(page_id):
            kind = block["type"]
            value = block.get(kind, {})
            if kind == "child_page":
                children.append(await self._page(block["id"], level))
                continue
            if kind == "child_database":
                for child_id in await self._database_pages(block["id"]):
                    children.append(await self._page(child_id, level))
                continue
            if kind == "image":
                document.append(await self._image(block))
                continue
            if kind == "table":
                document.append(await self._table(block))
                continue
            if kind == "table_row":
                continue
            if kind in {"video", "embed", "bookmark"}:
                media = self._media_url_block(block)
                if media:
                    document.append(media)
                continue
            rich = value.get("rich_text", [])
            if rich or kind in {"divider", "to_do", "code", "callout"}:
                item: dict[str, Any] = {
                    "type": kind,
                    "rich_text": await self._rich(rich),
                    "checked": value.get("checked"),
                }
                if kind == "code":
                    item["language"] = value.get("language", "plain text")
                if kind == "callout":
                    item["icon"] = (value.get("icon") or {}).get("emoji")
                document.append(item)
            if block.get("has_children") and kind not in {"child_page", "table"}:
                nested = await self._blocks_document(block["id"])
                document.extend(nested)
        return ImportedPage(page_id.replace("-", ""), title, level, document, children)

    async def import_country(self, page_id: str, slug: str, fallback_flag: str) -> ImportedCountry:
        self.images = {}
        root = await self._page(page_id, AccessLevel.FREE)
        meta = await self._get(f"/pages/{page_id}")
        icon = meta.get("icon") or {}
        flag = icon.get("emoji", fallback_flag) if icon.get("type") == "emoji" else fallback_flag
        return ImportedCountry(
            page_id.replace("-", ""), slug, flag, root, list(self.images.values())
        )
