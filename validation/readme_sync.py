"""Splices the generated summary block into the project's README.md, replacing
whatever was between the markers last time, or appending a new section on first run."""

from pathlib import Path

from validation.summary import END_MARKER, START_MARKER

README_PATH = Path(__file__).parent.parent / "README.md"


def update_readme(new_block, path=README_PATH):
    text = path.read_text(encoding="utf-8")

    if START_MARKER in text and END_MARKER in text:
        start = text.index(START_MARKER)
        end = text.index(END_MARKER) + len(END_MARKER)
        text = text[:start] + new_block + text[end:]
    else:
        text = text.rstrip("\n") + "\n\n" + new_block + "\n"

    path.write_text(text, encoding="utf-8")
