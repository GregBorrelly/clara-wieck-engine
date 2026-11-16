"""Turn an upload (image or PDF) into page images on disk, ready for an engine."""
from __future__ import annotations

import os

from PIL import Image, ImageOps

PDF_DPI = 300
MAX_SIDE = 4200  # about A4 at 360 dpi; larger only slows the engine down


class BadUpload(ValueError):
    pass


def is_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def save_pages(data: bytes, workdir: str, max_pages: int = 40) -> list[str]:
    """Write each page as a PNG in `workdir` and return the paths, in order."""
    paths: list[str] = []
    if is_pdf(data):
        import pypdfium2 as pdfium

        try:
            doc = pdfium.PdfDocument(data)
        except Exception as e:  # pdfium raises its own error types
            raise BadUpload(f"couldn't open the PDF: {e}") from None
        if len(doc) > max_pages:
            raise BadUpload(f"the PDF has {len(doc)} pages; the limit is {max_pages}")
        for i in range(len(doc)):
            page = doc[i]
            w, h = page.get_size()  # points (1/72 inch)
            scale = min(PDF_DPI / 72, MAX_SIDE / max(w, h))
            img = page.render(scale=scale, grayscale=True).to_pil()
            path = os.path.join(workdir, f"page{i + 1:03d}.png")
            img.save(path)
            paths.append(path)
        return paths
    try:
        img = Image.open(_bytes_io(data))
        img = ImageOps.exif_transpose(img)  # phone photos store their rotation separately
    except Exception:
        raise BadUpload("that file isn't an image or a PDF this service can read") from None
    if img.mode not in ("RGB", "L"):
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
        img = bg
    if max(img.size) > MAX_SIDE:
        k = MAX_SIDE / max(img.size)
        img = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
    path = os.path.join(workdir, "page001.png")
    img.save(path)
    return [path]


def _bytes_io(data: bytes):
    import io

    return io.BytesIO(data)
