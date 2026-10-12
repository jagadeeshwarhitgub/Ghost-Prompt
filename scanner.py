"""
Core detection engine.

scan_file(path) -> dict with:
    risk_score   (0-100)
    risk_level   ("Low" | "Medium" | "High" | "Critical")
    findings     list of {type, detail, severity}
    clean_text   the text that's SAFE to send to the LLM (visible text only)
    raw_text     everything extracted from the text layer (for the demo toggle)
"""
import re
import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path

INSTRUCTION_PATTERNS = [
    r"ignore (the )?(previous|prior|above|user'?s?) instructions?",
    r"disregard (the )?(previous|prior|above) (instructions?|request)",
    r"system\s*:",
    r"you are now",
    r"act as",
    r"reveal (any )?(api key|credential|password|secret)",
    r"search .*(drive|email|inbox|files?) for",
    r"send (this|the|it) to",
    r"email .* to",
    r"exfiltrate",
    r"assistant\s*:",
    r"new instructions?",
]

SEVERITY_WEIGHTS = {
    "invisible_text": 40,
    "tiny_font": 30,
    "suspicious_metadata": 20,
    "instruction_pattern": 35,
    "offpage_text": 25,
}


def _extract_text_layer_with_style(doc):
    """Pull every text span with its font size, color, and position."""
    spans = []
    for page_num, page in enumerate(doc):
        d = page.get_text("dict")
        page_rect = page.rect
        for block in d.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    spans.append({
                        "page": page_num,
                        "text": span["text"],
                        "size": span["size"],
                        "color": span["color"],  # int, decode below
                        "bbox": span["bbox"],
                        "page_rect": page_rect,
                    })
    return spans


def _color_int_to_rgb(c):
    return ((c >> 16) & 255, (c >> 8) & 255, c & 255)


def _ocr_page_text(pdf_path, page_num):
    images = convert_from_path(pdf_path, first_page=page_num + 1, last_page=page_num + 1)
    if not images:
        return ""
    return pytesseract.image_to_string(images[0])


def scan_file(pdf_path):
    findings = []
    doc = fitz.open(pdf_path)

    spans = _extract_text_layer_with_style(doc)
    raw_text_parts = []
    visible_text_parts = []
    hidden_text_parts = []

    # cache OCR per page so we don't redo it per span
    ocr_cache = {}

    for span in spans:
        text = span["text"].strip()
        if not text:
            continue
        raw_text_parts.append(text)

        page_num = span["page"]
        size = span["size"]
        r, g, b = _color_int_to_rgb(span["color"])
        x0, y0, x1, y1 = span["bbox"]
        page_rect = span["page_rect"]

        is_suspicious = False

        # Check 1: near-white text (assume white/near-white page background)
        if r > 240 and g > 240 and b > 240:
            findings.append({
                "type": "invisible_text",
                "detail": f"Page {page_num+1}: white/near-white colored text found: \"{text[:80]}\"",
                "severity": SEVERITY_WEIGHTS["invisible_text"],
            })
            is_suspicious = True

        # Check 2: tiny font size
        if size < 2:
            findings.append({
                "type": "tiny_font",
                "detail": f"Page {page_num+1}: font size {size:.2f}pt (effectively invisible): \"{text[:80]}\"",
                "severity": SEVERITY_WEIGHTS["tiny_font"],
            })
            is_suspicious = True

        # Check 3: off-page positioning
        if x1 < 0 or y1 < 0 or x0 > page_rect.width or y0 > page_rect.height:
            findings.append({
                "type": "offpage_text",
                "detail": f"Page {page_num+1}: text positioned outside visible page area: \"{text[:80]}\"",
                "severity": SEVERITY_WEIGHTS["offpage_text"],
            })
            is_suspicious = True

        if is_suspicious:
            hidden_text_parts.append(text)
        else:
            visible_text_parts.append(text)

    # Check 4: instruction-like language anywhere in hidden text (highest signal)
    combined_hidden = " ".join(hidden_text_parts)
    for pattern in INSTRUCTION_PATTERNS:
        m = re.search(pattern, combined_hidden, re.IGNORECASE)
        if m:
            findings.append({
                "type": "instruction_pattern",
                "detail": f"Hidden text matches instruction pattern: \"{m.group(0)}\"",
                "severity": SEVERITY_WEIGHTS["instruction_pattern"],
            })

    # Also scan ALL text (visible + hidden) for instruction patterns, lower confidence if visible-only
    full_text = " ".join(raw_text_parts)

    # Check 5: metadata
    meta = doc.metadata or {}
    for field, value in meta.items():
        if not value:
            continue
        for pattern in INSTRUCTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                findings.append({
                    "type": "suspicious_metadata",
                    "detail": f"Metadata field '{field}' contains instruction-like text: \"{value[:100]}\"",
                    "severity": SEVERITY_WEIGHTS["suspicious_metadata"],
                })

    # Check 6 (optional but powerful): visible-vs-OCR diff on page 1
    # Compares what a human sees (OCR of rendered page) vs raw text layer
    try:
        ocr_text = _ocr_page_text(pdf_path, 0)
        ocr_words = set(re.findall(r"\w+", ocr_text.lower()))
        raw_words = set(re.findall(r"\w+", full_text.lower()))
        missing_from_render = raw_words - ocr_words
        # filter noise: only flag if a meaningful chunk of unique words is missing
        if len(missing_from_render) > 5:
            findings.append({
                "type": "invisible_text",
                "detail": f"Text-layer contains {len(missing_from_render)} words not visible in the rendered page image (page 1) — likely hidden content.",
                "severity": SEVERITY_WEIGHTS["invisible_text"],
            })
    except Exception as e:
        pass  # OCR is best-effort for the demo; don't crash the scan

    # --- Score ---
    risk_score = min(100, sum(f["severity"] for f in findings))
    if risk_score >= 70:
        risk_level = "Critical"
    elif risk_score >= 45:
        risk_level = "High"
    elif risk_score >= 20:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    doc.close()

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "findings": findings,
        "clean_text": " ".join(visible_text_parts),
        "raw_text": full_text,
        "hidden_text": combined_hidden,
        "hidden_segments": hidden_text_parts,
    }
