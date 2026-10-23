#!/usr/bin/env python3
"""Build feed.xml (RSS 2.0) + feed.json (JSON Feed 1.1) for the FB360 panorama upstream.

Source of truth: items.json in this directory. NEVER edit feed.xml/feed.json by hand.
Each item (from the collection pipeline) must provide:
  id, title, location, country, theme, author, license, license_url, source_url,
  original_download_url, original_width, original_height, shoot_date,
  finished_file (basename, file must exist under media/), caption_en, caption_fr, caption_zh,
  pubDate (YYYY-MM-DD, Beijing collection date)
download_url is derived: RAW_BASE + media/<finished_file>.
"""
import json, os, sys, hashlib
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_BASE = "https://raw.githubusercontent.com/TikerBin/fb360-upstream/main/"
BJ = timezone(timedelta(hours=8))
REQUIRED = ["id", "title", "location", "country", "theme", "author", "license",
            "license_url", "source_url", "original_download_url", "finished_file",
            "caption_en", "caption_fr", "caption_zh", "pubDate"]
MAX_ITEMS = 420

def load_items():
    with open(os.path.join(HERE, "items.json"), encoding="utf-8") as f:
        items = json.load(f)["items"]
    seen = set()
    for it in items:
        for k in REQUIRED:
            if k not in it or (it[k] == "" and k != "shoot_date"):
                raise SystemExit(f"item {it.get('id','?')}: missing/empty field {k}")
        if it["id"] in seen:
            raise SystemExit(f"duplicate id {it['id']}")
        seen.add(it["id"])
        media = os.path.join(HERE, "media", it["finished_file"])
        if not os.path.isfile(media):
            raise SystemExit(f"item {it['id']}: media file missing: {it['finished_file']}")
        it["_size"] = os.path.getsize(media)
        it["_sha256"] = hashlib.sha256(open(media, "rb").read()).hexdigest()
        it["_download_url"] = RAW_BASE + "media/" + it["finished_file"]
        d = datetime.strptime(it["pubDate"], "%Y-%m-%d").replace(tzinfo=BJ)
        if d > datetime.now(BJ) + timedelta(days=1):
            raise SystemExit(f"item {it['id']}: pubDate in the future: {it['pubDate']}")
        it["_pub_dt"] = d
    items.sort(key=lambda x: (x["pubDate"], x["id"]), reverse=True)
    return items[:MAX_ITEMS]

def build_rss(items):
    now_rfc = format_datetime(datetime.now(BJ))
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">',
           "<channel>",
           "<title>FB360 Panorama Upstream</title>",
           f"<link>{RAW_BASE}</link>",
           "<description>Free-license 360° equirectangular landscape panoramas, Facebook-360 ready (6000×3000, GPano). Captions in English, per-item license + attribution.</description>",
           "<language>en</language>",
           f"<lastBuildDate>{now_rfc}</lastBuildDate>"]
    for it in items:
        pub_rfc = format_datetime(it["_pub_dt"])
        full = (f"{it['caption_en']}\n\n"
                f"Author: {it['author']} · License: {it['license']} ({it['license_url']}) · "
                f"Location: {it['location']}, {it['country']} · Theme: {it['theme']} · "
                f"Original: {it['original_width']}×{it['original_height']} · Shoot date: {it.get('shoot_date','')}")
        out += ["<item>",
                f"<title>{escape(it['title'])}</title>",
                f"<link>{escape(it['source_url'])}</link>",
                f'<guid isPermaLink="false">{escape(it["id"])}</guid>',
                f"<pubDate>{pub_rfc}</pubDate>",
                f"<category>{escape(it['theme'])}</category>",
                f"<description>{escape(it['caption_en'])}</description>",
                f"<content:encoded><![CDATA[{full}]]></content:encoded>",
                f'<enclosure url="{escape(it["_download_url"])}" length="{it["_size"]}" type="image/jpeg"/>',
                "</item>"]
    out += ["</channel>", "</rss>"]
    with open(os.path.join(HERE, "feed.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

def build_json(items):
    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "FB360 Panorama Upstream",
        "home_page_url": RAW_BASE,
        "feed_url": RAW_BASE + "feed.json",
        "description": "Free-license 360° equirectangular landscape panoramas, Facebook-360 ready (6000×3000, GPano).",
        "items": []
    }
    for it in items:
        feed["items"].append({
            "id": it["id"],
            "url": it["source_url"],
            "title": it["title"],
            "content_text": it["caption_en"],
            "summary": it["caption_en"],
            "date_published": it["_pub_dt"].isoformat(),
            "tags": [it["theme"]],
            "attachments": [{"url": it["_download_url"], "mime_type": "image/jpeg", "size_in_bytes": it["_size"]}],
            "_author": it["author"], "_license": it["license"], "_license_url": it["license_url"],
            "_source_url": it["source_url"], "_original_download_url": it["original_download_url"],
            "_original_width": it.get("original_width"), "_original_height": it.get("original_height"),
            "_location": it["location"], "_country": it["country"], "_shoot_date": it.get("shoot_date", ""),
            "_spec": "6000x3000 equirectangular JPEG, GPano XMP + RICOH THETA S EXIF",
            "_sha256": it["_sha256"],
        })
    with open(os.path.join(HERE, "feed.json"), "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    items = load_items()
    build_rss(items)
    build_json(items)
    # self-check: both outputs must parse
    import xml.dom.minidom
    xml.dom.minidom.parse(os.path.join(HERE, "feed.xml"))
    json.load(open(os.path.join(HERE, "feed.json"), encoding="utf-8"))
    print(f"OK: {len(items)} items -> feed.xml + feed.json")
