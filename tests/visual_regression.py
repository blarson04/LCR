"""
visual_regression.py: golden-image check over the committed report PDFs (B-6).

Renders every page of each committed PDF deliverable to PNG and compares it
against the goldens in tests/goldens/. A page that differs by more than the
tolerance fails, so any visual change to a deliverable must ship with a
deliberate golden update in the same commit (never rubber-stamp: eyeball the
new renders before updating).

    python tests/visual_regression.py            # compare (CI mode)
    python tests/visual_regression.py --update   # regenerate goldens

Requires pypdfium2 + Pillow (requirements-dev.txt).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDENS = ROOT / "tests" / "goldens"
SCALE = 100 / 72  # ~100 dpi: small goldens, plenty for layout diffs
# Fraction of pixels allowed to differ meaningfully before a page fails
# (antialiasing wiggle across pdfium versions stays well under this).
MAX_DIFF_FRACTION = 0.005
PIXEL_TOLERANCE = 24  # per-channel delta below this doesn't count as a diff

PDFS = {
    "report": ROOT / "report" / "Larson_Capital_Research-Report.pdf",
    "methodology": ROOT / "report" / "Larson_Capital_Research_Methodology.pdf",
}


def render(pdf_path: Path):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf_path)
    for i, page in enumerate(doc):
        yield i, page.render(scale=SCALE).to_pil().convert("RGB")


def compare(name: str, pdf_path: Path) -> list[str]:
    from PIL import ImageChops
    from PIL import Image

    problems = []
    gdir = GOLDENS / name
    seen = set()
    for i, img in render(pdf_path):
        gpath = gdir / f"page-{i + 1:02d}.png"
        seen.add(gpath.name)
        if not gpath.exists():
            problems.append(f"{name} page {i + 1}: no golden at {gpath}")
            continue
        gold = Image.open(gpath).convert("RGB")
        if gold.size != img.size:
            problems.append(f"{name} page {i + 1}: size {img.size} vs golden "
                            f"{gold.size}")
            continue
        diff = ImageChops.difference(img, gold)
        hist = diff.convert("L").histogram()
        bad = sum(hist[PIXEL_TOLERANCE:])
        frac = bad / (img.size[0] * img.size[1])
        if frac > MAX_DIFF_FRACTION:
            out = gdir / f"page-{i + 1:02d}.actual.png"
            img.save(out)
            problems.append(f"{name} page {i + 1}: {frac:.2%} of pixels differ "
                            f"(> {MAX_DIFF_FRACTION:.1%}); actual saved to {out}")
    stale = [p.name for p in gdir.glob("page-*.png")
             if p.name not in seen and ".actual" not in p.name]
    for s in sorted(stale):
        problems.append(f"{name}: stale golden {s} (page count changed?)")
    return problems


def update() -> None:
    for name, pdf_path in PDFS.items():
        gdir = GOLDENS / name
        gdir.mkdir(parents=True, exist_ok=True)
        for old in gdir.glob("page-*.png"):
            old.unlink()
        n = 0
        for i, img in render(pdf_path):
            img.save(gdir / f"page-{i + 1:02d}.png")
            n = i + 1
        print(f"{name}: {n} golden pages written to {gdir}")


def main() -> None:
    if "--update" in sys.argv:
        update()
        return
    problems = []
    for name, pdf_path in PDFS.items():
        if not pdf_path.exists():
            problems.append(f"{name}: missing PDF {pdf_path}")
            continue
        if not (GOLDENS / name).exists():
            problems.append(f"{name}: no goldens directory; run with --update")
            continue
        problems += compare(name, pdf_path)
    if problems:
        print("VISUAL REGRESSION FAILURES:")
        for p in problems:
            print("  " + p)
        raise SystemExit(1)
    print("visual regression: OK (all pages match goldens)")


if __name__ == "__main__":
    main()
