#!/usr/bin/env python3
"""Lee el feed RSS público del canal y actualiza videos.json.

No necesita clave de API. El feed de YouTube solo devuelve las 15 subidas más
recientes (vídeos y Shorts), así que el script ACUMULA: conserva lo que ya había
en videos.json, actualiza lo que vuelve a salir en el feed y añade lo nuevo.
Solo reescribe el archivo si algo cambia.
"""
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

CHANNEL_ID = "UCIa1rkAjGToYNpQAXzt3xgA"
FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
OUT = pathlib.Path(__file__).resolve().parent.parent / "videos.json"
MAX_ITEMS = 80  # cuántas entradas guardar como máximo

NS = {
    "a": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "urbex-en-moto-web/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def parse(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    videos = []
    for entry in root.findall("a:entry", NS):
        vid = entry.findtext("yt:videoId", namespaces=NS)
        if not vid:
            continue
        link_el = entry.find("a:link", NS)
        link = link_el.get("href") if link_el is not None else f"https://www.youtube.com/watch?v={vid}"
        group = entry.find("media:group", NS)
        desc = ""
        views = None
        if group is not None:
            desc = (group.findtext("media:description", namespaces=NS) or "").strip()
            stats = group.find("media:community/media:statistics", NS)
            if stats is not None and stats.get("views", "").isdigit():
                views = int(stats.get("views"))
        raw_title = (entry.findtext("a:title", namespaces=NS) or "").strip()
        # Los Shorts traen hashtags en el título: en la web se muestran sin ellos.
        title = re.sub(r"\s+", " ", re.sub(r"#\w+", "", raw_title)).strip() or raw_title
        videos.append({
            "id": vid,
            "title": title,
            "url": link,
            "published": entry.findtext("a:published", namespaces=NS),
            "views": views,
            "short": "/shorts/" in link,
            "description": desc.split("\n")[0][:220],
            "checked": True,
        })
    return videos


def original_title(vid: str) -> str | None:
    """Título original de un vídeo que ya no sale en el feed (vía oEmbed)."""
    url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(f"https://www.youtube.com/watch?v={vid}")
    try:
        return json.loads(fetch(url)).get("title")
    except Exception:
        return None


def main() -> int:
    feed = parse(fetch(FEED_URL))
    if not feed:
        print("El feed no devolvió vídeos; no toco videos.json.")
        return 1

    old_text = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
    old = json.loads(old_text).get("videos", []) if old_text else []
    by_id = {v["id"]: v for v in old}
    for v in feed:
        by_id[v["id"]] = {**by_id.get(v["id"], {}), **v}

    # Entradas antiguas que nunca salieron en el feed: corregir el título una vez.
    for v in by_id.values():
        if not v.get("checked"):
            title = original_title(v["id"])
            if title:
                v["title"] = title
            v["checked"] = True

    videos = sorted(by_id.values(), key=lambda v: v.get("published") or "", reverse=True)[:MAX_ITEMS]
    new_text = json.dumps({"channelId": CHANNEL_ID, "videos": videos}, ensure_ascii=False, indent=2) + "\n"
    if new_text == old_text:
        print("Sin cambios.")
        return 0
    OUT.write_text(new_text, encoding="utf-8")
    longs = sum(1 for v in videos if not v.get("short"))
    print(f"videos.json actualizado: {len(videos)} entradas ({longs} vídeos, {len(videos) - longs} Shorts).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
