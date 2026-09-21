# textreflow

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22872013.svg)](https://doi.org/10.5281/zenodo.22872013)
[![PyPI](https://img.shields.io/pypi/v/textreflow.svg)](https://pypi.org/project/textreflow/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Layout regions in, ordered prose out. A layout detector (Docling, YOLO,
Surya, LayoutParser, PaddleOCR, …) tells you *where* the title, the paragraphs
and the tables are on each page. It does not tell you the order to read them
in, or that the paragraph cut off at the bottom of the left column continues at
the top of the right one. textreflow is the step in between:

```
PDF ──▶ layout detector ──▶ regions ──▶ textreflow ──▶ typed blocks ──▶ chunker
```

- **Column-aware reading order.** Full-width bands (title, abstract, wide
  figures) first, then the left column top to bottom, then the right.
- **Paragraphs rebuilt** across regions, columns and page breaks. A paragraph
  stays open until a sentence ends, and a figure, caption or footnote in
  between does not close it.
- **De-hyphenation from the document itself.** `construc-` + `tion` becomes
  `construction`, but `Edge-` + `centric` stays `Edge-centric` when that
  compound appears unbroken somewhere else in the same document.
- **Structure kept** as block types: title, section, authors, caption, table,
  formula, footnote, list.
- **Page furniture removed** from the flow (running heads, page numbers, text
  inside figures) and returned separately, not thrown away.
- **No dependencies.** Standard library only. No detector is bundled, so
  nothing AGPL comes along with it.

```bash
pip install textreflow
```

## Use

```python
from textreflow import assemble, render_txt

layout = {"pages": [{"page": 0, "width": 612, "regions": [
    {"label": "Text", "bbox": [40, 100, 290, 700], "lines": ["Models have demon-"]},
    {"label": "Text", "bbox": [320, 60, 570, 200], "lines": ["strated it."]},
]}]}

blocks, dropped = assemble(layout)
blocks   # [{"type": "paragraph", "page": 0, "text": "Models have demonstrated it."}]
dropped  # {"page_headers": [], "page_footers": [], "picture_text": []}

print(render_txt(blocks))   # tagged text: "# " title, "## " section, [TABLE] … [/TABLE], …
```

From Docling (install it yourself; textreflow only reads the document object):

```python
from docling.document_converter import DocumentConverter
from textreflow import assemble
from textreflow.adapters.docling import from_docling

doc = DocumentConverter().convert("paper.pdf").document
blocks, dropped = assemble(from_docling(doc))
```

The blocks are exactly the input that
[grain-growth-chunking](https://github.com/mudit-choudhary/grain-growth-chunking)
takes, so the two chain directly:

```python
from grain_growth import chunk_document
chunks, skipped = chunk_document(blocks, filename="paper")
```

## The input contract

For each page: its number, its width, and the regions found on it. A region
has a label, a bounding box, and its text as lines.

```python
{"pages": [
    {"page": 0,                                  # 0-based
     "width": 612.0,                             # same units as bbox
     "regions": [
         {"label": "Text",
          "bbox": [40.0, 100.0, 290.0, 200.0],   # x0, y0, x1, y1, top-left origin
          "lines": ["The construc-", "tion of graphs"]}],
     "swallowed_text": [                         # optional
         {"label": "Picture", "text": "axis"}]}]}
```

| `label` | Becomes |
|---|---|
| `Title` | `title` block |
| `Section-header` | `section` block; closes the open paragraph |
| `Authors` | `authors` block; read on its own, never as part of a column |
| `Text` | prose, merged across regions until a sentence ends |
| `List-item` | consecutive items form one `list` block |
| `Caption`, `Footnote`, `Formula` | their own blocks; an open paragraph continues past them |
| `Table` | `table` block, one row per line |
| `Picture` | nothing; a position anchor only |
| `Page-header`, `Page-footer` | removed from the flow, returned in `dropped` |

Regions can arrive in any order, because reading order is worked out from the
boxes. Any unit works (PDF points, pixels) as long as `bbox` and `width` use
the same one. `lines` must already be in reading order within the region:
grouping words into lines is the detector's job. Put text found inside
pictures in `swallowed_text` if you want it reported in `dropped`. Other keys
(`conf`, `height`, …) are ignored.

Check a layout before you trust the output. A wrong label does not crash
anything: the region is quietly read as prose.

```python
from textreflow import validate_layout
validate_layout(layout)                 # raises ValueError on the first problems
validate_layout(layout, strict=False)   # returns every problem as a list
```

Column geometry can be tuned: `assemble(layout, full_width_fraction=0.6,
single_column_fraction=0.7)`. The defaults are the values used in the
evaluation below.

## Evidence

The measure is the share of paragraphs (over 40 characters) that begin with a
lower-case letter. Each of these is a continuation the parser failed to join
to the paragraph before it. Measured on 60 arXiv papers:

| Pipeline | Paragraphs | Begin mid-sentence |
|---|---:|---:|
| Docling, its own document model | 4,378 | **12.5%** |
| Docling's layout → textreflow | 3,031 | **2.4%** |
| A fine-tuned YOLO layout → textreflow | 3,022 | 4.8% |

Same detector, same boxes: replacing only Docling's assembly step with
textreflow cuts mid-sentence paragraphs about five-fold, from 12.5% to 2.4%.

Source: [`evals/Reports/parser_quality_60.json`](https://github.com/mudit-choudhary/Anneal/blob/main/evals/Reports/parser_quality_60.json)
in the Anneal repository, produced by `evals/scripts/parser_quality_probe.py`.

**What this does not show:**

- These are pooled percentages over all paragraphs. They are not a paired
  per-paper test and have no confidence interval, so the size of the effect
  per document is not established.
- An earlier 5-paper run gave 17.4% against 2.9%. That smaller sample
  overstated Docling's failure rate. Use the 60-paper figures above.
- The metric catches only *missed* merges. A wrong merge (two paragraphs
  joined because the first did not end in `.`, `!` or `?`) does not show up
  in it.
- The heuristics were developed on arXiv-style one- and two-column papers.
  Three-column layouts, right-to-left scripts and forms have not been
  evaluated.

## Development

```bash
pip install -e ".[test]"
pytest -q                      # 40 tests, no network, no detector needed
```

## Citing

If this is useful in your work, please cite it. `CITATION.cff` in this
repository gives GitHub's "Cite this repository" button everything it needs:

> Choudhary, M. (2026). *Textreflow: Reading Order and Paragraph
> Reconstruction for Document Layout Detectors* (version 1.0.0) [Software].
> Zenodo. https://doi.org/10.5281/zenodo.22872013

The DOI above always resolves to the newest version; cite
[10.5281/zenodo.22872014](https://doi.org/10.5281/zenodo.22872014) for 1.0.0
specifically. ORCID: [0009-0003-8880-0925](https://orcid.org/0009-0003-8880-0925).

## Licence

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
