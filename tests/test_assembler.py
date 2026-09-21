# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Mudit Choudhary
"""Reading order and paragraph assembly, on synthetic regions.

Ported unchanged from Anneal's tests/test_txt_processor.py, where the
assembler was developed.
"""

from textreflow import (
    LayoutAssembler,
    collect_hyphenated_vocab,
    ends_terminally,
    join_lines,
    merge_paragraph,
    order_regions,
    render_txt,
)

PAGE_W = 612.0


def region(label, x0, y0, x1, y1, lines=None):
    return {"label": label, "conf": 0.9, "bbox": [x0, y0, x1, y1],
            "lines": lines if lines is not None else ["placeholder"]}


class TestOrderRegions:
    def test_two_column_reading_order(self):
        title = region("Title", 50, 30, 560, 60, ["A Title"])
        left_top = region("Text", 40, 100, 290, 200, ["left top"])
        left_bottom = region("Text", 40, 220, 290, 400, ["left bottom"])
        right_top = region("Text", 320, 100, 570, 200, ["right top"])
        ordered = order_regions([right_top, left_bottom, title, left_top], PAGE_W)
        assert [r["lines"][0] for r in ordered] == [
            "A Title", "left top", "left bottom", "right top"]

    def test_full_width_region_splits_bands(self):
        fig = region("Picture", 60, 300, 550, 450, [])
        above_left = region("Text", 40, 100, 290, 250, ["above left"])
        above_right = region("Text", 320, 100, 570, 250, ["above right"])
        below_left = region("Text", 40, 500, 290, 600, ["below left"])
        ordered = order_regions([below_left, fig, above_right, above_left], PAGE_W)
        texts = [r["lines"][0] if r["lines"] else "FIG" for r in ordered]
        assert texts == ["above left", "above right", "FIG", "below left"]

    def test_authors_not_pushed_into_columns(self):
        title = region("Title", 50, 30, 560, 60, ["A Title"])
        author = region("Authors", 320, 80, 500, 120, ["Some Author"])
        left_body = region("Text", 40, 140, 290, 700, ["left body"])
        ordered = order_regions([left_body, author, title], PAGE_W)
        assert [r["lines"][0] for r in ordered] == [
            "A Title", "Some Author", "left body"]

    def test_side_by_side_authors_read_left_to_right(self):
        # ACM-style 3-across author block; the y coordinates jitter slightly,
        # which must not reorder them.
        title = region("Title", 50, 30, 560, 60, ["A Title"])
        a1 = region("Authors", 40, 82, 190, 130, ["Author One"])
        a2 = region("Authors", 230, 79, 380, 128, ["Author Two"])
        a3 = region("Authors", 420, 81, 570, 131, ["Author Three"])
        body = region("Text", 40, 160, 290, 700, ["left body"])
        ordered = order_regions([body, a3, a1, title, a2], PAGE_W)
        assert [r["lines"][0] for r in ordered] == [
            "A Title", "Author One", "Author Two", "Author Three", "left body"]

    def test_stacked_authors_keep_top_to_bottom(self):
        a1 = region("Authors", 40, 80, 300, 110, ["First line of authors"])
        a2 = region("Authors", 40, 120, 300, 150, ["Affiliation line"])
        ordered = order_regions([a2, a1], PAGE_W)
        assert [r["lines"][0] for r in ordered] == ["First line of authors", "Affiliation line"]

    def test_mid_page_column_merge_separates_bands(self):
        # YOLO detected a full-width Text block in the middle of a 2-column
        # page: columns above are read first, then it, then columns below.
        above_l = region("Text", 40, 100, 290, 250, ["above left"])
        above_r = region("Text", 320, 100, 570, 250, ["above right"])
        merged = region("Text", 45, 280, 565, 380, ["spans both columns"])
        below_l = region("Text", 40, 400, 290, 600, ["below left"])
        below_r = region("Text", 320, 400, 570, 600, ["below right"])
        ordered = order_regions([below_r, above_r, merged, below_l, above_l], PAGE_W)
        assert [r["lines"][0] for r in ordered] == [
            "above left", "above right", "spans both columns", "below left", "below right"]

    def test_page_header_footer_removed(self):
        header = region("Page-header", 40, 10, 570, 25, ["Running head"])
        footer = region("Page-footer", 40, 780, 570, 795, ["7"])
        body = region("Text", 40, 100, 290, 200, ["body"])
        ordered = order_regions([header, body, footer], PAGE_W)
        assert [r["lines"][0] for r in ordered] == ["body"]

    def test_single_column_page(self):
        blocks = [region("Text", 60, 100 + i * 120, 550, 180 + i * 120, [f"p{i}"])
                  for i in (2, 0, 1)]
        ordered = order_regions(blocks, PAGE_W)
        assert [r["lines"][0] for r in ordered] == ["p0", "p1", "p2"]


