# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Mudit Choudhary
"""The input contract, whole-document assembly, and the Docling adapter.

The adapter is tested against stand-ins rather than Docling itself: this
package must install and test with no detector present at all.
"""

import pytest

from textreflow import LABELS, assemble, render_txt, validate_layout
from textreflow.adapters.docling import from_docling


def page(regions, n=0, width=612.0, **extra):
    return {"page": n, "width": width, "regions": regions, **extra}


def reg(label, bbox, lines=("x",)):
    return {"label": label, "bbox": list(bbox), "lines": list(lines)}


class TestValidate:
    def test_good_layout_passes(self):
        layout = {"pages": [page([reg("Title", (50, 30, 560, 60)),
                                  reg("Picture", (60, 300, 550, 450), [])],
                                 swallowed_text=[{"label": "Picture", "text": "axis"}])]}
        assert validate_layout(layout) == []

    def test_every_documented_label_is_accepted(self):
        layout = {"pages": [page([reg(label, (0, 0, 10, 10)) for label in sorted(LABELS)])]}
        assert validate_layout(layout) == []

    def test_an_unknown_label_is_caught(self):
        # The assembler would read "Heading" as prose and silently lose the
        # section break, which is far harder to notice than an exception.
        with pytest.raises(ValueError, match="Heading"):
            validate_layout({"pages": [page([reg("Heading", (0, 0, 10, 10))])]})

    def test_collects_every_problem_when_not_strict(self):
        layout = {"pages": [
            {"page": -1, "width": 0, "regions": [
                reg("Text", (10, 0, 5, 10)),                          # x0 > x1
                {"label": "Text", "bbox": [0, 0, 1], "lines": []},     # 3 coords
                {"label": "Text", "bbox": [0, 0, 1, 1], "lines": "a line"},
            ], "swallowed_text": ["axis"]}]}
        assert len(validate_layout(layout, strict=False)) == 6

    def test_not_a_layout(self):
        assert validate_layout([], strict=False) == ["layout must be a dict with a 'pages' list"]


class TestAssemble:
    def test_two_column_paragraph_across_columns_and_furniture(self):
        layout = {"pages": [page([
            reg("Page-header", (40, 10, 570, 25), ["Preprint"]),
            reg("Text", (320, 60, 570, 200), ["strated it."]),
            reg("Text", (40, 100, 290, 700), ["Models have demon-"]),
            reg("Picture", (320, 300, 570, 450), []),
            reg("Page-footer", (40, 780, 570, 795), ["7"]),
        ], swallowed_text=[{"label": "Picture", "text": "axis"},
                           {"label": "Page-header", "text": "Preprint"}])]}
        blocks, dropped = assemble(layout)
        assert blocks == [{"type": "paragraph", "page": 0, "text": "Models have demonstrated it."}]
        assert dropped == {"page_headers": ["Preprint"], "page_footers": ["7"],
                           "picture_text": ["axis"]}

    def test_hyphen_vocab_is_collected_across_the_document(self):
        layout = {"pages": [
            page([reg("Text", (60, 100, 550, 200), ["An edge-centric view."])]),
            page([reg("Text", (60, 100, 550, 200), ["The Edge-", "centric method."])], n=1)]}
        blocks, _ = assemble(layout)
        assert blocks[1]["text"] == "The Edge-centric method."

    def test_column_geometry_is_tunable(self):
        # 300 wide on a 612 page: a column at the default 0.6, full-width at 0.4.
        layout = {"pages": [page([reg("Text", (310, 100, 610, 200), ["right."]),
                                  reg("Text", (0, 300, 300, 400), ["left."])])]}
        assert [b["text"] for b in assemble(layout)[0]] == ["left.", "right."]
        assert [b["text"] for b in assemble(layout, full_width_fraction=0.4)[0]] == ["right.", "left."]

    def test_blocks_render(self):
        blocks, _ = assemble({"pages": [page([reg("Title", (50, 30, 560, 60), ["A Paper"]),
                                              reg("Table", (50, 100, 560, 200), ["| a |", " ", "| b |"])])]})
        assert render_txt(blocks) == "# A Paper\n\n[TABLE]\n| a |\n| b |\n[/TABLE]\n"


