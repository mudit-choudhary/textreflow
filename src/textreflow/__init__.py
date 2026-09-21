# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Mudit Choudhary
"""textreflow — layout regions to ordered, typed prose.

The stage between a layout detector and a chunker: column-aware reading order,
paragraphs rebuilt across regions, columns and pages with de-hyphenation,
structure kept as block types, page furniture removed from the flow.

    from textreflow import assemble, render_txt

    layout = {"pages": [{"page": 0, "width": 612, "regions": [
        {"label": "Text", "bbox": [40, 100, 290, 700], "lines": ["Models have demon-"]},
        {"label": "Text", "bbox": [320, 60, 570, 200], "lines": ["strated it."]}]}]}
    blocks, dropped = assemble(layout)
    # [{"type": "paragraph", "page": 0, "text": "Models have demonstrated it."}]

`textreflow.layout` documents the input contract; `textreflow.adapters` turns
a detector's output into it. The blocks are the input contract of
`grain_growth` (pip install grain-growth-chunking).
"""

from .assembler import (
    FULL_WIDTH_FRACTION,
    NOISE_LABELS,
    SINGLE_COLUMN_FRACTION,
    TERMINAL_CHARS,
    LayoutAssembler,
    assemble,
    collect_hyphenated_vocab,
    ends_terminally,
    join_hyphenated,
    join_lines,
    merge_paragraph,
    order_regions,
    render_txt,
)
from .layout import LABELS, validate_layout

__version__ = "1.0.0"

__all__ = [
    "FULL_WIDTH_FRACTION", "LABELS", "LayoutAssembler", "NOISE_LABELS",
    "SINGLE_COLUMN_FRACTION", "TERMINAL_CHARS", "assemble", "collect_hyphenated_vocab",
    "ends_terminally", "join_hyphenated", "join_lines", "merge_paragraph",
    "order_regions", "render_txt", "validate_layout", "__version__",
]
