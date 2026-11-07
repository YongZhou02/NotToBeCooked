import importlib.util
from pathlib import Path

script = Path(__file__).resolve().parents[1] / "builder/audit_semantic_pdfs.py"
spec = importlib.util.spec_from_file_location("semantic_pdf_audit", script)
assert spec and spec.loader
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_uncertainty_marker_is_not_a_clean_page():
    assert "unverified_content_marker" in audit.inspect_text(
        "[UNVERIFIED VISUAL RELATIONSHIP: verify the arrow]"
    )


def test_text_presence_does_not_assert_semantic_correctness():
    assert audit.inspect_text("A --> B") == []
    assert audit.inspect_text(" \n") == ["no_native_text"]
    assert audit.inspect_text("x\ufffdy") == ["unicode_replacement_character"]
