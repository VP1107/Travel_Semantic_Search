"""
etl/utils.py
------------
Shared utilities for the ETL pipeline.

Provides:
  - html_strip(text)       : Remove HTML tags and decode entities
  - normalize_text(text)   : Clean whitespace / encoding artifacts
  - get_logger(name)       : Configured logger writing to file + console
"""

import html
import logging
import os
import re
import sys
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# HTML Stripping
# ---------------------------------------------------------------------------

class _HTMLStripper(HTMLParser):
    """Minimal HTML parser that collects visible text only."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def html_strip(text: str | None) -> str:
    """
    Remove all HTML tags from *text* and decode HTML entities.

    Returns an empty string for None / empty input.
    """
    if not text:
        return ""

    # Decode HTML entities first (&amp; &nbsp; &#39; etc.)
    decoded = html.unescape(text)

    # Strip tags using our parser
    stripper = _HTMLStripper()
    stripper.feed(decoded)
    raw = stripper.get_text()

    return normalize_text(raw)


# ---------------------------------------------------------------------------
# Text Normalization
# ---------------------------------------------------------------------------

def normalize_text(text: str | None) -> str:
    """
    Normalize whitespace and remove common encoding artifacts.

    - Collapses multiple spaces / newlines into a single space
    - Strips leading / trailing whitespace
    - Removes zero-width and non-breaking space characters
    """
    if not text:
        return ""

    # Replace non-breaking spaces and zero-width chars
    text = text.replace("\u00a0", " ")   # &nbsp;
    text = text.replace("\u200b", "")    # zero-width space
    text = text.replace("\u200c", "")    # zero-width non-joiner
    text = text.replace("\ufeff", "")    # BOM

    # Collapse whitespace (spaces, tabs, newlines)
    text = re.sub(r"[ \t\r\n]+", " ", text)

    return text.strip()


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

def get_logger(name: str = "etl") -> logging.Logger:
    """
    Return a logger that writes to both console and logs/etl.log.

    Creates the logs directory if it does not exist.
    Safe to call multiple times — handlers are only added once.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        # Already configured — return as-is
        return logger

    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # --- File handler ---
    log_dir = os.environ.get("LOG_DIR", "logs")
    log_file = os.environ.get("LOG_FILE", os.path.join(log_dir, "etl.log"))
    os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else ".", exist_ok=True)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
