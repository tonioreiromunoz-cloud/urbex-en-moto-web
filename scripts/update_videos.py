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
CHANNEL_URL = "https://www.youtube.com/@UrbexenMotoTyJ"
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "videos.json"
INDEX = ROOT / "index.html"
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

    # Cifras del canal: si no se pueden leer, se conservan las anteriores.
    old_channel = json.loads(old_text).get("channel", {}) if old_text else {}
    channel = {**old_channel, **channel_stats()}

    data = {"channelId": CHANNEL_ID, "channel": channel, "videos": videos}
    new_text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    changed_html = update_share_image(videos)
    if new_text == old_text and not changed_html:
        print("Sin cambios.")
        return 0
    if new_text != old_text:
        OUT.write_text(new_text, encoding="utf-8")
    longs = sum(1 for v in videos if not v.get("short"))
    print(f"videos.json actualizado: {len(videos)} entradas ({longs} vídeos, {len(videos) - longs} Shorts), canal: {channel}.")
    return 0


def to_number(text: str) -> int | None:
    """'112' -> 112, '1.2K' -> 1200, '1,5 mil' -> 1500, '3.4M' -> 3400000."""
    m = re.match(r"\s*([\d.,]+)\s*(K|M|mil|k|m)?\b", text)
    if not m:
        return None
    num, unit = m.group(1), (m.group(2) or "").lower()
    if unit:
        value = float(num.replace(",", "."))
        return int(round(value * (1_000_000 if unit == "m" else 1000)))
    digits = re.sub(r"[.,]", "", num)
    return int(digits) if digits.isdigit() else None


def channel_stats() -> dict:
    """Suscriptores y número de vídeos leídos de la página pública del canal."""
    try:
        req = urllib.request.Request(
            CHANNEL_URL,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
                     "Accept-Language": "en-US,en;q=0.9"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"No se pudo leer la página del canal: {e}")
        return {}
    out = {}
    m = re.search(r'"([\d.,]+\s*[KMkm]?)\s+subscribers"', html)
    if m and to_number(m.group(1)) is not None:
        out["subscribers"] = to_number(m.group(1))
    m = re.search(r'"([\d.,]+)\s+videos"', html)
    if m and to_number(m.group(1)) is not None:
        out["videoCount"] = to_number(m.group(1))
    return out


def update_share_image(videos: list[dict]) -> bool:
    """Pone la miniatura del último vídeo largo como imagen al compartir (og:image y twitter:image)."""
    if not INDEX.exists():
        return False
    longs = [v for v in videos if not v.get("short")]
    if not longs:
        return False
    vid = longs[0]["id"]
    image = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"
    try:
        with urllib.request.urlopen(urllib.request.Request(image, method="HEAD"), timeout=20) as resp:
            if resp.status != 200:
                raise ValueError
    except Exception:
        image = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    html = INDEX.read_text(encoding="utf-8")
    new = re.sub(
        r'(<meta (?:property="og:image"|name="twitter:image") content=")https://i\.ytimg\.com/vi/[^"]+(")',
        lambda m: m.group(1) + image + m.group(2), html)
    if new != html:
        INDEX.write_text(new, encoding="utf-8")
        print(f"Imagen para compartir actualizada: {image}")
        return True
    return False


if __name__ == "__main__":
    sys.exit(main())
