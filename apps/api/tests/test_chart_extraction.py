from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from docling.datamodel.base_models import InputFormat
from docling.datamodel.chart_extraction_options import ChartExtractionModelKind
from docling_core.types.doc.base import BoundingBox
from docling_core.types.doc.common.reference import ProvenanceItem
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.items.picture.meta import PictureMeta, TabularChartMetaField
from docling_core.types.doc.items.table.table_data import TableCell, TableData

from app.services import ingestion


@pytest.mark.parametrize("enabled", [True, False])
def test_chart_pipeline_respects_setting(monkeypatch, enabled):
    monkeypatch.setattr(ingestion.settings, "CHART_EXTRACTION_ENABLED", enabled)
    converter = Mock()
    factory = Mock(return_value=converter)
    monkeypatch.setattr(ingestion, "DocumentConverter", factory)
    ingestion.ingest_document("chart.pdf")
    options = factory.call_args.kwargs["format_options"][InputFormat.PDF].pipeline_options
    assert options.do_ocr is True
    assert options.do_chart_extraction is enabled
    assert options.chart_extraction_options.model == ChartExtractionModelKind.GRANITE_VISION
    assert options.chart_extraction_options.chart2code is False


def test_chart_values_enter_text_with_page_provenance():
    cells = [
        TableCell(
            text=value,
            start_row_offset_idx=row,
            end_row_offset_idx=row + 1,
            start_col_offset_idx=column,
            end_col_offset_idx=column + 1,
            column_header=row == 0,
        )
        for row, values in enumerate([["Quarter", "Sales"], ["Q1", "120"], ["Q2", "180"]])
        for column, value in enumerate(values)
    ]
    doc = DoclingDocument(name="chart-test")
    picture = doc.add_picture(
        prov=ProvenanceItem(page_no=7, bbox=BoundingBox(l=0, t=0, r=100, b=100), charspan=(0, 0)),
    )
    picture.meta = PictureMeta(
        tabular_chart=TabularChartMetaField(
            title="Quarterly sales",
            chart_data=TableData(table_cells=cells, num_rows=3, num_cols=2),
        )
    )
    items = ingestion.extract_text(doc)
    assert len(items) == 1
    assert items[0]["page_start"] == items[0]["page_end"] == 7
    for value in ["Quarterly sales", "Q1", "120", "Q2", "180", "model-extracted"]:
        assert value in items[0]["content"]


def test_picture_without_chart_data_is_not_invented():
    picture = SimpleNamespace(label=SimpleNamespace(value="picture"), meta=None)
    doc = SimpleNamespace(iterate_items=lambda: [(picture, 0)])
    assert ingestion.extract_text(doc) == []
