#!/usr/bin/env python3
"""Local photo importer for the Full Circle Paradise gallery system.

Runs only on 127.0.0.1. Photos are processed locally and are never uploaded
anywhere except into the website project folder on this computer.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import tempfile
import threading
import time
import unicodedata
import urllib.parse
import webbrowser
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
except ImportError as exc:
    raise SystemExit(
        "The Photo Importer needs Pillow. Install it once with:\n"
        "  sudo apt install python3-pil"
    ) from exc

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
SITE_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = SITE_ROOT / "gallery-data.js"
GALLERY_ROOT = SITE_ROOT / "images" / "galleries"
CATEGORIES = {
    "story": "The Farm / Story",
    "tour": "Site Tour",
    "climate": "Climate & Ecology",
    "water": "Water",
    "food": "Food & Soil",
    "buildings": "Buildings & Energy",
    "social": "Social Permaculture",
    "design": "The Design",
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".heic", ".heif"}
MAX_UPLOAD_BYTES = 300 * 1024 * 1024


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or f"photo-{int(time.time())}"


def humanize(value: str) -> str:
    value = re.sub(r"[_-]+", " ", Path(value).stem)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:1].upper() + value[1:] if value else "Full Circle Paradise photograph"


def load_gallery_data() -> dict[str, list[dict[str, str]]]:
    if not DATA_FILE.exists():
        return {key: [] for key in CATEGORIES}
    text = DATA_FILE.read_text(encoding="utf-8")
    match = re.search(r"window\.FIELDSTATION_GALLERIES\s*=\s*(\{.*\})\s*;\s*$", text, re.S)
    if not match:
        raise RuntimeError(f"Could not read gallery data from {DATA_FILE}")
    data = json.loads(match.group(1))
    for key in CATEGORIES:
        data.setdefault(key, [])
    return data


def save_gallery_data(data: dict[str, list[dict[str, str]]]) -> None:
    text = (
        "// Generated and updated by tools/photo_importer.py\n"
        "window.FIELDSTATION_GALLERIES = "
        + json.dumps(data, indent=2, ensure_ascii=False)
        + ";\n"
    )
    temp = DATA_FILE.with_suffix(".js.tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(DATA_FILE)


def unique_output_name(category: str, original_name: str) -> str:
    base = slugify(Path(original_name).stem)
    full_dir = GALLERY_ROOT / category / "full"
    candidate = base
    number = 2
    while (full_dir / f"{candidate}.webp").exists():
        candidate = f"{base}-{number}"
        number += 1
    return candidate


def convert_image(data: bytes, category: str, original_name: str, caption: str = "") -> dict[str, str]:
    try:
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")

            name = unique_output_name(category, original_name)
            full_dir = GALLERY_ROOT / category / "full"
            thumb_dir = GALLERY_ROOT / category / "thumbs"
            full_dir.mkdir(parents=True, exist_ok=True)
            thumb_dir.mkdir(parents=True, exist_ok=True)

            full = image.copy()
            full.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
            full_path = full_dir / f"{name}.webp"
            full.save(full_path, "WEBP", quality=84, method=6)

            thumb = image.copy()
            thumb.thumbnail((560, 560), Image.Resampling.LANCZOS)
            thumb_path = thumb_dir / f"{name}.webp"
            thumb.save(thumb_path, "WEBP", quality=78, method=6)

    except UnidentifiedImageError as exc:
        raise ValueError(f"{original_name} is not a readable image") from exc
    except OSError as exc:
        raise ValueError(f"Could not process {original_name}: {exc}") from exc

    final_caption = caption.strip() or humanize(original_name)
    return {
        "src": full_path.relative_to(SITE_ROOT).as_posix(),
        "thumb": thumb_path.relative_to(SITE_ROOT).as_posix(),
        "alt": final_caption,
        "caption": final_caption,
    }


def import_one(category: str, filename: str, payload: bytes, caption: str = "") -> list[dict[str, str]]:
    if category not in CATEGORIES:
        raise ValueError("Unknown gallery category")

    entries: list[dict[str, str]] = []
    suffix = Path(filename).suffix.lower()

    if suffix == ".zip":
        with tempfile.TemporaryDirectory(prefix="fieldstation-photos-") as temp_dir:
            temp_path = Path(temp_dir)
            try:
                with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                    for member in archive.infolist():
                        if member.is_dir() or Path(member.filename).suffix.lower() not in IMAGE_EXTENSIONS:
                            continue
                        # Avoid unsafe archive paths by reading bytes directly instead of extracting.
                        photo_bytes = archive.read(member)
                        entries.append(convert_image(photo_bytes, category, Path(member.filename).name))
            except zipfile.BadZipFile as exc:
                raise ValueError(f"{filename} is not a valid ZIP archive") from exc
    elif suffix in IMAGE_EXTENSIONS:
        entries.append(convert_image(payload, category, filename, caption))
    else:
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")

    if not entries:
        raise ValueError("No supported photographs were found")

    gallery_data = load_gallery_data()
    known = {item.get("src") for item in gallery_data[category]}
    for entry in entries:
        if entry["src"] not in known:
            gallery_data[category].append(entry)
    save_gallery_data(gallery_data)
    return entries


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FieldStation Photo Importer</title>
<style>
:root { --ink:#313629; --forest:#3b492b; --terracotta:#9a6648; --paper:#f8f1df; --line:#c3ab78; }
* { box-sizing:border-box; }
body { margin:0; color:var(--ink); background:#d8ccb0; font:17px/1.55 system-ui,sans-serif; }
main { width:min(920px,calc(100% - 2rem)); margin:2rem auto; padding:clamp(1.25rem,4vw,2.5rem); background:var(--paper); border:1px solid var(--line); box-shadow:0 22px 55px #3328152b; }
h1 { margin:.1rem 0 .3rem; color:var(--forest); font:700 clamp(2rem,7vw,4rem)/.95 Georgia,serif; }
.lede { max-width:720px; }
label { display:block; margin:1rem 0 .35rem; font-weight:700; }
select,input,button { font:inherit; }
select,input[type=file] { width:100%; padding:.75rem; border:1px solid var(--line); background:white; }
.drop { margin-top:1rem; padding:2rem 1rem; border:2px dashed var(--line); text-align:center; background:#fffaf0; }
.drop.drag { border-color:var(--terracotta); background:#fff2dd; }
.files { display:grid; gap:.6rem; margin:1rem 0; }
.file { display:grid; grid-template-columns:72px minmax(0,1fr); gap:.75rem; align-items:center; padding:.55rem; background:white; border:1px solid #d8c59a; }
.file img { width:72px; height:58px; object-fit:cover; }
.file input { width:100%; padding:.45rem; border:1px solid #d8c59a; }
button { border:0; padding:.85rem 1.1rem; color:white; background:var(--forest); cursor:pointer; font-weight:700; }
button:hover { background:var(--terracotta); }
button:disabled { opacity:.5; cursor:wait; }
.status { min-height:2rem; margin-top:1rem; padding:.75rem; background:#ece2ca; white-space:pre-wrap; }
.note { color:#5f6453; font-size:.9rem; }
</style>
</head>
<body>
<main>
<p>🐸 Full Circle Paradise</p>
<h1>Photo Importer</h1>
<p class="lede">Choose a page, then select photographs exported from Immich. The importer resizes them, creates fast thumbnails, and adds them to that page’s browseable gallery. Everything stays on this computer.</p>
<label for="category">Website page</label>
<select id="category">__OPTIONS__</select>
<div class="drop" id="drop">
  <strong>Drop photographs or an Immich ZIP here</strong><br>
  <span class="note">or choose files below</span>
</div>
<label for="picker">Photographs</label>
<input id="picker" type="file" accept="image/*,.zip" multiple>
<div class="files" id="files"></div>
<button id="publish" type="button" disabled>Add photographs to the website</button>
<div class="status" id="status">Waiting for photographs.</div>
<p class="note">After importing, refresh the website with <strong>Ctrl+Shift+R</strong>. The new photographs will appear in the selected page gallery.</p>
</main>
<script>
const picker = document.querySelector('#picker');
const drop = document.querySelector('#drop');
const list = document.querySelector('#files');
const publish = document.querySelector('#publish');
const status = document.querySelector('#status');
let files = [];
function setFiles(next) {
  files = [...next].filter(file => file.type.startsWith('image/') || file.name.toLowerCase().endsWith('.zip'));
  list.innerHTML = '';
  files.forEach((file, index) => {
    const row = document.createElement('div'); row.className='file';
    const preview = document.createElement('img');
    if (file.type.startsWith('image/')) preview.src = URL.createObjectURL(file); else preview.alt='ZIP';
    const box = document.createElement('div');
    const name = document.createElement('strong'); name.textContent=file.name;
    const caption = document.createElement('input'); caption.placeholder='Caption (optional)'; caption.dataset.index=index;
    box.append(name, caption); row.append(preview, box); list.append(row);
  });
  publish.disabled = files.length === 0;
  status.textContent = files.length ? `${files.length} file(s) ready.` : 'Waiting for photographs.';
}
picker.addEventListener('change', () => setFiles(picker.files));
['dragenter','dragover'].forEach(name => drop.addEventListener(name, e => { e.preventDefault(); drop.classList.add('drag'); }));
['dragleave','drop'].forEach(name => drop.addEventListener(name, e => { e.preventDefault(); drop.classList.remove('drag'); }));
drop.addEventListener('drop', e => setFiles(e.dataTransfer.files));
publish.addEventListener('click', async () => {
  publish.disabled=true; let imported=0; status.textContent='Processing photographs…';
  const category=document.querySelector('#category').value;
  for (let i=0;i<files.length;i++) {
    const file=files[i];
    const caption=list.querySelector(`input[data-index="${i}"]`)?.value || '';
    status.textContent=`Processing ${i+1} of ${files.length}: ${file.name}`;
    try {
      const response=await fetch(`/upload?category=${encodeURIComponent(category)}`, {
        method:'POST', body:file,
        headers:{'X-Filename':encodeURIComponent(file.name),'X-Caption':encodeURIComponent(caption)}
      });
      const result=await response.json();
      if (!response.ok) throw new Error(result.error || 'Import failed');
      imported += result.imported;
    } catch (error) {
      status.textContent += `\nError: ${error.message}`; publish.disabled=false; return;
    }
  }
  status.textContent=`Done — ${imported} photograph(s) added. Refresh the website with Ctrl+Shift+R.`;
  files=[]; picker.value=''; list.innerHTML='';
});
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "FieldStationPhotoImporter/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path not in {"/", "/index.html"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        options = "".join(f'<option value="{key}">{label}</option>' for key, label in CATEGORIES.items())
        body = PAGE.replace("__OPTIONS__", options).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/upload":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})
            return

        params = urllib.parse.parse_qs(parsed.query)
        category = params.get("category", [""])[0]
        filename = urllib.parse.unquote(self.headers.get("X-Filename", "photo.jpg"))
        caption = urllib.parse.unquote(self.headers.get("X-Caption", ""))

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_UPLOAD_BYTES:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "The selected file is empty or too large"})
            return

        payload = self.rfile.read(length)
        try:
            entries = import_one(category, filename, payload, caption)
        except (ValueError, RuntimeError) as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except Exception as exc:  # Keep the local tool helpful instead of crashing.
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Unexpected error: {exc}"})
            return

        self.send_json(HTTPStatus.OK, {"imported": len(entries), "entries": entries})


def choose_port(start: int = DEFAULT_PORT) -> int:
    for port in range(start, start + 20):
        try:
            server = ThreadingHTTPServer((HOST, port), Handler)
        except OSError:
            continue
        server.server_close()
        return port
    raise RuntimeError("No free local port was found")


def main() -> None:
    if not DATA_FILE.exists():
        raise SystemExit(f"gallery-data.js was not found in {SITE_ROOT}")
    port = choose_port()
    server = ThreadingHTTPServer((HOST, port), Handler)
    url = f"http://{HOST}:{port}/"
    print(f"FieldStation Photo Importer: {url}")
    print(f"Website folder: {SITE_ROOT}")
    print("Press Ctrl+C in this window when you are finished.")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