# --- Docling stand-ins -------------------------------------------------------

class _BBox:
    def __init__(self, l, t, r, b, origin="CoordOrigin.BOTTOMLEFT"):
        self.l, self.t, self.r, self.b, self.coord_origin = l, t, r, b, origin


class _Prov:
    def __init__(self, page_no, bbox):
        self.page_no, self.bbox = page_no, bbox


class _Item:
    def __init__(self, label, text, page_no=1, bbox=None, orig=None, markdown=None):
        self.label = f"DocItemLabel.{label.upper()}"
        self.text, self.orig, self._md = text, orig, markdown
        self.prov = [_Prov(page_no, bbox or _BBox(40, 700, 290, 600))]

    def export_to_markdown(self, doc):
        if self._md is None:
            raise RuntimeError("no table structure")
        return self._md


class _Size:
    width, height = 612.0, 792.0


class _Page:
    size = _Size()


class _Doc:
    def __init__(self, items, n_pages=1):
        self.pages = {i: _Page() for i in range(1, n_pages + 1)}
        self._items = items

    def iterate_items(self):
        return [(i, 0) for i in self._items]


class TestDoclingAdapter:
    def test_labels_map_boxes_flip_and_pages_become_zero_based(self):
        doc = _Doc([_Item("title", "A Paper", 1, _BBox(50, 760, 560, 730)),
                    _Item("section_header", "3 Method", 2),
                    _Item("text", "line one\nline two", 2),
                    _Item("page_footer", "7", 2),
                    _Item("something_new", "prose", 2)], n_pages=2)
        layout = from_docling(doc)
        assert validate_layout(layout) == []
        p0, p1 = layout["pages"]
        assert (p0["page"], p1["page"]) == (0, 1)
        assert p0["regions"][0]["bbox"] == [50, 32.0, 560, 62.0]    # 792 - 760, 792 - 730
        assert [r["label"] for r in p1["regions"]] == ["Section-header", "Text", "Page-footer", "Text"]
        assert p1["regions"][1]["lines"] == ["line one", "line two"]

    def test_formula_text_falls_back_to_orig(self):
        region = from_docling(_Doc([_Item("formula", "", orig="E = mc^2")]))["pages"][0]["regions"][0]
        assert region["lines"] == ["E = mc^2"]

    def test_tables_arrive_as_markdown_rows(self):
        doc = _Doc([_Item("table", "", markdown="| a | b |\n|---|---|\n\n| 1 | 2 |"),
                    _Item("table", "fallback text")])
        rows = [r["lines"] for r in from_docling(doc)["pages"][0]["regions"]]
        assert rows == [["| a | b |", "|---|---|", "| 1 | 2 |"], ["fallback text"]]

    def test_pictures_are_anchors_and_unplaced_items_are_skipped(self):
        orphan = _Item("text", "no page")
        orphan.prov = []
        doc = _Doc([_Item("picture", "caption-ish"), orphan, _Item("text", "page 3", 3)])
        regions = from_docling(doc)["pages"][0]["regions"]
        assert [(r["label"], r["lines"]) for r in regions] == [("Picture", [])]

    def test_max_pages(self):
        doc = _Doc([_Item("text", "one", 1), _Item("text", "two", 2)], n_pages=2)
        assert [p["page"] for p in from_docling(doc, max_pages=1)["pages"]] == [0]

    def test_output_assembles(self):
        doc = _Doc([_Item("text", "Models have demon-", 1, _BBox(40, 700, 290, 100)),
                    _Item("text", "strated it.", 1, _BBox(320, 730, 570, 600))])
        blocks, _ = assemble(from_docling(doc))
        assert [b["text"] for b in blocks] == ["Models have demonstrated it."]
