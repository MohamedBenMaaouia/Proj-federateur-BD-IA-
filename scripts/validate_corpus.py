"""Validate the ingestion corpus in data/raw/ and write data/raw/manifest.json.

Checks, per file type:
- PDF manuals: the file opens, every page is counted, text is extractable
  (not a scanned image), and the extracted text is in the expected language.
- OBD-II code list (JSON): valid JSON, expected schema, every code matches the
  SAE J2012 format (P + 4 hex digits), no duplicate codes, no empty descriptions.

The manifest records size, SHA-256 and the measured properties of each file,
so anyone can confirm they ingest exactly the validated corpus.

Usage:
    pip install pypdf
    python scripts/validate_corpus.py
Exit code 0 = corpus valid, 1 = at least one check failed.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

# Expected corpus: file -> expected language of its text.
MANUALS = {
    "manuals/2017-F-150-Owners-Manual-English.pdf": "en",
    "manuals/2017-F-150-Owners-Manual-French.pdf": "fr",
}
CODES_FILE = "obd_codes.json"
CODE_RE = re.compile(r"^P[0-9A-F]{4}$")

# Very common function words, enough to tell English from French text.
_STOPWORDS = {
    "en": {"the", "and", "of", "to", "is", "in", "your", "with", "for", "vehicle"},
    "fr": {"le", "la", "les", "et", "de", "des", "du", "votre", "pour", "véhicule"},
}

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    print(("  OK    " if condition else "  FAIL  ") + message)
    if not condition:
        failures.append(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def detect_language(text: str) -> str:
    words = re.findall(r"[a-zàâçéèêëîïôûùüÿœ]+", text.lower())
    scores = {lang: sum(w in sw for w in words) for lang, sw in _STOPWORDS.items()}
    return max(scores, key=scores.get)


def validate_pdf(rel: str, expected_lang: str) -> dict:
    path = RAW / rel
    print(f"\n[PDF] {rel}")
    check(path.exists(), "file exists")
    if not path.exists():
        return {}
    reader = PdfReader(str(path))
    n_pages = len(reader.pages)
    check(n_pages > 0, f"{n_pages} pages")

    # Text extraction on a spread of pages (first, middle, last + every 25th).
    sample_idx = sorted({0, n_pages // 2, n_pages - 1, *range(0, n_pages, 25)})
    texts = [reader.pages[i].extract_text() or "" for i in sample_idx]
    with_text = sum(1 for t in texts if len(t.strip()) > 50)
    check(with_text / len(texts) >= 0.8, f"text extractable on {with_text}/{len(texts)} sampled pages (not scanned images)")

    lang = detect_language(" ".join(texts))
    check(lang == expected_lang, f"language detected: {lang} (expected {expected_lang})")

    return {
        "file": f"data/raw/{rel}",
        "type": "pdf",
        "doc_type": "manual",
        "language": expected_lang,
        "pages": n_pages,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def validate_codes(rel: str) -> dict:
    path = RAW / rel
    print(f"\n[JSON] {rel}")
    check(path.exists(), "file exists")
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    codes = data.get("codes", [])
    check(isinstance(codes, list) and len(codes) > 0, f"{len(codes)} codes")
    check(data.get("count") == len(codes), "declared count matches the number of codes")

    bad_format = [c.get("code") for c in codes if not CODE_RE.match(str(c.get("code", "")))]
    check(not bad_format, f"every code matches P + 4 hex digits ({len(bad_format)} invalid)")

    seen, dupes = set(), set()
    for c in codes:
        (dupes if c["code"] in seen else seen).add(c["code"])
    check(not dupes, f"no duplicate codes ({len(dupes)} duplicates)")

    empty = [c["code"] for c in codes if not str(c.get("description", "")).strip()]
    check(not empty, f"every code has a description ({len(empty)} empty)")

    return {
        "file": f"data/raw/{rel}",
        "type": "json",
        "doc_type": "obd_code",
        "language": "en",
        "records": len(codes),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> int:
    print(f"Validating corpus in {RAW}")
    entries = [validate_pdf(rel, lang) for rel, lang in MANUALS.items()]
    entries.append(validate_codes(CODES_FILE))

    manifest = {
        "corpus": "Vehicle diagnostics & maintenance knowledge base",
        "valid": not failures,
        "files": [e for e in entries if e],
        "totals": {
            "files": sum(1 for e in entries if e),
            "pdf_pages": sum(e.get("pages", 0) for e in entries),
            "obd_codes": sum(e.get("records", 0) for e in entries),
        },
    }
    (RAW / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + ("CORPUS VALID" if not failures else f"CORPUS INVALID: {len(failures)} check(s) failed"))
    print(f"Manifest written to {RAW / 'manifest.json'}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
