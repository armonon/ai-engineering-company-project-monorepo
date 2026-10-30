from __future__ import annotations

import importlib.util
from pathlib import Path

from rfp_intake import process_rfp

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "data" / "raw" / "rfp" / "modaviva-capstone-demo.pdf"


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_capstone_demo_rfp", ROOT / "scripts" / "build_capstone_demo_rfp.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_versioned_fixture_matches_deterministic_builder():
    assert FIXTURE.read_bytes() == _builder().build_pdf()


def test_capstone_demo_rfp_passes_real_intake_and_routes_like_the_pitch(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RFP_MARKDOWN_DIR", str(tmp_path))
    result = process_rfp(str(FIXTURE), "capstone-demo")

    assert result.status == "intake_complete"
    metadata = result.handoff_payload["metadata"]
    assert metadata["client_name"] == "ModaViva, S.L."
    assert metadata["client_country"] == "Spain"
    assert metadata["currency"] == "EUR"
    assert metadata["departments_needed"] == ["warehouse", "reverse"]
