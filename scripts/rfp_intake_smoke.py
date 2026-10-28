"""Run the dedicated RFP intake graph against one local PDF."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from uuid import uuid4

from rfp_intake import process_rfp


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", help="Path to a PDF RFP")
    parser.add_argument("--ticket-id", default=None)
    args = parser.parse_args()
    result = process_rfp(args.pdf, args.ticket_id or str(uuid4()))
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
