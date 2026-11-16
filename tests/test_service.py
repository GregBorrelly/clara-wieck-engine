"""Service tests with a stand-in engine (fast), plus one real homr run when RUN_HOMR=1."""
import base64
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from PIL import Image

from reader import app as service
from reader.engines.base import Engine, PageResult
from reader.pages import BadUpload, save_pages


class Fake(Engine):
    name = "fake"

    def __init__(self):
        self.seen = []

    def read_page(self, path):
        self.seen.append(Image.open(path).size)
        if len(self.seen) == 2 and os.environ.get("FAIL_SECOND"):
            raise RuntimeError("boom")
        return PageResult(musicxml="<score-partwise/>", seconds=0.1, engine="fake", systems=[{"left": 0.1, "top": 0.2, "right": 0.9, "bottom": 0.3}])


def png(w=800, h=1000, mode="RGB"):
    b = io.BytesIO()
    Image.new(mode, (w, h), "white").save(b, "PNG")
    return b.getvalue()


def pdf(pages=2):
    b = io.BytesIO()
    imgs = [Image.new("RGB", (612, 792), "white") for _ in range(pages)]
    imgs[0].save(b, "PDF", save_all=True, append_images=imgs[1:], resolution=72)
    return b.getvalue()


def test_pages_from_pdf_render_at_300_dpi(tmp_path):
    paths = save_pages(pdf(3), str(tmp_path))
    assert len(paths) == 3
    w, h = Image.open(paths[0]).size
    assert w == 2550 and abs(h - 3300) <= 1  # US letter at 300 dpi


def test_huge_photo_is_shrunk_and_transparency_flattened(tmp_path):
    (path,) = save_pages(png(9000, 6000, "RGBA"), str(tmp_path))
    im = Image.open(path)
    assert max(im.size) == 4200 and im.mode == "RGB"


def test_not_an_image(tmp_path):
    try:
        save_pages(b"hello", str(tmp_path))
    except BadUpload:
        return
    raise AssertionError("expected BadUpload")


def test_read_multipart_and_json(monkeypatch):
    fake = Fake()
    monkeypatch.setattr(service, "ENGINES", {"fake": fake})
    monkeypatch.setattr(service, "DEFAULT", "fake")
    c = TestClient(service.app)
    r = c.post("/read", files={"file": ("p.pdf", pdf(2), "application/pdf")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["engine"] == "fake" and [p["page"] for p in body["pages"]] == [1, 2]
    assert body["pages"][0]["systems"][0]["top"] == 0.2
    r = c.post("/read", json={"data": "data:image/png;base64," + base64.b64encode(png()).decode()})
    assert r.status_code == 200 and len(r.json()["pages"]) == 1
    assert c.get("/health").json()["engines"] == ["fake"]


def test_one_bad_page_keeps_the_others(monkeypatch):
    fake = Fake()
    monkeypatch.setattr(service, "ENGINES", {"fake": fake})
    monkeypatch.setattr(service, "DEFAULT", "fake")
    monkeypatch.setenv("FAIL_SECOND", "1")
    pages = TestClient(service.app).post("/read", files={"file": ("p.pdf", pdf(3), "application/pdf")}).json()["pages"]
    assert "error" in pages[1] and "musicxml" in pages[0] and "musicxml" in pages[2]


def test_token_and_errors(monkeypatch):
    monkeypatch.setattr(service, "ENGINES", {"fake": Fake()})
    monkeypatch.setattr(service, "DEFAULT", "fake")
    monkeypatch.setattr(service, "TOKEN", "s3cret")
    c = TestClient(service.app)
    assert c.post("/read", json={"data": "x"}).status_code == 401
    h = {"authorization": "Bearer s3cret"}
    assert c.post("/read", json={"data": ""}, headers=h).status_code == 400
    assert c.post("/read", json={"data": base64.b64encode(png()).decode(), "engine": "nope"}, headers=h).status_code == 400
    assert c.post("/read", json={"data": base64.b64encode(b"junk").decode()}, headers=h).status_code == 400


def test_real_homr_on_an_engraved_line():
    if not os.environ.get("RUN_HOMR"):
        return
    from reader.engines.homr_engine import HomrEngine
    here = os.path.join(os.path.dirname(__file__), "fixtures", "page.png")
    r = HomrEngine().read_page(here)
    assert "<score-partwise" in r.musicxml and r.systems
