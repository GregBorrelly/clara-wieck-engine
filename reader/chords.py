"""Chord symbols printed over the music: "G", "Am7", "C#dim", "Bb/F", as on a lead sheet or a fake book.

The reading engine reads notes and nothing in letters, and the page's text reader keeps only lines it is sure of with
real words in them, which loses most chord symbols ("G" is one letter; "D7" has a stem through it). So the chords are
read on their own, line of music by line of music:

1. Each staff is found from its five lines, and its top line followed across the page, so a curved photo is read
   along its curve. Of a piano's two staves the upper one is taken: chord symbols sit above the music.
2. The chord row is found first, in a tall band over the staff: the height where most chord-like text sits (just
   over the staff on a lead sheet, higher on an engraved piano page where bar numbers and slurs come between).
   Bands reaching just above that row are then cut out, laid flat, and read as text several ways.
3. Each reading keeps only what a chord symbol can be, after mending the text reader's usual confusions with them
   (a stem through a 7 read as "/", an ending's number stuck to the front, "?" for 7).
4. A chord is kept where at least three readings found one at the same place on the chord row; a single letter, which
   a stray mark can look like, needs one more. Where readings differ, the commonest wins, or a fuller reading of the
   same chord ("Am7" over "Am") when enough readings saw all of it.

Measured on a photographed lead sheet (52 chords) and two engraved piano pages: see BENCHMARK.md.
Without Tesseract installed, a page simply has no chords.
"""
from __future__ import annotations

import os
import re
from collections import Counter

CHORD = re.compile(r"^[A-G][#b]?(maj|min|dim|aug|sus|add|m|M|o|\+|-)?\d{0,2}(\(?[#b]?\d{1,2}\)?)*(/[A-G][#b]?)?$")
FIX = [
    (r"^[\[\]|lI1-4%§]+(?=[A-Gp])", ""),            # an ending's number or a sign printed against the chord
    (r"^\d(?=[A-G])", ""),
    (r"^p(?=\d)", "D"),                               # D read as p after an ending's bracket
    (r"^([A-G][#b]?(?:maj|m|dim|sus|add)?)/7$", r"\g<1>7"),   # a stem through the 7
    (r"^([A-G][#b]?(?:maj|m|dim)?)[/Zz]$", r"\g<1>7"),
    (r"^([A-G][#b]?(?:maj|m)?)\?$", r"\g<1>7"),
    (r"^([A-G])[$¢£ft§Hh]+(dim|m|7|maj|°)", r"\1#\2"),
    (r"^([A-G])[$¢£§]+$", r"\1#"),
    (r"^([A-G])c$", r"\1"),                           # the segno's tail read onto the chord
    (r"sug", "sus"), (r"sus[qg]$", "sus4"),            # s read as g, 4 as q
]
# (how far above the chord row's baseline the band reaches, in line spacings; page segmentation mode; enlargement).
# The band runs from the staff's top line up to that height. Chosen in BENCHMARK.md.
READINGS = [(1.6, 6, 1), (1.6, 6, 2), (2.2, 6, 2), (2.8, 6, 2), (2.2, 11, 1), (2.8, 11, 2), (2.2, 4, 2), (2.2, 11, 2), (1.6, 4, 2), (2.8, 6, 1)]
TALLEST = 8.0      # line spacings above the staff searched for the chord row
SPACING = (16.0, 48.0)   # line spacings (pixels) read as they are; a band outside them is resized into them. Resizing
                         # softens the letters, and even 4% lost chords in BENCHMARK.md, so it is kept to small or huge pictures
WORKERS = 4        # lines read at once
NEED, NEED_SINGLE = 3, 4


def norm(text: str) -> str:
    t = text.replace("♯", "#").replace("♭", "b").strip(".,:;'\"`!_—-»«*~()")
    for a, b in FIX:
        t = re.sub(a, b, t)
    return t


