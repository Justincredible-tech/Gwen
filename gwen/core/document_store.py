"""Document Store — reads user-provided files for companion context.

Scans a working directory for .txt, .md, and .html files, strips HTML tags,
and makes content available for injection into the conversation context.
"""

import logging
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Supported file extensions and their descriptions.
SUPPORTED_EXTS = {".txt": "text", ".md": "markdown", ".html": "html"}


class _HTMLStripper(HTMLParser):
    """Strip HTML tags, keeping the text content."""

    def __init__(self) -> None:
        super().__init__()
        self._text_parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._text_parts.append(data)

    def get_text(self) -> str:
        return "".join(self._text_parts)


def _strip_html(raw: str) -> str:
    """Remove HTML tags from a string."""
    stripper = _HTMLStripper()
    stripper.feed(raw)
    # Collapse excessive whitespace
    text = stripper.get_text()
    return re.sub(r"\n\s*\n", "\n\n", text).strip()


def _read_file(path: Path) -> str:
    """Read a supported file and return plain text content.

    Parameters
    ----------
    path : Path
        File to read.

    Returns
    -------
    str
        Plain-text content.  HTML is stripped.  Decoding errors are
        replaced so the file is never unreadable.
    """
    ext = path.suffix.lower()
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return ""

    if ext == ".html":
        return _strip_html(raw)
    return raw


class DocumentStore:
    """Manages a user document directory and makes files available as context.

    Usage
    -----
    >>> store = DocumentStore("~/.gwen/docs")
    >>> store.scan()               # (re-)load all files from disk
    >>> store.list()               # list available document names
    >>> store.set_active("notes.md")   # include in next prompt
    >>> store.get_context_block()  # formatted string for the prompt
    """

    # Maximum characters per document when injected into context.
    MAX_DOC_LENGTH = 8_000
    # Maximum total characters for the combined context block.
    MAX_TOTAL_LENGTH = 16_000

    def __init__(self, docs_dir: str = "~/.gwen/docs") -> None:
        """Create the store.

        Parameters
        ----------
        docs_dir : str
            Path to the working directory. Created if it does not exist.
        """
        self.docs_path = Path(docs_dir).expanduser()
        self.docs_path.mkdir(parents=True, exist_ok=True)
        # Map filename -> content
        self._documents: dict[str, str] = {}
        # Filenames currently marked active for context injection
        self._active: set[str] = set()
        logger.info("DocumentStore ready: %s", self.docs_path.resolve())

    # -- scanning -----------------------------------------------------------

    def scan(self) -> None:
        """Re-read every supported file in the working directory.

        Existing content is replaced.  Active flags are preserved for
        files that still exist.
        """
        old_active = self._active.copy()
        self._documents.clear()
        self._active.clear()

        if not self.docs_path.exists():
            logger.warning("Docs directory does not exist: %s", self.docs_path)
            return

        for path in sorted(self.docs_path.iterdir()):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS:
                content = _read_file(path)
                if content:
                    self._documents[path.name] = content
                    if path.name in old_active:
                        self._active.add(path.name)

        logger.info(
            "Scanned %d document(s) from %s",
            len(self._documents),
            self.docs_path,
        )

    # -- querying -----------------------------------------------------------

    def list_documents(self) -> list[tuple[str, str, int]]:
        """Return metadata for every document in the store.

        Returns
        -------
        list[tuple[str, str, int]]
            Each tuple is (filename, type_label, length).
        """
        result: list[tuple[str, str, int]] = []
        for name in sorted(self._documents):
            ext = Path(name).suffix.lower()
            label = SUPPORTED_EXTS.get(ext, "unknown")
            length = len(self._documents[name])
            result.append((name, label, length))
        return result

    def get(self, name: str) -> Optional[str]:
        """Return the full content of a document by filename.

        Returns ``None`` if the file is not in the store.
        """
        return self._documents.get(name)

    def exists(self, name: str) -> bool:
        """True if the named document is loaded in the store."""
        return name in self._documents

    # -- active-document management -----------------------------------------

    def set_active(self, name: str) -> bool:
        """Mark a document as active (will be included in context).

        Parameters
        ----------
        name : str
            Exact filename as shown by ``list()``.

        Returns
        -------
        bool
            ``True`` if the document exists and was activated.
        """
        if name not in self._documents:
            logger.warning("Cannot activate '%s' — not found in store", name)
            return False
        self._active.add(name)
        logger.info("Document activated: %s", name)
        return True

    def clear_active(self, name: Optional[str] = None) -> None:
        """Deactivate one or all documents.

        Parameters
        ----------
        name : str | None
            Filename to deactivate.  If ``None``, clear everything.
        """
        if name is None:
            self._active.clear()
            logger.info("All documents deactivated")
        elif name in self._active:
            self._active.discard(name)
            logger.info("Document deactivated: %s", name)

    def active_names(self) -> list[str]:
        """Return the list of currently active document filenames."""
        return sorted(self._active)

    # -- context injection --------------------------------------------------

    def get_context_block(self) -> str:
        """Build a formatted context block from active documents.

        Each document is truncated to ``MAX_DOC_LENGTH``.  The total
        block is truncated to ``MAX_TOTAL_LENGTH``.  Returns an empty
        string when no documents are active.

        Returns
        -------
        str
            Formatted block ready for inclusion in a system or user
            prompt.
        """
        if not self._active:
            return ""

        parts: list[str] = []
        total = 0

        for name in sorted(self._active):
            content = self._documents.get(name, "")
            # Truncate per-document
            if len(content) > self.MAX_DOC_LENGTH:
                content = content[: self.MAX_DOC_LENGTH] + "\n...[truncated]"
            block = f"--- {name} ---\n{content}"
            total += len(block)
            if total > self.MAX_TOTAL_LENGTH:
                parts.append("...[additional documents omitted]")
                break
            parts.append(block)

        if not parts:
            return ""

        return "\n\n".join(["[USER DOCUMENTS]"] + parts)

    # -- auto-detection from user text --------------------------------------

    def detect_references(self, text: str) -> list[str]:
        """Scan user text for filenames that match documents in the store.

        A reference is counted when a document filename (or its stem,
        e.g. ``notes`` for ``notes.md``) appears as a whole word in the
        text.

        Parameters
        ----------
        text : str
            User message to scan.

        Returns
        -------
        list[str]
            Matching document filenames (not stems).
        """
        found: list[str] = []
        for name in self._documents:
            # Match exact filename or stem as whole words
            stem = Path(name).stem
            pattern = re.compile(rf"\b({re.escape(name)}|{re.escape(stem)})\b", re.IGNORECASE)
            if pattern.search(text):
                found.append(name)
        return found
