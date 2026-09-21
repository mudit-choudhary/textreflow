# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Mudit Choudhary
"""The input contract.

textreflow consumes the output of a layout detector: per page, the regions it
found, each with a label, a bounding box and the text lines inside it. It never
sees a PDF, an image or a word list — grouping words into lines is the
detector side's job. A layout is a plain dict:

    {"pages": [
        {"page": 0,                        # 0-based page number
         "width": 612.0,                   # page width, same units as bbox
         "regions": [
             {"label": "Text",
              "bbox": [40.0, 100.0, 290.0, 200.0],   # x0, y0, x1, y1; top-left origin
              "lines": ["The construc-", "tion of graphs"]},
             ...],
         "swallowed_text": [               # optional: words kept out of the flow
             {"label": "Picture", "text": "axis"}, ...]},
        ...]}

`label` is one of LABELS. Regions may arrive in any order; reading order is
recomputed from the boxes. Only the horizontal geometry relative to `width`
and the vertical order matter, so any unit works — PDF points, pixels — as long
as bbox and width agree. `lines` are in top-to-bottom order; a region with no
`lines` (a picture) is an anchor only. Other keys (`conf`, `height`, …) are
ignored and may be left in.
"""

from numbers import Real

LABELS = frozenset({
    "Title",           # -> "title" block, `# ` tag
    "Section-header",  # -> "section" block, `## ` tag; closes the open paragraph
    "Authors",         # -> "authors" block; read on its own, never in a column
    "Text",            # prose; merged across regions until a sentence ends
    "List-item",       # consecutive items form one "list" block
    "Caption",         # -> "caption"; does not interrupt an open paragraph
    "Footnote",        # -> "footnote"; does not interrupt an open paragraph
    "Formula",         # -> "formula"; does not interrupt an open paragraph
    "Table",           # -> "table"; one row per line, kept verbatim
    "Picture",         # anchor only; its own text belongs in swallowed_text
    "Page-header",     # removed from the flow, returned in dropped
    "Page-footer",     # removed from the flow, returned in dropped
})


def _number(v):
    return isinstance(v, Real) and not isinstance(v, bool)


def validate_layout(layout, *, strict=True):
    """Check a layout against the contract.

    Returns the list of problems as strings. With `strict` (the default) the
    first problems raise ValueError instead — an unknown label does not crash
    the assembler, it is quietly read as prose, which is harder to notice than
    a failure here.
    """
    problems = []
    pages = layout.get("pages") if isinstance(layout, dict) else None
    if not isinstance(pages, list):
        problems.append("layout must be a dict with a 'pages' list")
        pages = []
    for i, page in enumerate(pages):
        where = f"page {i}"
        if not isinstance(page, dict):
            problems.append(f"{where}: must be a dict, got {type(page).__name__}")
            continue
        n = page.get("page")
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            problems.append(f"{where}: 'page' must be a non-negative integer, got {n!r}")
        w = page.get("width")
        if not _number(w) or w <= 0:
            problems.append(f"{where}: 'width' must be a positive number, got {w!r}")
        regions = page.get("regions")
        if not isinstance(regions, list):
            problems.append(f"{where}: 'regions' must be a list")
            regions = []
        for j, r in enumerate(regions):
            rw = f"{where} region {j}"
            if not isinstance(r, dict):
                problems.append(f"{rw}: must be a dict, got {type(r).__name__}")
                continue
            if r.get("label") not in LABELS:
                problems.append(f"{rw}: label {r.get('label')!r} is not one of {sorted(LABELS)}")
            b = r.get("bbox")
            if not (isinstance(b, (list, tuple)) and len(b) == 4 and all(map(_number, b))):
                problems.append(f"{rw}: bbox must be [x0, y0, x1, y1], got {b!r}")
            elif b[0] > b[2] or b[1] > b[3]:
                problems.append(f"{rw}: bbox {list(b)} has x0 > x1 or y0 > y1")
            lines = r.get("lines", [])
            if not isinstance(lines, list) or not all(isinstance(s, str) for s in lines):
                problems.append(f"{rw}: lines must be a list of strings")
        swallowed = page.get("swallowed_text", [])
        if not isinstance(swallowed, list) or not all(
                isinstance(s, dict) and isinstance(s.get("label"), str) and isinstance(s.get("text"), str)
                for s in swallowed):
            problems.append(f"{where}: swallowed_text must be a list of {{label, text}} dicts")
    if problems and strict:
        raise ValueError("invalid layout — " + "; ".join(problems[:5]))
    return problems
