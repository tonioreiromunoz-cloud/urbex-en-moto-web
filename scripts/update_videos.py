#!/usr/bin/env python3
"""Lee el feed RSS público del canal y regenera videos.json.

No necesita clave de API. El feed de YouTube devuelve las 15 subidas más
recientes del canal (vídeos y Shorts). Solo reescribe el archivo si algo cambia.
"""
import json
import pathlib
import sys
import urllib.request
import xml.etree.ElementTree as ET

CHANNEL_ID = "UCIa1rkAjGToYNpQAXzt3xgA"
FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
OUT = pathlib.Path(__file__).resolve().parent.parent / "videos.json"

NS = {
    "a": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


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
        videos.append({
            "id": vid,
            "title": (entry.findtext("a:title", namespaces=NS) or "").strip(),
            "url": link,
            "published": entry.findtext("a:published", namespaces=NS),
            "views": views,
            "short": "/shorts/" in link,
            "description": desc.split("\n")[0][:220],
        })
    videos.sort(key=lambda v: v["published"] or "", reverse=True)
    return videos


def main() -> int:
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "urbex-en-moto-web/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        xml_text = resp.read().decode("utf-8")
    videos = parse(xml_text)
    if not videos:
        print("El feed no devolvió vídeos; no toco videos.json.")
        return 1
    new = json.dumps({"channelId": CHANNEL_ID, "videos": videos}, ensure_ascii=False, indent=2) + "\n"
    old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
    if new == old:
        print("Sin cambios.")
        return 0
    OUT.write_text(new, encoding="utf-8")
    print(f"videos.json actualizado: {len(videos)} entradas, la última es «{videos[0]['title']}».")
    return 0


if __name__ == "__main__":
    sys.exit(main())
