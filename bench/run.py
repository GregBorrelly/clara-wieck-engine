"""Benchmark an engine on pieces whose notes are known.

    python -m bench.run --app ../etude --pieces 8           # spread across the app's library
    python -m bench.run --app ../etude --ids ode-to-joy --variants clean photo

For each piece: the app's score -> MusicXML -> engraved A4 pages (Verovio, 300 dpi),
optionally made to look like phone photos; each page is read by the engine; the readings
are joined and converted back with the app's own MusicXML importer, then scored.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from bench.augment import phone_photo  # noqa: E402
from bench.metrics import compare  # noqa: E402
from bench.render import engrave  # noqa: E402


def load_app(app_dir: str):
    sys.path.insert(0, os.path.join(os.path.abspath(app_dir), "api"))
    from _score.model import normalize
    from _score.musicxml import from_musicxml, to_musicxml
    return normalize, from_musicxml, to_musicxml


def pick(app_dir: str, n: int, max_bars: int) -> list[dict]:
    index = json.load(open(os.path.join(app_dir, "public", "library", "index.json")))
    usable = [e for e in index if 8 <= e.get("bars", 0) <= max_bars]
    usable.sort(key=lambda e: (e.get("difficulty", 0), e["id"]))
    if n >= len(usable):
        return usable
    step = len(usable) / n
    return [usable[int(i * step)] for i in range(n)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True, help="path to the PlayMySheet app checkout")
    ap.add_argument("--engine", default="homr")
    ap.add_argument("--pieces", type=int, default=6)
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--max-bars", type=int, default=40)
    ap.add_argument("--variants", nargs="*", default=["clean", "photo"])
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    a = ap.parse_args()

    normalize, from_musicxml, to_musicxml = load_app(a.app)
    from reader.engines.homr_engine import HomrEngine
    engine = {"homr": HomrEngine}[a.engine]()
    os.makedirs(a.out, exist_ok=True)

    lib = os.path.join(a.app, "public", "library")
    entries = [{"id": i} for i in a.ids] if a.ids else pick(a.app, a.pieces, a.max_bars)
    rows = []
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(a.out, f"results-{a.engine}-{stamp}.json")
    for e in entries:
        truth, _ = normalize(json.load(open(os.path.join(lib, f"{e['id']}.json"))))
        clean_pages = engrave(to_musicxml(truth), os.path.join(a.out, e["id"]))
        for variant in a.variants:
            pages = clean_pages if variant == "clean" else [
                phone_photo(p, p.replace(".png", "-photo.jpg"), seed=k) for k, p in enumerate(clean_pages)]
            measures, secs, err, got = [], 0.0, None, None
            for p in pages:
                try:
                    r = engine.read_page(p)
                    secs += r.seconds
                    s, _ = from_musicxml(r.musicxml.encode())
                    got = got or s
                    measures += s["measures"]
                except Exception as ex:
                    err = f"{type(ex).__name__}: {ex}"[:200]
            if got is None:
                print(f"{e['id']:<44} {variant:<6} failed: {err}")
                continue
            got = {**got, "measures": measures}
            c = compare(truth, got)
            c.update(id=e["id"], variant=variant, pages=len(pages), seconds=round(secs, 1), error=err)
            rows.append(c)
            json.dump(rows, open(path, "w"), indent=1)  # saved as we go, so a crash keeps what's done
            print(f"{e['id'][:44]:<44} {variant:<6} notes {c['notes_f1']:.0%}  pitches {c['pitch_f1']:.0%}  "
                  f"bars {c['bars_perfect']}/{c['bars']} (read {c['bars_read']})  key {'ok' if c['key_ok'] else 'WRONG'}  "
                  f"time {'ok' if c['time_ok'] else 'WRONG'}  {c['seconds']}s/{c['pages']}p", flush=True)
    for variant in a.variants:
        rs = [r for r in rows if r["variant"] == variant]
        if rs:
            notes = sum(r["notes"] for r in rs)
            w = lambda k: sum(r[k] * r["notes"] for r in rs) / max(1, notes)  # noqa: E731
            print(f"\n{variant}: notes {w('notes_f1'):.1%}, pitches {w('pitch_f1'):.1%}, "
                  f"perfect bars {sum(r['bars_perfect'] for r in rs)}/{sum(r['bars'] for r in rs)}, "
                  f"key right {sum(r['key_ok'] for r in rs)}/{len(rs)}, time right {sum(r['time_ok'] for r in rs)}/{len(rs)}, "
                  f"median {statistics.median(r['seconds'] / r['pages'] for r in rs):.0f}s per page")
    print("details:", path)


if __name__ == "__main__":
    main()
