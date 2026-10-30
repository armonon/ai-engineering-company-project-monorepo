"""Build the versioned ModaViva RFP used by the capstone demo.

The capstone runbook needs one prepared, client-valid RFP that routes to the
`warehouse` and `reverse` departments in EUR. The original course fixture is
not versioned, so this script writes a deterministic, text-extractable PDF
from the same ModaViva facts the intake tests already assert.

Run it from the repository root:
    python scripts/build_capstone_demo_rfp.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1] / "data" / "raw" / "rfp" / "modaviva-capstone-demo.pdf"
)

LINES = [
    "REQUEST FOR PROPOSAL (RFP)",
    "Issuing Organization: ModaViva, S.L.",
    "RFP Reference No.: MV-LOG-2026-03",
    "Proposal Due Date: August 28, 2026",
    "",
    "ModaViva is a Spanish ecommerce brand requesting almacenamiento of 15,000 SKUs",
    "near Zaragoza and gestión de devoluciones. We maintain our own carrier and no",
    "last mile service is required.",
]


def _pdf_text(line: str) -> str:
    """Escape one line for a WinAnsi-encoded PDF literal string."""
    escaped = []
    for character in line:
        if character in "\\()":
            escaped.append("\\" + character)
        elif ord(character) < 128:
            escaped.append(character)
        else:
            escaped.append(f"\\{character.encode('cp1252')[0]:03o}")
    return "".join(escaped)


def build_pdf(lines: list[str] = LINES) -> bytes:
    """Return a minimal single-page PDF; output is byte-for-byte deterministic."""
    content_lines = ["BT", "/F1 11 Tf", "15 TL", "72 740 Td"]
    content_lines += [f"({_pdf_text(line)}) Tj T*" for line in lines]
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]

    output = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_offset = len(output)
    output += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    output += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    output += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1)
    output += b"startxref\n%d\n%%%%EOF\n" % xref_offset
    return bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build_pdf())
    print(args.output)


if __name__ == "__main__":
    main()
