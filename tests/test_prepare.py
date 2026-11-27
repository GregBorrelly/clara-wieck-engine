"""Page preparation: bent staff lines straightened, a facing page cut away, a clean page left alone.

Needs OpenCV (it comes with homr). Run: python -m tests.test_prepare
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

from reader import prepare as P


def page(w=1500, h=2000, bend=0.0, second_page=False, dark_border=False):
    """A sheet with six systems of two staves; `bend` curls the lines (pixels of sag at the edges)."""
    img = np.full((h, w), 40 if dark_border else 245, np.uint8)
    x0, x1 = (60, w - 60) if not second_page else (60, int(w * 0.8))
    if dark_border:
        img[80:h - 80, 40:w - 40] = 240
    xs = np.arange(w)
    sag = lambda x: bend * ((x - w / 2) / (w / 2)) ** 2  # noqa: E731
    def staves(a, b):
        for s in range(6):
            for staff in range(2):
                for line in range(5):
                    y0 = 220 + s * 280 + staff * 110 + line * 16
                    for x in range(a, b):
                        y = int(round(y0 + sag(x)))
                        img[y:y + 3, x] = 20
                for n in range(a + 60, b - 40, 70):  # some notes, so it isn't only lines
                    cv2.circle(img, (n, int(220 + s * 280 + staff * 110 + 24 + sag(n))), 9, 20, -1)
    staves(x0, x1)
    if second_page:
        staves(int(w * 0.8) + 50, w - 10)
    return img


def run(img):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "page001.png")
        cv2.imwrite(path, img)
        before = open(path, "rb").read()
        ready = P.prepare(path)
        return ready, cv2.imread(path, cv2.IMREAD_GRAYSCALE), open(path, "rb").read() == before


def check(cond, msg):
    if not cond:
        raise SystemExit("FAIL: " + msg)
    print("ok -", msg)


flat = page()
ready, out, same = run(flat)
check(not ready.changed and same and ready.back({"left": 0.1, "top": 0.2, "right": 0.9, "bottom": 0.3}) == {"left": 0.1, "top": 0.2, "right": 0.9, "bottom": 0.3},
      "a flat, clean page is left exactly as it was sent, and positions map to themselves")

bent = page(bend=60)
was = P.lean(bent)
ready, out, same = run(bent)
now = P.lean(out)
check(ready.changed and not same and was > 0.03 and now < 0.25 * was, f"bent staff lines are straightened (mean slope {was:.3f} -> {now:.3f})")
check(any("Straightened" in n for n in ready.notes), "what was done is reported")
# A line of music found near the edge of the straightened page was lower down on the page as sent (the edges sag).
edge = ready.back({"left": 0.02, "top": 0.105, "right": 0.12, "bottom": 0.2})
middle = ready.back({"left": 0.45, "top": 0.105, "right": 0.55, "bottom": 0.2})
check(edge["bottom"] > middle["bottom"] + 0.01 and abs(middle["top"] - 0.105) < 0.01, "positions on the straightened page are mapped back to where they were on the photograph")

two = page(second_page=True, dark_border=True)
ready, out, same = run(two)
ink_right = (P.staff_lines(out)[:, int(out.shape[1] * 0.93):] > 0).sum()
check(ready.changed and any("this page only" in n for n in ready.notes) and out.shape[1] / out.shape[0] < two.shape[1] / two.shape[0], "the edge of a facing page is cut away")
check(max(out.shape) == max(two.shape), "the page is as large after the cut as it was sent")
box = ready.back({"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 1.0})
check(0.0 <= box["left"] < 0.1 and 0.7 < box["right"] < 0.9 and box["top"] < 0.1 and box["bottom"] > 0.9, "positions on the cut page are mapped back onto the whole photograph")
lines_before = (P.staff_lines(two)[:, : int(two.shape[1] * 0.8)] > 0).sum()
kept = (P.staff_lines(cv2.resize(out, (int(out.shape[1] * two.shape[0] / out.shape[0]), two.shape[0]))) > 0).sum()
check(kept > 0.9 * lines_before, "none of this page's staves are lost to the cut")

one_dark = page(dark_border=True)
ready, out, same = run(one_dark)
check(out.shape[0] >= 0.85 * one_dark.shape[0], "a single sheet on a dark desk keeps its full height")
tiny = np.full((300, 300), 255, np.uint8)
ready, out, same = run(tiny)
check(not ready.changed and same, "a picture too small to judge is left alone")
blank = np.full((1200, 900), 250, np.uint8)
ready, out, same = run(blank)
check(not ready.changed and same, "a page with no staves is left alone")
# The top of a photographed page in shadow (a book's curve) is still paper: the title printed there is kept.
shaded = page()
shaded[:200] = (shaded[:200].astype(np.float32) * 0.65).astype(np.uint8)   # paper at about two thirds of its brightness
cv2.putText(shaded, "TITLE", (500, 120), cv2.FONT_HERSHEY_SIMPLEX, 3, 20, 8)
g = P._grey(shaded)
left, top, right, bottom = P.page_box(g)
check(top == 0, f"a page whose top is in shadow keeps its top, title and all (cut at {top})")
desk = page()
desk[:150] = 30                                                              # a dark table above the paper
left, top, right, bottom = P.page_box(P._grey(desk))
check(top >= 100, f"a dark table above the paper is still cut away (cut at {top})")

print("all preparation tests passed")