def _staves(g):
    """Every five-line staff's top line, per column strip: (bins, tops per bin, line spacing)."""
    import cv2
    import numpy as np
    H, W = g.shape
    ink = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 12)
    lines = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((1, max(25, W // 60)), np.uint8))
    step = max(12, W // 140)
    bins = list(range(0, W - step, step))
    cands = []
    for x in bins:
        col = lines[:, x:x + step].max(1) > 0
        edges = np.flatnonzero(np.diff(np.concatenate([[0], col.astype(np.int8), [0]])))
        cands.append((edges[0::2] + edges[1::2] - 1) / 2.0)
    gaps = np.concatenate([np.diff(c) for c in cands if len(c) > 1] or [np.array([0.0])])
    hist = np.bincount(np.clip(gaps.astype(int), 0, 400))
    hist[:4] = 0
    sp = float(np.argmax(hist)) or 10.0
    tops = []
    for c in cands:
        out = [y for y in c if sum(any(abs(c - (y + k * sp)) < 0.35 * sp) for k in (1, 2, 3, 4)) >= 3 and not any(abs(c - (y - sp)) < 0.35 * sp)]
        tops.append(np.array(out))
    return bins, step, tops, sp


def staff_count(path: str, with_top: bool = False):
    """How many five-line staves the page holds: one per line of music for a melody, two for a piano.

    With `with_top`, also where the first staff's top line is, as a fraction of the page (less a line spacing):
    everything above it is the heading."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return (None, None) if with_top else None
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return (None, None) if with_top else None
    bins, step, tops, sp = _staves(img)
    # Across the middle half of the page, where every staff runs: the usual number found in one column strip.
    mid = [len(t) for i, t in enumerate(tops) if len(bins) // 4 <= i < 3 * len(bins) // 4]
    count = int(np.median(mid)) if mid else None
    if not with_top:
        return count
    firsts = [t.min() for i, t in enumerate(tops) if len(t) and len(bins) // 4 <= i < 3 * len(bins) // 4]
    top = (float(np.median(firsts)) - sp) / img.shape[0] if firsts else None
    return count, top


def _trace(box, H, W, bins, step, tops, sp):
    """The top line of the upper staff of one line of music, as y(x), followed across the page from where it is surest."""
    import numpy as np
    x0, x1 = box["left"] * W, box["right"] * W
    want = box["top"] * H
    best = None
    for i, x in enumerate(bins):
        if not (x0 + (x1 - x0) / 3 <= x <= x1 - (x1 - x0) / 3) or not len(tops[i]):
            continue
        near = tops[i][np.argmin(np.abs(tops[i] - want))]
        d = abs(near - want)
        if d < 3 * sp and (best is None or d < best[0]):
            best = (d, i, near)
    if best is None:
        return None
    _, i0, y0 = best
    path = {i0: y0}
    for direction in (1, -1):
        y, i, miss = y0, i0 + direction, 0
        while 0 <= i < len(bins) and x0 - step <= bins[i] <= x1 + step and miss < 12:
            c = tops[i]
            if len(c) and np.abs(c - y).min() < 0.8 * sp:
                y = c[np.argmin(np.abs(c - y))]
                path[i] = y
                miss = 0
            else:
                miss += 1
            i += direction
    xs = np.array([bins[i] + step / 2 for i in sorted(path)], float)
    ys = np.array([path[i] for i in sorted(path)], float)
    if len(xs) < 4:
        return None
    c = np.polyfit(xs, ys, min(4, max(1, len(xs) // 6)))
    d = np.polyder(c)
    lo, hi = xs.min(), xs.max()

    def f(x):
        x = np.asarray(x, float)
        return np.where(x < lo, np.polyval(c, lo) + np.polyval(d, lo) * (x - lo),
                        np.where(x > hi, np.polyval(c, hi) + np.polyval(d, hi) * (x - hi), np.polyval(c, x)))
    return f


def _band(g, f, x0, x1, up, sp):
    """The strip `up` line spacings tall just above the staff's top line, laid flat along it."""
    import cv2
    import numpy as np
    sh = int((up + 0.3) * sp)
    mx, my = np.meshgrid(np.arange(x0, x1, dtype=np.float32), np.arange(sh, dtype=np.float32))
    base = f(mx[0]).astype(np.float32)
    return cv2.remap(g, mx, base[None, :] - up * sp + my, cv2.INTER_LINEAR, borderValue=255)


def _read(strip, psm, scale):
    import cv2
    import pytesseract
    img = cv2.resize(strip, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC) if scale != 1 else strip
    d = pytesseract.image_to_data(img, config=f"--psm {psm}", output_type=pytesseract.Output.DICT)
    out = []
    for i, raw in enumerate(d["text"]):
        t = norm(raw)
        if t and CHORD.match(t):
            r = raw.strip()
            # Something read onto the front of the chord ("2D7": an ending's number): its share of the width is skipped.
            k = r.find(t[0]) if r and r[0] != t[0] else 0
            left = d["left"][i] + d["width"][i] * max(0, k) / max(1, len(r))
            out.append((left / scale, (d["left"][i] + d["width"][i]) / scale, (d["top"][i] + d["height"][i]) / scale, t))
    return out


def _sharpen(band):
    """The band with its letters' edges brought up (an unsharp mask), for a picture softened by being made smaller."""
    import cv2
    import numpy as np
    b = band.astype(np.float32)
    return np.clip(2.0 * b - cv2.GaussianBlur(b, (0, 0), 2.0), 0, 255).astype(np.uint8)


def _base(sp: float) -> float:
    lo, hi = SPACING
    return lo / sp if sp < lo else hi / sp if sp > hi else 1.0


def _row(img, f, x0, x1, tall, sp) -> float | None:
    """How high above the staff's top line the chord symbols' baseline sits, in line spacings; None if no chords."""
    import numpy as np
    strip = _band(img, f, x0, x1, tall, sp)
    lifts = []
    base = _base(sp)
    for psm, scale in ((11, 1), (11, 2), (6, 1)):
        try:
            got = _read(strip, psm, scale * base)
        except Exception:
            continue
        lifts += [(tall * sp - base) / sp for a, b, base, t in got]
    if len(lifts) < 2:
        return None
    lifts = np.array(lifts)
    # The height with the most chord-like text within half a line spacing of it; nearer the staff if two tie.
    counts = [(int((np.abs(lifts - h) < 0.5).sum()), -h, h) for h in lifts if h > -0.2]
    if not counts:
        return None
    return float(max(counts)[2])


def _barlines(img, f, x0, x1, sp, clef_end) -> list[int]:
    """The barlines of one line of music, across the page in pixels.

    A barline is a thin stroke that fills the staff from its top line to its bottom line and stops at the top line,
    with no notehead beside it: a note's stem that happens to span the staff has its head next to it.
    """
    import cv2
    import numpy as np
    rows = int(6 * sp)
    mx, my = np.meshgrid(np.arange(x0, x1, dtype=np.float32), np.arange(rows, dtype=np.float32))
    base = f(mx[0]).astype(np.float32)
    flat = cv2.remap(img, mx, base[None, :] - sp + my, cv2.INTER_LINEAR, borderValue=255)
    ink = cv2.adaptiveThreshold(flat, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 12) > 0
    top, bottom = int(1.25 * sp), int(4.75 * sp)
    inside = ink[top:bottom].mean(0)
    above = ink[:int(0.7 * sp)].mean(0)
    cand = (inside >= 0.9) & (above <= 0.35)
    strokes, x = [], 0
    while x < len(cand):
        if not cand[x]:
            x += 1
            continue
        y = x
        while y < len(cand) and cand[y]:
            y += 1
        if y - x <= 0.6 * sp:
            strokes.append((x, y))
        x = y

    def run(col):   # the longest stretch of ink down one column inside the staff
        c, best = 0, 0
        for v in ink[top - int(0.25 * sp):bottom + int(0.25 * sp), col]:
            c = c + 1 if v else 0
            best = max(best, c)
        return best
    out = []
    for a, b in strokes:
        near = [c for c in list(range(max(0, a - int(0.9 * sp)), max(0, a - int(0.15 * sp)))) + list(range(b + int(0.15 * sp), min(len(cand), b + int(0.9 * sp))))]
        if any(run(c) >= 0.6 * sp for c in near[::2]):
            continue          # a notehead beside it: a stem
        xc = x0 + (a + b) / 2
        if xc - x0 < clef_end:
            continue
        if out and xc - out[-1] < 1.2 * sp:
            out[-1] = xc       # a double or repeat bar: one barline, at its right-hand stroke
        else:
            out.append(xc)
    return [int(round(v)) for v in out]


def find(path: str, systems: list[dict], readings=None, layout: dict | None = None) -> list[dict]:
    """Chord symbols over each line of music on the page image at `path`.

    `systems` are the lines of music as boxes (fractions of the page). Returns [{text, left, right, top, bottom, x, y,
    system}] with positions as fractions of the page, left to right within each line.
    """
    try:
        import cv2
        import numpy as np
        import pytesseract  # noqa: F401
    except ImportError:
        return []
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None or not systems:
        return []
    H, W = img.shape
    try:
        bins, step, tops, sp = _staves(img)
    except Exception:
        return []
    from concurrent.futures import ThreadPoolExecutor
    # Each Tesseract on one core, so several lines are read side by side instead of fighting over every core.
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        lines = list(pool.map(lambda kb: _line(img, H, W, bins, step, tops, sp, systems, kb[0], kb[1], readings), enumerate(systems)))
    if layout is not None:
        # Each line's barlines, in the same pixels as the chords, so the chords can be lined up with the bars.
        bars = []
        for box in systems:
            f = _trace(box, H, W, bins, step, tops, sp)
            x0, x1 = int(max(0, box["left"] * W - 2 * sp)), int(min(W, box["right"] * W + sp))
            try:
                bars.append(_barlines(img, f, x0, x1, sp, box["left"] * W - x0 + 3 * sp) if f is not None else [])
            except Exception:
                bars.append([])
        layout["barlines"] = bars
    return [c for line in lines for c in line]


def _line(img, H, W, bins, step, tops, sp, systems, k, box, readings) -> list[dict]:
    """The chord symbols over one line of music."""
    import numpy as np
    out: list[dict] = []
    if True:
        f = _trace(box, H, W, bins, step, tops, sp)
        if f is None:
            return out
        x0, x1 = int(max(0, box["left"] * W - 2 * sp)), int(min(W, box["right"] * W + sp))
        # How far up there is room: to the bottom of the line of music above, or the top of the page.
        y_here = float(f(np.array([(x0 + x1) / 2]))[0])
        room = (y_here - (systems[k - 1]["bottom"] * H if k else 0)) / sp - 0.5
        lift = _row(img, f, x0, x1, min(TALLEST, max(2.0, room)), sp)
        if lift is None:
            return out
        found = []
        strips = {}
        for n, (over, psm, scale, *rest) in enumerate(readings or READINGS):
            sharp = bool(rest and rest[0])
            up = min(lift + over, max(2.0, room))
            if (up, sharp) not in strips:
                strips[(up, sharp)] = _sharpen(_band(img, f, x0, x1, up, sp)) if sharp else _band(img, f, x0, x1, up, sp)
            try:
                got = _read(strips[(up, sharp)], psm, scale * _base(sp))
            except Exception:
                continue
            for a, b, base, t in got:
                found.append((a, b, base - up * sp, t, n))   # base measured up from the staff's top line (negative = above)
        if not found:
            return out
        row = float(np.median([fb for _, _, fb, _, _ in found]))
        clef_end = box["left"] * W - x0 + 4 * sp           # the clef and key signature: no chord is printed over them
        pts = sorted((a, b, t, n) for a, b, fb, t, n in found if abs(fb - row) < sp and a >= clef_end)
        groups: list[list] = []
        for a, b, t, n in pts:
            if groups and a - groups[-1][-1][0] < 1.2 * sp:
                groups[-1].append((a, b, t, n))
            else:
                groups.append([(a, b, t, n)])
        chords = []
        for gr in groups:
            votes = Counter(t for t, n in {(t, n) for _, _, t, n in gr})
            voters = len({n for _, _, _, n in gr})
            best, cnt = votes.most_common(1)[0]
            for t, c in votes.items():
                if t != best and t.startswith(best) and c >= 2 and c >= 0.3 * cnt:
                    best, cnt = t, c
            if voters < NEED or (len(best) == 1 and voters < NEED_SINGLE):
                continue
            a = float(np.median([p[0] for p in gr]))
            b = float(np.median([p[1] for p in gr]))
            if chords and chords[-1]["text"] == best and a - chords[-1]["_b"] < 2.5 * sp:
                continue   # the same chord found twice, split by a gap in one reading
            xa, xb = x0 + a, x0 + b
            ya = float(f(np.array([(xa + xb) / 2]))[0] + row)
            chords.append({"text": best, "_b": b, "left": round(xa / W, 4), "right": round(xb / W, 4),
                           "top": round((ya - 0.9 * sp) / H, 4), "bottom": round(ya / H, 4),
                           "x": round((xa + xb) / 2 / W, 4), "y": round((ya - 0.45 * sp) / H, 4), "system": k})
        for c in chords:
            c.pop("_b")
        out += chords
    return out
