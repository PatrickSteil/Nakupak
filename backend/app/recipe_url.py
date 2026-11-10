"""Fetch a recipe page safely and read its schema.org/Recipe JSON-LD (no LLM)."""
import asyncio
import html
import ipaddress
import json
import re
import socket
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from .utils import image_extension

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
MAX_PAGE_BYTES = 3 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Nakupak recipe import)"}


class FetchError(Exception):
    pass


async def _check_public(url: str) -> None:
    """Reject non-http(s) URLs and hosts resolving to private/loopback/link-local addresses."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("Only http(s) URLs are supported")
    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo, parts.hostname, parts.port or (443 if parts.scheme == "https" else 80)
        )
    except socket.gaierror:
        raise FetchError("Could not resolve the host")
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise FetchError("This address is not allowed")


async def safe_get(url: str, max_bytes: int) -> tuple[bytes, str | None]:
    """GET with SSRF protection: every redirect hop is validated, size is capped."""
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=False, headers=_HEADERS) as client:
        for _ in range(5):
            await _check_public(url)
            try:
                async with client.stream("GET", url) as resp:
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            raise FetchError("Bad redirect")
                        url = urljoin(url, location)
                        continue
                    if resp.status_code >= 400:
                        raise FetchError(f"The page returned HTTP {resp.status_code}")
                    body = bytearray()
                    async for chunk in resp.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > max_bytes:
                            raise FetchError("The page is too large")
                    return bytes(body), resp.headers.get("content-type")
            except httpx.HTTPError as e:
                raise FetchError(f"Failed to fetch the page: {e.__class__.__name__}")
        raise FetchError("Too many redirects")


_LD_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.S | re.I
)


def _nodes(data):
    if isinstance(data, list):
        for d in data:
            yield from _nodes(d)
    elif isinstance(data, dict):
        yield data
        if "@graph" in data:
            yield from _nodes(data["@graph"])


def _is_recipe(node: dict) -> bool:
    t = node.get("@type")
    return t == "Recipe" or (isinstance(t, list) and "Recipe" in t)


def _clean(text) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(text)))
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def _instructions(raw) -> list[str]:
    if isinstance(raw, str):
        parts = [p for p in re.split(r"\n+", _clean_keep_newlines(raw)) if p.strip()]
        return [_clean(p) for p in parts]
    steps = []
    if isinstance(raw, list):
        for el in raw:
            steps.extend(_instructions(el))
    elif isinstance(raw, dict):
        if "itemListElement" in raw:
            steps.extend(_instructions(raw["itemListElement"]))
        elif raw.get("text"):
            steps.append(_clean(raw["text"]))
        elif raw.get("name"):
            steps.append(_clean(raw["name"]))
    return [s for s in steps if s]


def _clean_keep_newlines(text: str) -> str:
    return html.unescape(re.sub(r"<br\s*/?>|</p>|</li>", "\n", text, flags=re.I))


def _first_image(raw) -> str | None:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list) and raw:
        return _first_image(raw[0])
    if isinstance(raw, dict):
        return raw.get("url")
    return None


def extract_recipe(page: str, source_url: str) -> dict | None:
    """Return {name, description, image_url, ingredients_text} or None if no Recipe found."""
    for block in _LD_RE.findall(page):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for node in _nodes(data):
            if not _is_recipe(node):
                continue
            ingredients = node.get("recipeIngredient") or node.get("ingredients") or []
            if isinstance(ingredients, str):
                ingredients = [ingredients]
            desc = _clean(node.get("description") or "")
            steps = _instructions(node.get("recipeInstructions") or [])
            parts = []
            if desc:
                parts.append(desc)
            if steps:
                parts.append("\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1)))
            parts.append(f"[{source_url}]({source_url})")
            image = _first_image(node.get("image"))
            return {
                "name": _clean(node.get("name") or ""),
                "description": "\n\n".join(parts),
                "image_url": urljoin(source_url, image) if image else None,
                "ingredients_text": "\n".join(_clean(i) for i in ingredients if _clean(i)),
            }
    return None


async def download_image(url: str) -> str | None:
    """Store a remote image locally; returns the /api/uploads path or None on any problem."""
    try:
        body, content_type = await safe_get(url, MAX_IMAGE_BYTES)
    except FetchError:
        return None
    ext = image_extension(content_type)
    if ext is None:
        return None
    filename = f"{uuid.uuid4().hex}{ext}"
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOADS_DIR / filename).write_bytes(body)
    return f"/api/uploads/{filename}"
