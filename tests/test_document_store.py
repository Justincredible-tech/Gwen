"""Tests for gwen.core.document_store — file reading and context injection."""

import tempfile
from pathlib import Path

import pytest

from gwen.core.document_store import DocumentStore, _strip_html


class TestHTMLStripper:
    """Unit tests for the HTML tag stripper."""

    def test_strips_simple_tags(self) -> None:
        raw = "<html><body>Hello <b>world</b></body></html>"
        assert _strip_html(raw) == "Hello world"

    def test_strips_nested_tags(self) -> None:
        raw = "<div><p>Paragraph <span>text</span></p></div>"
        assert _strip_html(raw) == "Paragraph text"

    def test_plain_text_unchanged(self) -> None:
        raw = "Just plain text."
        assert _strip_html(raw) == "Just plain text."

    def test_empty_html(self) -> None:
        assert _strip_html("") == ""

    def test_collapses_whitespace(self) -> None:
        raw = "<p>Line one.</p>\n\n\n<p>Line two.</p>"
        result = _strip_html(raw)
        assert "Line one." in result
        assert "Line two." in result


class TestDocumentStoreBasics:
    """Unit tests for DocumentStore scanning and querying."""

    def test_creates_directory_if_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp) / "nonexistent" / "docs"
            store = DocumentStore(docs_dir=str(docs_dir))
            assert docs_dir.exists()

    def test_scans_txt_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "notes.txt").write_text("Hello from a text file.", encoding="utf-8")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            assert store.exists("notes.txt")
            assert store.get("notes.txt") == "Hello from a text file."

    def test_scans_md_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "README.md").write_text("# Title\n\nBody text.", encoding="utf-8")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            assert store.exists("README.md")
            assert store.get("README.md") == "# Title\n\nBody text."

    def test_scans_html_file_stripped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "page.html").write_text(
                "<html><body><h1>Title</h1><p>Content.</p></body></html>",
                encoding="utf-8",
            )
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            assert store.exists("page.html")
            content = store.get("page.html")
            assert "<html>" not in content
            assert "Title" in content
            assert "Content." in content

    def test_ignores_unsupported_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "image.png").write_bytes(b"\x89PNG")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            assert not store.exists("image.png")

    def test_list_documents_returns_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "a.txt").write_text("Short", encoding="utf-8")
            (docs_dir / "b.md").write_text("# Markdown", encoding="utf-8")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            docs = store.list_documents()
            assert len(docs) == 2
            names = [d[0] for d in docs]
            assert "a.txt" in names
            assert "b.md" in names

    def test_scan_updates_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "notes.txt").write_text("Version 1", encoding="utf-8")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            assert store.get("notes.txt") == "Version 1"
            (docs_dir / "notes.txt").write_text("Version 2", encoding="utf-8")
            store.scan()
            assert store.get("notes.txt") == "Version 2"

    def test_scan_preserves_active_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "notes.txt").write_text("text", encoding="utf-8")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            store.set_active("notes.txt")
            (docs_dir / "extra.md").write_text("md", encoding="utf-8")
            store.scan()
            assert "notes.txt" in store.active_names()


class TestDocumentStoreActivation:
    """Unit tests for activating and deactivating documents."""

    def test_set_active_returns_true_for_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "x.txt").write_text("x", encoding="utf-8")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            assert store.set_active("x.txt") is True
            assert "x.txt" in store.active_names()

    def test_set_active_returns_false_for_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DocumentStore(docs_dir=str(tmp))
            store.scan()
            assert store.set_active("nope.txt") is False

    def test_clear_active_single(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "a.txt").write_text("a", encoding="utf-8")
            (docs_dir / "b.txt").write_text("b", encoding="utf-8")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            store.set_active("a.txt")
            store.set_active("b.txt")
            store.clear_active("a.txt")
            assert store.active_names() == ["b.txt"]

    def test_clear_active_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "a.txt").write_text("a", encoding="utf-8")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            store.set_active("a.txt")
            store.clear_active()
            assert store.active_names() == []


class TestDocumentStoreContextBlock:
    """Unit tests for building the prompt context block."""

    def test_empty_when_no_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DocumentStore(docs_dir=str(tmp))
            assert store.get_context_block() == ""

    def test_includes_active_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "notes.txt").write_text("Important info.", encoding="utf-8")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            store.set_active("notes.txt")
            block = store.get_context_block()
            assert "[USER DOCUMENTS]" in block
            assert "--- notes.txt ---" in block
            assert "Important info." in block

    def test_truncates_long_documents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            long_text = "x" * (DocumentStore.MAX_DOC_LENGTH + 100)
            (docs_dir / "long.txt").write_text(long_text, encoding="utf-8")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            store.set_active("long.txt")
            block = store.get_context_block()
            assert "...[truncated]" in block
            assert len(block) < len(long_text)

    def test_omits_additional_docs_when_total_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            # Two docs that together exceed MAX_TOTAL_LENGTH
            half = DocumentStore.MAX_TOTAL_LENGTH // 2 + 1000
            (docs_dir / "a.txt").write_text("A" * half, encoding="utf-8")
            (docs_dir / "b.txt").write_text("B" * half, encoding="utf-8")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            store.set_active("a.txt")
            store.set_active("b.txt")
            block = store.get_context_block()
            assert "...[additional documents omitted]" in block


class TestDocumentStoreDetection:
    """Unit tests for reference detection in user text."""

    def test_detects_exact_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "notes.txt").write_text("text", encoding="utf-8")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            found = store.detect_references("What do you think about notes.txt?")
            assert "notes.txt" in found

    def test_detects_stem_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "budget.md").write_text("text", encoding="utf-8")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            found = store.detect_references("Tell me about budget")
            assert "budget.md" in found

    def test_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "TODO.html").write_text("text", encoding="utf-8")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            found = store.detect_references("Read todo.html for me")
            assert "TODO.html" in found

    def test_no_false_positives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = Path(tmp)
            (docs_dir / "notes.txt").write_text("text", encoding="utf-8")
            store = DocumentStore(docs_dir=str(docs_dir))
            store.scan()
            found = store.detect_references("I have no notes about this.")
            assert "notes.txt" in found  # "notes" is a stem match
            found2 = store.detect_references("This is completely unrelated.")
            assert "notes.txt" not in found2
