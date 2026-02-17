from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class MarkdownAtom:
    atom_type: str  # heading|paragraph|list|table|code
    text: str
    heading_path: Tuple[str, ...]
    start_line: int
    end_line: int


def _is_heading(line: str) -> Tuple[bool, int, str]:
    s = line.lstrip()
    if not s.startswith("#"):
        return False, 0, ""
    i = 0
    while i < len(s) and s[i] == "#":
        i += 1
    if i == 0 or i > 6:
        return False, 0, ""
    if i < len(s) and s[i] != " ":
        return False, 0, ""
    title = s[i + 1 :].strip()
    return True, i, title


def _is_list_item(line: str) -> bool:
    s = line.lstrip()
    if s.startswith(("-", "*", "+")) and len(s) >= 2 and s[1] == " ":
        return True
    # ordered list: "1. xxx"
    if len(s) >= 3 and s[0].isdigit():
        j = 0
        while j < len(s) and s[j].isdigit():
            j += 1
        if j < len(s) - 1 and s[j : j + 2] == ". ":
            return True
    return False


def _looks_like_table_row(line: str) -> bool:
    s = line.strip()
    return "|" in s and not s.startswith("```")


def parse_markdown_atoms(text: str) -> List[MarkdownAtom]:
    """
    Parse markdown into semantic atoms while tracking the current heading path.

    Atomization rules (pragmatic):
    - Headings update the heading stack, and are emitted as their own atoms.
    - Fenced code blocks (``` ... ```) are single atoms.
    - Tables are groups of consecutive table-like lines.
    - Lists are groups of consecutive list items (including indented continuations).
    - Paragraphs are groups of consecutive non-empty lines.
    """
    lines = text.splitlines()
    atoms: List[MarkdownAtom] = []

    heading_stack: List[Tuple[int, str]] = []  # (level, title)

    i = 0
    while i < len(lines):
        line = lines[i]
        lineno = i + 1

        # Skip blank lines
        if not line.strip():
            i += 1
            continue

        # Fenced code blocks
        if line.strip().startswith("```"):
            fence = line.strip()[:3]
            start = i
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence):
                i += 1
            if i < len(lines):
                i += 1  # include closing fence
            block = "\n".join(lines[start:i]).strip()
            atoms.append(
                MarkdownAtom(
                    atom_type="code",
                    text=block,
                    heading_path=tuple(t for _, t in heading_stack),
                    start_line=start + 1,
                    end_line=i,
                )
            )
            continue

        # Heading
        is_h, level, title = _is_heading(line)
        if is_h:
            # update stack
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            atoms.append(
                MarkdownAtom(
                    atom_type="heading",
                    text=line.strip(),
                    heading_path=tuple(t for _, t in heading_stack),
                    start_line=lineno,
                    end_line=lineno,
                )
            )
            i += 1
            continue

        # Table (consecutive table-like lines)
        if _looks_like_table_row(line):
            start = i
            i += 1
            while i < len(lines) and lines[i].strip() and _looks_like_table_row(lines[i]):
                i += 1
            block = "\n".join(lines[start:i]).strip()
            atoms.append(
                MarkdownAtom(
                    atom_type="table",
                    text=block,
                    heading_path=tuple(t for _, t in heading_stack),
                    start_line=start + 1,
                    end_line=i,
                )
            )
            continue

        # List (group consecutive list-related lines)
        if _is_list_item(line):
            start = i
            i += 1
            while i < len(lines):
                if not lines[i].strip():
                    break
                if _is_list_item(lines[i]) or lines[i].startswith("  ") or lines[i].startswith("\t"):
                    i += 1
                    continue
                break
            block = "\n".join(lines[start:i]).strip()
            atoms.append(
                MarkdownAtom(
                    atom_type="list",
                    text=block,
                    heading_path=tuple(t for _, t in heading_stack),
                    start_line=start + 1,
                    end_line=i,
                )
            )
            continue

        # Paragraph (until blank line or structural marker)
        start = i
        i += 1
        while i < len(lines):
            if not lines[i].strip():
                break
            if lines[i].strip().startswith("```"):
                break
            if _is_heading(lines[i])[0]:
                break
            if _is_list_item(lines[i]):
                break
            # if table row starts, break to let table handler take it
            if _looks_like_table_row(lines[i]):
                break
            i += 1
        block = "\n".join(lines[start:i]).strip()
        atoms.append(
            MarkdownAtom(
                atom_type="paragraph",
                text=block,
                heading_path=tuple(t for _, t in heading_stack),
                start_line=start + 1,
                end_line=i,
            )
        )

    return atoms


@dataclass(frozen=True)
class Chunk:
    text: str
    heading_path: Tuple[str, ...]
    start_line: int
    end_line: int


def atoms_to_chunks(
    atoms: Sequence[MarkdownAtom],
    l_max: int = 1024,
    l_overlap: int = 50,
) -> List[Chunk]:
    """
    Convert semantic atoms into fixed-length windows.

    We first concatenate atoms (with separators) to preserve structure, then
    generate overlapping character windows of size <= l_max with overlap l_overlap.
    """
    if l_max <= 0:
        raise ValueError("l_max must be positive")
    if l_overlap < 0:
        raise ValueError("l_overlap must be >= 0")
    if l_overlap >= l_max:
        raise ValueError("l_overlap must be < l_max")

    # Create a linear stream with lightweight headings context.
    # Keep mapping from character offsets to a (heading_path, line range) anchor.
    parts: List[str] = []
    anchors: List[Tuple[int, Tuple[str, ...], int, int]] = []  # char_offset, heading_path, start_line, end_line

    cur_len = 0
    for a in atoms:
        prefix = ""
        if a.heading_path:
            prefix = " > ".join(a.heading_path) + "\n"
        block = (prefix + a.text).strip() + "\n\n"
        anchors.append((cur_len, a.heading_path, a.start_line, a.end_line))
        parts.append(block)
        cur_len += len(block)

    stream = "".join(parts).strip()
    if not stream:
        return []

    # Sliding window over characters
    chunks: List[Chunk] = []
    start = 0
    n = len(stream)
    step = l_max - l_overlap
    while start < n:
        end = min(start + l_max, n)
        window = stream[start:end].strip()
        if not window:
            start += step
            continue

        # Find nearest anchor at or before `start`
        heading_path: Tuple[str, ...] = tuple()
        start_line = 1
        end_line = 1
        for off, hp, sl, el in anchors:
            if off <= start:
                heading_path = hp
                start_line = sl
                end_line = el
            else:
                break

        chunks.append(
            Chunk(
                text=window,
                heading_path=heading_path,
                start_line=start_line,
                end_line=end_line,
            )
        )
        if end == n:
            break
        start += step

    return chunks

