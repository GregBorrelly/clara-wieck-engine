"""Getting a photographed page ready to be read: bent staff lines made straight, a facing page cut away.

A page in a book curls, and the staff lines in a photo of it bend. On a bent staff the engine can't tell
which staff a note between the two belongs to, and gives notes to the wrong hand. So before reading:

1. The slope of every piece of staff line is measured, one smooth surface is fitted to those slopes, and
   each spot of the picture is moved up or down by how far it has drifted. Because the surface is smooth,
   the lines come out smooth.
2. Everything outside the sheet of paper is cut away, and so is the edge of a facing page: a cut is made
   only in a band that no staff line crosses, with staves on both sides of it.

Measured on photographs of a scales book and a piece (see BENCHMARK.md), this order took the notes read
exactly right from 68% to 99%. Evening out the lighting, removing coloured ink and turning the picture
black and white were measured too and are deliberately not done: each lost notes on some page.

A page that needs nothing (a scan, an engraved page) is left exactly as it was. Where each line of music is
found on the prepared picture, `Prepared.back` says where that is on the picture as it was sent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

LEVEL = 0.004       # mean slope (rise over run) below which staff lines count as straight: about a quarter of a degree
NEEDS = 0.012       # a page is only straightened if its lines lean more than this (about 0.7 degrees): a scan is left alone
PASSES = 5
TERMS = [(i, j) for i in range(5) for j in range(4)]  # slope may bend along the page and differ from top to bottom


@dataclass
class Prepared:
    changed: bool = False
    notes: list[str] = field(default_factory=list)
    back: Callable[[dict], dict] = lambda box: box   # a box on the prepared page (fractions) -> the same place as sent


def _grey(img):
    import cv2
    return img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def staff_lines(g):
    """Only the staff lines: ink that runs sideways for a stretch (short enough a stretch to survive a bent line)."""
    import cv2
    import numpy as np
    ink = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 41, 15)
    return cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((1, max(25, g.shape[1] // 45)), np.uint8))


def line_slopes(g):
    """Where the staff lines are and how steeply each piece of one runs: rows of (x, y, slope).

    Every unbroken piece of staff line is fitted with a gentle curve of its own, and its slope read off along
    it. A staff line is as thin as the thinnest long strokes on the page: beams and slurs, which are thicker
    and slant for their own reasons, are told apart by that and left out.
    """
    import cv2
    import numpy as np
    mask = staff_lines(g)
    L = max(25, g.shape[1] // 45)
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    long = [i for i in range(1, n) if st[i, 2] >= 3 * L]
    if not long:
        return np.zeros((0, 3))
    thin = float(np.percentile([st[i, 4] / st[i, 2] for i in long], 30))
    out = []
    for i in long:
        x, y, w, h, _area = st[i]
        piece = lab[y:y + h, x:x + w] == i
        cols = np.where(piece.any(0))[0]
        thick = piece.sum(0)[cols]
        if np.median(thick) > 1.6 * thin + 1:
            continue
        ok = thick <= 1.6 * thin + 2          # where a note or stem touches the line, the column says nothing
        if ok.sum() < 2 * L:
            continue
        rows = (piece * np.arange(h).reshape(-1, 1)).sum(0)[cols] / thick
        c = np.polyfit(cols[ok], rows[ok], 2 if ok.sum() > 6 * L else 1)
        if np.abs(np.polyval(c, cols[ok]) - rows[ok]).max() > 2.5:
            continue  # not one smooth line: two lines joined, or a line running into something
        for cx in range(int(cols[0]) + L // 2, int(cols[-1]), L):
            out.append((x + cx, y + float(np.polyval(c, cx)), float(np.polyval(np.polyder(c), cx))))
    return np.array(out, np.float64).reshape(-1, 3)


def lean(g) -> float | None:
    """How far the staff lines are from level, as a mean slope; None when too few are found to say."""
    import numpy as np
    pts = line_slopes(g)
    return float(np.sqrt((pts[:, 2] ** 2).mean())) if len(pts) >= 40 else None


def straighten(img):
    """Staff lines made straight and level. Returns (picture, where each row came from, slope before, slope after).

    `where each row came from` is a map the size of the picture: for every spot, the height in the picture as
    it was sent that now shows there. With nothing to do, or no improvement, the picture comes back untouched.
    """
    import cv2
    import numpy as np
    H, W = img.shape[:2]
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    out, source = img, gy.copy()
    first = last = None
    for _ in range(PASSES):
        pts = line_slopes(_grey(out))
        if len(pts) < 40:
            break
        u, v, s = pts[:, 0] / W * 2 - 1, pts[:, 1] / H * 2 - 1, pts[:, 2]
        last = float(np.sqrt((s ** 2).mean()))
        first = last if first is None else first
        if last < LEVEL:
            break
        A = np.stack([u ** i * v ** j for i, j in TERMS], axis=-1)
        keep = np.ones(len(s), bool)
        for _ in range(5):  # fit, drop the pieces that disagree with the surface (a slur taken for a line), fit again
            coef, *_ = np.linalg.lstsq(np.vstack([A[keep], 0.005 * np.eye(len(TERMS))]),
                                       np.concatenate([s[keep], np.zeros(len(TERMS))]), rcond=None)
            res = s - A @ coef
            keep = np.abs(res) < 2.2 * max(np.median(np.abs(res[keep])) * 1.48, 1e-4)
        # Drift at a spot: the slope added up along its row, from the middle column to the spot.
        cu, cv = np.meshgrid(np.linspace(-1, 1, 160), np.linspace(-1, 1, 200))
        drift = np.zeros_like(cu)
        for (i, j), a in zip(TERMS, coef):
            drift += a * cv ** j * cu ** (i + 1) / (i + 1)
        shift = cv2.resize((drift * W / 2).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
        border = (255, 255, 255) if out.ndim == 3 else 255
        out = cv2.remap(out, gx, gy + shift, cv2.INTER_CUBIC, borderValue=border)
        source = cv2.remap(source, gx, gy + shift, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    if first is None or out is img:
        return img, gy, first, first
    after = lean(_grey(out))
    if first < NEEDS or after is None or after > 0.6 * first:
        return img, gy, first, first  # level enough already, or not clearly better: the page is read as it was sent
    return out, source, first, after


def paper(g):
    """Where the paper is, as one shape: the bright region that holds the most staff lines."""
    import cv2
    import numpy as np
    small = cv2.resize(g, None, fx=0.2, fy=0.2, interpolation=cv2.INTER_AREA)
    _, th = cv2.threshold(cv2.GaussianBlur(small, (11, 11), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((31, 31), np.uint8))
    n, lab, _st, _ = cv2.connectedComponentsWithStats(th)
    if n < 2:
        return np.ones(g.shape, bool)
    lines = cv2.resize(staff_lines(g), (small.shape[1], small.shape[0]), interpolation=cv2.INTER_AREA) > 0
    best = max(range(1, n), key=lambda i: int(lines[lab == i].sum()))
    if not lines[lab == best].any():
        return np.ones(g.shape, bool)
    return cv2.resize((lab == best).astype(np.uint8), (g.shape[1], g.shape[0]), interpolation=cv2.INTER_NEAREST) > 0


def page_box(g) -> tuple[int, int, int, int]:
    """The part of the picture that is this page: (left, top, right, bottom) in pixels.

    The paper's own extent, less the edge of a facing page. Nothing is cut from the top or bottom of the
    paper, and a cut between pages is made only in the middle of a band that no staff line crosses, so no
    line of this page's music can be lost.
    """
    import numpy as np
    H, W = g.shape
    sheet = paper(g)
    ys, xs = np.where(sheet)
    if not len(xs):
        return 0, 0, W, H
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    import cv2
    # Staff lines well inside the paper: the paper's own top and bottom edges also run sideways, and are not music.
    inside = cv2.erode(sheet.astype(np.uint8), np.ones((max(15, H // 60), max(15, W // 60)), np.uint8)) > 0
    lines = ((staff_lines(g) > 0) & inside).sum(0).astype(np.float32)
    cols = np.arange(x0, x1, 4)
    weight = np.array([lines[c:c + 4].sum() for c in cols])
    if not weight.any():
        return x0, y0, x1, y1
    # A stave puts five long lines over every column it crosses. A band with under a twelfth of that is not a
    # stave: at most the straight edge left where the picture was unbent, or the rim of the paper.
    empty = weight <= 0.08 * max(1.0, float(np.percentile(weight, 90)))
    left, right, k = x0, x1, 0
    while k < len(cols):
        if not empty[k]:
            k += 1
            continue
        j = k
        while j < len(cols) and empty[j]:
            j += 1
        before, after = float(weight[:k].sum()), float(weight[j:].sum())
        if before > 0 and after > 0 and (j - k) * 4 >= 0.006 * W:
            mid = int(cols[(k + j) // 2])
            if after < 0.25 * before:       # the smaller side is the other page
                right = min(right, mid)
            elif before < 0.25 * after:
                left = max(left, mid)
        k = j
    return left, y0, right, y1


def prepare(path: str) -> Prepared:
    """Straighten and crop the page image at `path`, in place. Returns what was done and how to map positions back."""
    try:
        import cv2
        import numpy as np
    except ImportError:  # without OpenCV the page is read as it was sent
        return Prepared()
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None or img.ndim not in (2, 3) or min(img.shape[:2]) < 400:
        return Prepared()
    if img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    H, W = img.shape[:2]
    out, source, before, after = straighten(img)
    notes = []
    if out is not img:
        deg = lambda r: float(np.degrees(np.arctan(r)))  # noqa: E731
        notes.append(f"Straightened the staff lines: they leaned {deg(before):.1f} degrees on average, {deg(after):.1f} after.")
    left, top, right, bottom = page_box(_grey(out))
    cut = (right - left) * (bottom - top) < 0.97 * W * H and right - left > 0.4 * W and bottom - top > 0.4 * H
    if not cut:
        left, top, right, bottom = 0, 0, W, H
    if out is img and not cut:
        return Prepared()
    if cut:
        notes.append(f"Kept this page only: {100 * (right - left) * (bottom - top) / (W * H):.0f}% of the picture.")
        out = out[top:bottom, left:right]
        k = max(H, W) / max(out.shape[:2])   # as large as it was sent, so the music isn't read smaller
        out = cv2.resize(out, (round(out.shape[1] * k), round(out.shape[0] * k)), interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(path, out)
    coarse = source[::8, ::8].copy()

    def back(box: dict) -> dict:
        """A box on the prepared page, as fractions, moved to where it lies on the page as sent."""
        l, r = left + box["left"] * (right - left), left + box["right"] * (right - left)
        t, b = top + box["top"] * (bottom - top), top + box["bottom"] * (bottom - top)
        xs = np.clip(np.linspace(l, r, 9) / 8, 0, coarse.shape[1] - 1).astype(int)
        row = lambda y: coarse[int(np.clip(y / 8, 0, coarse.shape[0] - 1)), xs]  # noqa: E731
        return {"left": round(float(l) / W, 4), "right": round(float(r) / W, 4),
                "top": round(float(max(0.0, row(t).min())) / H, 4), "bottom": round(float(min(H, row(b).max())) / H, 4)}

    return Prepared(changed=True, notes=notes, back=back)
