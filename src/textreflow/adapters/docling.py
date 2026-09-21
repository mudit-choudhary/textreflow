# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Mudit Choudhary
"""Docling -> layout.

Uses only Docling's *layout*: its items' labels, boxes and text. Docling's own
reading order and paragraph model are discarded and rebuilt by textreflow,
which is the whole point — see the README's evidence section.

Docling is never imported here, so `pip install textreflow` pulls in no
detector at all; any object shaped like a `DoclingDocument` works.

    from docling.document_converter import DocumentConverter
    from textreflow import assemble, render_txt
    from textreflow.adapters.docling import from_docling

    doc = DocumentConverter().convert("paper.pdf").document
    blocks, dropped = assemble(from_docling(doc))
    print(render_txt(blocks))

This is the mapping behind the `docling_plus_ours` numbers in Anneal's
evaluation.
"""

# Docling item labels -> textreflow labels. Anything unlisted is read as Text.
LABEL_MAP = {
    "title": "Title",
    "section_header": "Section-header",
    "paragraph": "Text",
    "text": "Text",
    "list_item": "List-item",
    "caption": "Caption",
    "table": "Table",
    "formula": "Formula",
    "footnote": "Footnote",
    "page_header": "Page-header",
    "page_footer": "Page-footer",
    "picture": "Picture",
    "code": "Text",
    "reference": "List-item",
    "checkbox_selected": "Text",
    "checkbox_unselected": "Text",
    "document_index": "Table",
    "key_value_region": "Text",
    "form": "Text",
}


def from_docling(document, max_pages=None):
    """A layout from a `DoclingDocument`: boxes converted to a top-left origin
    in PDF points, tables as Markdown rows, pages 0-based."""
    pages = {}
    for page_no, page in document.pages.items():
        if max_pages is not None and page_no > max_pages:
            continue
        pages[page_no] = {"page": page_no - 1, "width": page.size.width, "height": page.size.height,
                          "regions": [], "swallowed_text": []}

    for item, _level in document.iterate_items():
        label = LABEL_MAP.get(str(getattr(item, "label", "")).split(".")[-1].lower(), "Text")
        if not getattr(item, "prov", None):
            continue
        prov = item.prov[0]
        page = pages.get(prov.page_no)
        if page is None:
            continue
        bb = prov.bbox
        # Docling boxes are usually bottom-left origin; textreflow's are top-left.
        if str(getattr(bb, "coord_origin", "")).lower().endswith("bottomleft"):
            y0, y1 = page["height"] - bb.t, page["height"] - bb.b
        else:
            y0, y1 = bb.t, bb.b
        bbox = [round(bb.l, 2), round(min(y0, y1), 2), round(bb.r, 2), round(max(y0, y1), 2)]

        if label == "Table":
            try:
                md = item.export_to_markdown(document)
            except Exception:                            # noqa: BLE001 - never fail a conversion
                md = getattr(item, "text", "") or ""
            lines = [ln for ln in md.splitlines() if ln.strip()]
        elif label == "Picture":
            lines = []
        else:
            # Docling leaves `.text` empty on some item types and puts the
            # content in `.orig` — formulas are the case that matters here.
            # Reading only `.text` silently discards every equation.
            text = (getattr(item, "text", "") or "").strip() or \
                   (getattr(item, "orig", "") or "").strip()
            lines = [ln for ln in text.splitlines() if ln.strip()] or ([text] if text else [])

        page["regions"].append({"label": label, "conf": 1.0, "bbox": bbox, "lines": lines})

    return {"pages": [pages[k] for k in sorted(pages)]}
