from __future__ import annotations

import re


_RE_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def clean_markdown(text: str) -> str:
    """
    Lightweight cleaning tailored for DeepWiki markdown exports.

    Goals:
    - Keep semantics (do NOT aggressively rewrite content).
    - Normalize whitespace/newlines to make chunking deterministic.
    """
    if not text:
        return ""

    # Normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Strip HTML comments (often carry non-semantic noise)
    text = _RE_HTML_COMMENT.sub("", text)

    # Remove trailing whitespace per line
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    # Collapse 3+ blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Ensure file ends with newline
    if text and not text.endswith("\n"):
        text += "\n"

    return text

