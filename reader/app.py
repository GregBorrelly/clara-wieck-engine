"""Clara Wieck reader: a sheet-music reading service built on homr. Images and PDFs in, MusicXML out.

POST /read   multipart field "file" (image or PDF), optional "engine"
             or JSON {"data": "<base64 or data URL>", "engine": "homr"}
GET  /health engines available and whether a request is running

Pages are read one at a time: the engines are CPU-heavy, and running two at once on a
small server only makes both slower.
"""
from __future__ import annotations

import base64
import os
import tempfile
import threading

from fastapi import FastAPI, HTTPException, Request, UploadFile

from .engines.base import Engine
from .engines.homr_engine import HomrEngine
from .pages import BadUpload, save_pages

ENGINES: dict[str, Engine] = {e.name: e for e in (HomrEngine(),) if e.available()}
DEFAULT = os.environ.get("READER_ENGINE", "homr")
MAX_BYTES = int(os.environ.get("READER_MAX_BYTES", 40 * 1024 * 1024))
TOKEN = os.environ.get("READER_TOKEN")  # optional shared secret with the app

app = FastAPI(title="Clara Wieck reader")
_lock = threading.Lock()


def _check_token(request: Request) -> None:
    if TOKEN and request.headers.get("authorization") != f"Bearer {TOKEN}":
        raise HTTPException(401, "missing or wrong token")


@app.get("/health")
def health():
    return {"ok": True, "name": "Clara Wieck reader", "engines": list(ENGINES), "default": DEFAULT if DEFAULT in ENGINES else None, "busy": _lock.locked()}


@app.post("/read")
async def read(request: Request):
    _check_token(request)
    engine_name = DEFAULT
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/"):
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile) and not hasattr(upload, "read"):
            raise HTTPException(400, "send the image or PDF in a field named 'file'")
        data = await upload.read()
        engine_name = str(form.get("engine") or engine_name)
    else:
        body = await request.json()
        raw = str(body.get("data") or "")
        try:
            data = base64.b64decode(raw.split(",", 1)[-1], validate=False)
        except ValueError:
            raise HTTPException(400, "data must be base64") from None
        engine_name = str(body.get("engine") or engine_name)
    if not data:
        raise HTTPException(400, "the file is empty")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"the file is larger than {MAX_BYTES // (1024 * 1024)} MB")
    engine = ENGINES.get(engine_name)
    if engine is None:
        raise HTTPException(400, f"unknown engine '{engine_name}'; available: {', '.join(ENGINES) or 'none'}")

    with tempfile.TemporaryDirectory() as work:
        try:
            pages = save_pages(data, work)
        except BadUpload as e:
            raise HTTPException(400, str(e)) from None
        out = []
        with _lock:
            for i, path in enumerate(pages):
                try:
                    r = engine.read_page(path)
                    out.append({"page": i + 1, "musicxml": r.musicxml, "systems": r.systems, "seconds": round(r.seconds, 2), "notes": r.notes})
                except Exception as e:  # one bad page shouldn't lose the others
                    out.append({"page": i + 1, "error": f"{type(e).__name__}: {e}"[:300]})
    return {"engine": engine.name, "pages": out}
