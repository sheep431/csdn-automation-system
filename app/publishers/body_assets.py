from __future__ import annotations


def insert_header_image_after_first_blockquote(markdown: str, image_markdown: str) -> str:
    if not image_markdown.strip() or image_markdown in markdown:
        return markdown

    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    quote_started = False
    insert_at: int | None = None

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if line.startswith(">"):
            quote_started = True
            continue
        if quote_started and stripped == "":
            insert_at = idx + 1
            break
        if quote_started and not line.startswith(">"):
            insert_at = idx
            break

    if insert_at is None:
        suffix = "\n\n" if not markdown.endswith("\n") else "\n"
        return markdown + suffix + image_markdown + "\n"

    new_lines = lines[:insert_at] + [image_markdown, ""] + lines[insert_at:]
    return "\n".join(new_lines)
