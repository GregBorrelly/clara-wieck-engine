"""The words printed on a page of music: the title, "Andantino", "dim.", "D.C. al Fine", a heading over an exercise.

The reading engine knows music symbols and nothing written out in letters. Here the page is read as text
(Tesseract), line by line, and each line comes back with where it sits, so whoever asked can decide what it is.
Music itself is read as stray letters now and then; only lines the text reader is sure of are kept, and a line
must have a real word in it. Without Tesseract installed the page simply has no words.
"""
from __future__ import annotations

SURE = 80          # Tesseract's confidence (0-100) below which a word is dropped
MIN_LETTERS = 2


def find(path: str) -> list[dict]:
    """Lines of text on the page image: [{text, left, top, right, bottom, size}], positions and size as fractions of the page."""
    try:
        import cv2
        import pytesseract
    except ImportError:
        return []
    img = cv2.imread(path)
    if img is None:
        return []
    H, W = img.shape[:2]
    try:
        d = pytesseract.image_to_data(img, config="--psm 11", output_type=pytesseract.Output.DICT)
    except Exception:  # no Tesseract binary, or it failed on this page: the music is still read
        return []
    lines: dict[tuple, list[int]] = {}
    for i, text in enumerate(d["text"]):
        t = text.strip()
        try:
            conf = float(d["conf"][i])
        except (TypeError, ValueError):
            continue
        if not t or conf < SURE:
            continue
        lines.setdefault((d["block_num"][i], d["par_num"][i], d["line_num"][i]), []).append(i)
    out = []
    for idx in lines.values():
        idx.sort(key=lambda i: d["left"][i])
        # Words far apart on one row are separate things (a title on the left, a composer on the right).
        groups, cur = [], [idx[0]]
        for i in idx[1:]:
            prev = cur[-1]
            gap = d["left"][i] - (d["left"][prev] + d["width"][prev])
            if gap > 2.5 * max(d["height"][prev], d["height"][i]):
                groups.append(cur)
                cur = [i]
            else:
                cur.append(i)
        groups.append(cur)
        for g in groups:
            text = " ".join(d["text"][i].strip() for i in g)
            if sum(ch.isalpha() for ch in text) < MIN_LETTERS:
                continue
            left = min(d["left"][i] for i in g)
            top = min(d["top"][i] for i in g)
            right = max(d["left"][i] + d["width"][i] for i in g)
            bottom = max(d["top"][i] + d["height"][i] for i in g)
            heights = sorted(d["height"][i] for i in g)
            out.append({"text": text, "left": round(left / W, 4), "top": round(top / H, 4), "right": round(right / W, 4),
                        "bottom": round(bottom / H, 4), "size": round(heights[len(heights) // 2] / H, 4)})
    out.sort(key=lambda w: (w["top"], w["left"]))
    return out


HEAD_SURE = 50     # the heading is read on its own, cleaned, so a lower confidence is trusted there


def heading(path: str, music_top: float) -> list[dict]:
    """The lines of text above the first staff (title, subtitle, composer, lyricist), read on their own.

    The page-wide reading misses a heading in the shade of a book's curve, or set in heavy capitals. Here the strip
    above the music is evened out (each spot against its own surroundings) and read twice, as a block of text and as
    scattered text: the first keeps a long title together, the second keeps apart credits stacked in a corner. Where
    the two overlap, the one with more letters read surely stands. A word set in clearly bigger type than its neighbour, with a gap
    between them, starts a new line, so a title and a smaller subtitle beside it come apart. Same form as `find`;
    `music_top` is the first staff's top as a fraction of the page.
    """
    try:
        import cv2
        import pytesseract
    except ImportError:
        return []
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []
    H, W = img.shape
    cut = int(music_top * H)
    if cut < 20:
        return []
    clean = cv2.adaptiveThreshold(img[:cut], 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 15)
    found = []
    for psm in (3, 11):
        try:
            d = pytesseract.image_to_data(clean, config=f"--psm {psm}", output_type=pytesseract.Output.DICT)
        except Exception:
            continue
        found += _lines(d, W, H)
    # Overlapping lines from the two readings: the one with the most letters read surely stands, so a whole title
    # beats the pieces of it, and a whole credit line beats a word or two of it.
    found.sort(key=lambda w: -w["_conf"] * sum(c.isalpha() for c in w["text"]))
    out = []
    for w in found:
        if not any(_overlap(w, o) > 0.3 for o in out):
            out.append(w)
    for w in out:
        w.pop("_conf")
    out.sort(key=lambda w: (w["top"], w["left"]))
    return out


def _overlap(a: dict, b: dict) -> float:
    """How much of the smaller of two boxes the other covers."""
    w = min(a["right"], b["right"]) - max(a["left"], b["left"])
    h = min(a["bottom"], b["bottom"]) - max(a["top"], b["top"])
    if w <= 0 or h <= 0:
        return 0.0
    small = min((a["right"] - a["left"]) * (a["bottom"] - a["top"]), (b["right"] - b["left"]) * (b["bottom"] - b["top"]))
    return w * h / max(small, 1e-9)


def _lines(d: dict, W: int, H: int) -> list[dict]:
    """Tesseract's words gathered into lines, each with its mean confidence."""
    lines: dict[tuple, list[int]] = {}
    for i, text in enumerate(d["text"]):
        try:
            conf = float(d["conf"][i])
        except (TypeError, ValueError):
            continue
        if text.strip() and (conf >= HEAD_SURE or (conf >= 15 and text.strip().lower() in ("music", "words", "by", "lyrics"))):
            lines.setdefault((d["block_num"][i], d["par_num"][i], d["line_num"][i]), []).append(i)
    out = []
    for idx in lines.values():
        idx.sort(key=lambda i: d["left"][i])
        groups, cur = [], [idx[0]]
        for i in idx[1:]:
            prev = cur[-1]
            gap = d["left"][i] - (d["left"][prev] + d["width"][prev])
            big, small = max(d["height"][prev], d["height"][i]), min(d["height"][prev], d["height"][i])
            if gap > 2.5 * big or (big > 1.35 * small and gap > 0.5 * small):
                groups.append(cur)
                cur = [i]
            else:
                cur.append(i)
        groups.append(cur)
        for g in groups:
            text = " ".join(d["text"][i].strip() for i in g)
            if sum(ch.isalpha() for ch in text) < MIN_LETTERS:
                continue
            left, top = min(d["left"][i] for i in g), min(d["top"][i] for i in g)
            right, bottom = max(d["left"][i] + d["width"][i] for i in g), max(d["top"][i] + d["height"][i] for i in g)
            heights = sorted(d["height"][i] for i in g)
            out.append({"text": text, "left": round(left / W, 4), "top": round(top / H, 4), "right": round(right / W, 4),
                        "bottom": round(bottom / H, 4), "size": round(heights[len(heights) // 2] / H, 4), "heading": True,
                        "_conf": sum(float(d["conf"][i]) for i in g) / len(g)})
    return out
