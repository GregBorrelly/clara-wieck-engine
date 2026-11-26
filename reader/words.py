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
