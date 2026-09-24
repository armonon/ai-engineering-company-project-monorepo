"""Governed telemetry dimensions for TrackFlow's inventory programme.

The inventory milestone predates the telemetry context and stores a client's
display name on each SKU. Telemetry must never use that name as ``client_id``
or invent an id in the browser, so this module is the small authoritative
registry for the four client brands in the approved seed catalogue.

Minimum stock is also policy, not UI decoration. Each seeded SKU has an
explicit threshold here; an unregistered SKU returns ``None`` and therefore
cannot emit a fabricated threshold event.
"""

from __future__ import annotations

CLIENT_ID_BY_NAME: dict[str, str] = {
    "PureStep Footwear": "client_01JTF000000000000000000001",
    "SoundWave Electronics": "client_01JTF000000000000000000002",
    "GlowLab Cosmetics": "client_01JTF000000000000000000003",
    "UrbanThread": "client_01JTF000000000000000000004",
}

MINIMUM_STOCK_BY_SKU: dict[str, int] = {
    "CLT-SNK-W-42": 25,
    "CLT-SNK-W-42-Z": 20,
    "TEC-EAR-001": 15,
    "CSM-SRM-030": 10,
    "CLT-CHN-N-32": 12,
    "TEC-CHG-065": 15,
}


def telemetry_client_id(client_name: str) -> str | None:
    """Return the opaque registry id, never a hash of the display name."""
    return CLIENT_ID_BY_NAME.get(client_name)


def minimum_stock_for_sku(sku: str) -> int | None:
    """Return the configured per-SKU threshold, or None when ungoverned."""
    return MINIMUM_STOCK_BY_SKU.get(sku)
