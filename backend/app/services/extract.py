"""Text extraction for supported document and image formats."""

import os
import shutil
from pathlib import Path


def _ocr_engine():
    """Load local OCR dependencies and locate the Tesseract executable."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise ValueError(
            "OCR dependencies are missing. From the backend folder run "
            "`python -m pip install -r requirements.txt`, then restart InquireX."
        ) from exc

    configured = os.getenv("TESSERACT_CMD", "").strip()
    candidate = configured or shutil.which("tesseract")
    if not candidate and os.name == "nt":
        common_paths = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR" / "tesseract.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Tesseract-OCR" / "tesseract.exe",
        ]
        local_app_data = os.getenv("LOCALAPPDATA", "").strip()
        if local_app_data:
            common_paths.append(Path(local_app_data) / "Programs" / "Tesseract-OCR" / "tesseract.exe")
        candidate = next((str(path) for path in common_paths if path.is_file()), None)
    if candidate:
        pytesseract.pytesseract.tesseract_cmd = candidate
    else:
        raise ValueError(
            "This file needs OCR, but the Tesseract OCR engine is not installed or not on PATH. "
            "Install Tesseract OCR, restart InquireX, and if needed set TESSERACT_CMD in backend/.env "
            "to the full path of tesseract.exe."
        )
    return pytesseract, Image


def ocr_available() -> bool:
    """Whether Python bindings and a local Tesseract executable can be found."""
    try:
        _ocr_engine()
        return True
    except ValueError:
        return False


def _ocr_image(image):
    pytesseract, _ = _ocr_engine()
    try:
        language = os.getenv("OCR_LANG", "eng").strip() or "eng"
        return pytesseract.image_to_string(image, lang=language, config="--psm 3").strip()
    except pytesseract.pytesseract.TesseractNotFoundError as exc:
        raise ValueError(
            "Tesseract OCR could not be started. Check TESSERACT_CMD in backend/.env, then restart InquireX."
        ) from exc
    except pytesseract.pytesseract.TesseractError as exc:
        raise ValueError(f"Tesseract could not read this page: {exc}") from exc


def _image_from_pixmap(pixmap, image_module):
    """Convert a PyMuPDF RGB pixmap into a Pillow image without disk writes."""
    return image_module.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def extract_pages(path: Path) -> tuple[int, list[tuple[int, str]]]:
    """Return (page_count, [(page_number, text), ...]), OCRing image-only pages locally."""
    ext = path.suffix.lower()

    if ext == ".pdf":
        import fitz  # pymupdf

        extracted = []
        try:
            pdf_document = fitz.open(path)
        except Exception as exc:
            raise ValueError(f"Could not open {path.name} as a PDF: {exc}") from exc

        has_ocr = ocr_available()
        ocr_failed_error = None

        with pdf_document as pdf:
            count = len(pdf)
            for index, page in enumerate(pdf):
                text = page.get_text().strip()
                if len(text) < 20 and has_ocr:
                    try:
                        pytesseract, image_module = _ocr_engine()
                        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csRGB, alpha=False)
                        image = _image_from_pixmap(pixmap, image_module)
                        language = os.getenv("OCR_LANG", "eng").strip() or "eng"
                        ocr_text = pytesseract.image_to_string(image, lang=language, config="--psm 3").strip()
                        if ocr_text and ocr_text != text:
                            text = f"{text}\n{ocr_text}".strip()
                    except pytesseract.pytesseract.TesseractNotFoundError as exc:
                        ocr_failed_error = exc
                    except pytesseract.pytesseract.TesseractError as exc:
                        ocr_failed_error = exc
                    except Exception as exc:
                        ocr_failed_error = exc
                if text:
                    extracted.append((index + 1, text))

        if not extracted:
            if not has_ocr:
                raise ValueError(
                    f"No readable text was found in {path.name}. This file appears to be a scanned or image-based PDF, "
                    "which requires the Tesseract OCR engine. Install Tesseract OCR (see backend/README.md) and restart InquireX."
                )
            if ocr_failed_error:
                raise ValueError(
                    f"OCR could not read text from {path.name}: {ocr_failed_error}"
                ) from ocr_failed_error
            raise ValueError(f"No readable text was found in {path.name}, even after OCR.")
        return count, extracted

    if ext in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not text.strip():
            raise ValueError(f"{path.name} is empty.")
        return 1, [(1, text)]

    if ext in {".png", ".jpg", ".jpeg"}:
        try:
            _, image_module = _ocr_engine()
            with image_module.open(path) as image:
                text = _ocr_image(image).strip()
        except OSError as exc:
            raise ValueError(f"Could not open image {path.name}: {exc}") from exc
        if not text:
            raise ValueError(f"OCR found no readable text in {path.name}.")
        return 1, [(1, text)]

    raise ValueError(f"Unsupported file type: {ext}")