class TestJoinLines:
    def test_dehyphenation(self):
        assert join_lines(["The construc-", "tion of graphs"]) == "The construction of graphs"

    def test_hyphen_kept_before_uppercase(self):
        assert join_lines(["a non-", "Euclidean space"]) == "a non-Euclidean space"

    def test_plain_join(self):
        assert join_lines(["one two", "three"]) == "one two three"

    def test_compound_hyphen_kept_when_seen_intact_elsewhere(self):
        vocab = {"edge-centric", "state-of-the-art"}
        assert join_lines(["the Edge-", "centric method"], vocab) == "the Edge-centric method"
        assert join_lines(["a state-of-the-", "art model."], vocab) == "a state-of-the-art model."
        # same words, no evidence it's a compound -> wrap hyphen dropped
        assert join_lines(["the Edge-", "centric method"]) == "the Edgecentric method"

    def test_compound_lookup_ignores_punctuation(self):
        assert join_lines(["(Edge-", "centric)."], {"edge-centric"}) == "(Edge-centric)."

    def test_merge_paragraph_uses_vocab(self):
        assert merge_paragraph("uses multi-", "scale features.", {"multi-scale"}) == "uses multi-scale features."
        assert merge_paragraph("uses multi-", "scale features.") == "uses multiscale features."


class TestHyphenVocab:
    def test_collects_intact_compounds_only(self):
        layout = {"pages": [{"regions": [
            {"lines": ["Edge-centric methods [1] and state-of-the-art", "results; a non-"]},
            {"lines": ["Euclidean space"]},
        ]}]}
        assert collect_hyphenated_vocab(layout) == {"edge-centric", "state-of-the-art"}


class TestEndsTerminally:
    def test_period(self):
        assert ends_terminally("This is done.")

    def test_period_inside_quote(self):
        assert ends_terminally('he said "done."')

    def test_open_sentence(self):
        assert not ends_terminally("the model has demonstrated")


class TestAssembler:
    def assemble(self, regions_pages):
        assembler = LayoutAssembler()
        for page_no, regions in enumerate(regions_pages):
            for r in regions:
                assembler.add_region(r, page_no)
        return assembler.finish()

    def test_paragraph_merges_across_pages(self):
        p1 = region("Text", 40, 100, 290, 700, ["Models have demonstrated"])
        p2 = region("Text", 40, 60, 290, 200, ["exceptional capabilities."])
        blocks = self.assemble([[p1], [p2]])
        assert len(blocks) == 1
        assert blocks[0]["text"] == "Models have demonstrated exceptional capabilities."

    def test_terminal_paragraph_not_merged(self):
        p1 = region("Text", 40, 100, 290, 300, ["First paragraph."])
        p2 = region("Text", 40, 320, 290, 500, ["Second paragraph."])
        blocks = self.assemble([[p1, p2]])
        assert [b["text"] for b in blocks] == ["First paragraph.", "Second paragraph."]

    def test_paragraph_stays_open_across_footnote(self):
        p1 = region("Text", 40, 100, 290, 600, ["Sentence that keeps"])
        fn = region("Footnote", 40, 700, 290, 750, ["1 A footnote."])
        p2 = region("Text", 320, 60, 570, 200, ["going after the footnote."])
        blocks = self.assemble([[p1, fn, p2]])
        assert blocks[0]["text"] == "Sentence that keeps going after the footnote."
        assert blocks[1]["type"] == "footnote"

    def test_section_header_closes_paragraph(self):
        p1 = region("Text", 40, 100, 290, 300, ["An unfinished sentence"])
        head = region("Section-header", 40, 320, 290, 340, ["2 Method"])
        p2 = region("Text", 40, 360, 290, 500, ["new section text."])
        blocks = self.assemble([[p1, head, p2]])
        assert [b["type"] for b in blocks] == ["paragraph", "section", "paragraph"]
        assert blocks[0]["text"] == "An unfinished sentence"

    def test_list_items_grouped(self):
        intro = region("Text", 40, 100, 290, 150, ["We contribute:"])
        li1 = region("List-item", 50, 160, 290, 200, ["• first thing"])
        li2 = region("List-item", 50, 210, 290, 250, ["• second thing"])
        blocks = self.assemble([[intro, li1, li2]])
        assert blocks[1]["type"] == "list"
        assert blocks[1]["text"] == "• first thing\n• second thing"

    def test_region_level_dehyphenation_on_merge(self):
        p1 = region("Text", 40, 100, 290, 700, ["a multi-granu-"])
        p2 = region("Text", 320, 60, 570, 200, ["larity approach."])
        blocks = self.assemble([[p1, p2]])
        assert blocks[0]["text"] == "a multi-granularity approach."


class TestRenderTxt:
    def test_tags(self):
        blocks = [
            {"type": "title", "page": 0, "text": "T"},
            {"type": "section", "page": 0, "text": "S"},
            {"type": "authors", "page": 0, "text": "A"},
            {"type": "caption", "page": 1, "text": "C"},
            {"type": "table", "page": 1, "text": "r1\nr2"},
            {"type": "paragraph", "page": 1, "text": "P"},
        ]
        out = render_txt(blocks)
        assert "# T\n\n## S\n\n[AUTHORS] A\n\n[CAPTION] C\n\n[TABLE]\nr1\nr2\n[/TABLE]\n\nP\n" == out
