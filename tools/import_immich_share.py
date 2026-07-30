#!/usr/bin/env python3
"""Import photographs from an Immich public share into FieldStation galleries.

Uses Immich's shared-link and thumbnail endpoints, so no API key or image
conversion dependency is required. The script runs on the same computer as
Immich; a localhost share URL therefore works here even though it cannot be
opened from outside that computer.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


def fetch_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "FieldStation-Immich-Bridge/1.0"})
    with urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_binary(url: str) -> tuple[bytes, str]:
    req = Request(url, headers={"User-Agent": "FieldStation-Immich-Bridge/1.0"})
    with urlopen(req, timeout=60) as response:
        return response.read(), response.headers.get_content_type()


def extension_for(content_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(content_type, mimetypes.guess_extension(content_type) or ".jpg")


def load_gallery_data(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"=\s*(\{.*\})\s*;\s*$", text, re.S)
    if not match:
        raise RuntimeError(f"Could not parse {path}")
    return json.loads(match.group(1))


def save_gallery_data(path: Path, data: dict) -> None:
    path.write_text(
        "// Full Circle Paradise photographic archive\n"
        "window.FIELDSTATION_GALLERIES = "
        + json.dumps(data, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )


def classify(asset: dict) -> str:
    exif = asset.get("exifInfo") or {}
    tags = " ".join(str(tag.get("name", "")) for tag in (asset.get("tags") or []))
    haystack = " ".join(
        [
            str(asset.get("originalFileName", "")),
            str(exif.get("description", "")),
            tags,
        ]
    ).lower()
    rules = [
        ("climate", ("fire", "burn", "smoke", "frost", "storm", "climate")),
        ("water", ("water", "tank", "well", "pond", "swale", "greywater", "rain")),
        ("buildings", ("build", "cabin", "house", "dome", "workshop", "barn", "oven", "construction")),
        ("social", ("meeting", "dinner", "supper", "community", "group", "party", "ceremony", "circle")),
        ("design", ("map", "design", "workbook", "drawing", "plan")),
        ("food", ("garden", "harvest", "fruit", "orchard", "food", "chicken", "goat", "cow", "egg", "bee", "hive", "compost", "seed", "plant")),
    ]
    for category, words in rules:
        if any(word in haystack for word in words):
            return category
    return "tour"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("share_url")
    args = parser.parse_args()

    project = args.project.expanduser().resolve()
    gallery_path = project / "gallery-data.js"
    if not gallery_path.exists():
        raise RuntimeError(f"Missing gallery data: {gallery_path}")

    parsed = urlparse(args.share_url)
    match = re.search(r"/share/([^/?#]+)", parsed.path)
    if not parsed.scheme or not parsed.netloc or not match:
        raise RuntimeError("The Immich URL must look like http://host:port/share/KEY")

    key = match.group(1)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    encoded_key = quote(key, safe="")
    shared = fetch_json(f"{origin}/api/shared-links/me?key={encoded_key}")
    assets = shared.get("assets") or (shared.get("album") or {}).get("assets") or []
    assets = [asset for asset in assets if str(asset.get("type", "IMAGE")).upper() == "IMAGE"]
    if not assets:
        print("Immich share contains no still images.")
        return 0

    full_dir = project / "images" / "immich-final" / "full"
    thumb_dir = project / "images" / "immich-final" / "thumbs"
    full_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)

    galleries = load_gallery_data(gallery_path)
    known_ids = {
        item.get("immichAssetId")
        for items in galleries.values()
        for item in items
        if item.get("immichAssetId")
    }

    added = 0
    for index, asset in enumerate(assets, 1):
        asset_id = str(asset.get("id", ""))
        if not asset_id or asset_id in known_ids:
            continue
        full_bytes, full_type = fetch_binary(
            f"{origin}/api/assets/{quote(asset_id)}/thumbnail?size=preview&key={encoded_key}"
        )
        thumb_bytes, thumb_type = fetch_binary(
            f"{origin}/api/assets/{quote(asset_id)}/thumbnail?size=thumbnail&key={encoded_key}"
        )
        full_ext = extension_for(full_type)
        thumb_ext = extension_for(thumb_type)
        stem = f"immich-{asset_id}"
        full_rel = f"images/immich-final/full/{stem}{full_ext}"
        thumb_rel = f"images/immich-final/thumbs/{stem}{thumb_ext}"
        (project / full_rel).write_bytes(full_bytes)
        (project / thumb_rel).write_bytes(thumb_bytes)

        exif = asset.get("exifInfo") or {}
        description = str(exif.get("description") or "").strip()
        filename = str(asset.get("originalFileName") or f"Immich photograph {index}")
        caption = description or f"Full Circle archive · {filename}"
        category = classify(asset)
        galleries.setdefault(category, []).append(
            {
                "src": full_rel,
                "thumb": thumb_rel,
                "alt": caption,
                "caption": caption,
                "immichAssetId": asset_id,
            }
        )
        known_ids.add(asset_id)
        added += 1

    save_gallery_data(gallery_path, galleries)
    print(f"Imported {added} Immich photographs into the FieldStation galleries.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Immich import skipped: {exc}", file=sys.stderr)
        raise SystemExit(1)
