#!/usr/bin/env python3
"""Seed the inventory database with TrackFlow's opening position.

Records come from CONTEXT-trackflow.md § "Seed Data": 6 SKUs across both
warehouses, 4 goods receipts (two of them for the same SKU), and 3
exits including one dispatch with a tracking number and one loss
without.

Run it:
    uv run seed-inventory          # from services/api/

Idempotent: SKUs are matched on their `sku` code and movements on their
reference / tracking pair, so running it twice inserts nothing the
second time.

Every seeded quantity is applied through the same rules the API
enforces, so the resulting stock is genuinely net entries minus exits —
not a figure written directly.
"""

from __future__ import annotations

import sys

from sqlmodel import Session, select

from database import create_inventory_schema, database_url, inventory_engine
from models import SKU, ExitType, SKUCategory, StockEntry, StockExit, Warehouse

# The seed operative. Movements reference a TinyDB user id as a string;
# "1" is the first account created by the auth seeder.
SEED_USER_UUID = "1"

SKUS: list[dict] = [
    {"name": "Classic White Sneaker - Size 42", "sku": "CLT-SNK-W-42",
     "client_name": "PureStep Footwear", "category": SKUCategory.FASHION,
     "warehouse": Warehouse.LA},
    {"name": "Classic White Sneaker - Size 42", "sku": "CLT-SNK-W-42-Z",
     "client_name": "PureStep Footwear", "category": SKUCategory.FASHION,
     "warehouse": Warehouse.ZGZ},
    {"name": "Wireless Earbuds Pro", "sku": "TEC-EAR-001",
     "client_name": "SoundWave Electronics", "category": SKUCategory.ELECTRONICS,
     "warehouse": Warehouse.LA},
    {"name": "Hydrating Face Serum 30ml", "sku": "CSM-SRM-030",
     "client_name": "GlowLab Cosmetics", "category": SKUCategory.COSMETICS,
     "warehouse": Warehouse.ZGZ},
    {"name": "Slim Fit Chino - Navy 32/32", "sku": "CLT-CHN-N-32",
     "client_name": "UrbanThread", "category": SKUCategory.FASHION,
     "warehouse": Warehouse.LA},
    {"name": "USB-C Fast Charger 65W", "sku": "TEC-CHG-065",
     "client_name": "SoundWave Electronics", "category": SKUCategory.ELECTRONICS,
     "warehouse": Warehouse.ZGZ},
]

# Two receipts for CLT-SNK-W-42 in different quantities, per CONTEXT.
ENTRIES: list[dict] = [
    {"sku": "CLT-SNK-W-42", "quantity": 120,
     "reference": "PO-2024-0098", "warehouse": Warehouse.LA},
    {"sku": "CLT-SNK-W-42", "quantity": 60,
     "reference": "GR-LA-0234", "warehouse": Warehouse.LA},
    {"sku": "TEC-EAR-001", "quantity": 80,
     "reference": "PO-2024-0112", "warehouse": Warehouse.LA},
    {"sku": "CSM-SRM-030", "quantity": 45,
     "reference": "GR-ZGZ-0077", "warehouse": Warehouse.ZGZ},
    {"sku": "CLT-SNK-W-42-Z", "quantity": 90,
     "reference": "PO-2024-0131", "warehouse": Warehouse.ZGZ},
]

# Quantities stay well inside the receipts for the same SKU+warehouse.
EXITS: list[dict] = [
    {"sku": "CLT-SNK-W-42", "quantity": 35, "exit_type": ExitType.DISPATCH,
     "tracking_number": "1Z999AA10123456784", "warehouse": Warehouse.LA},
    {"sku": "TEC-EAR-001", "quantity": 12, "exit_type": ExitType.DISPATCH,
     "tracking_number": "1Z999AA10987654321", "warehouse": Warehouse.LA},
    {"sku": "CSM-SRM-030", "quantity": 3, "exit_type": ExitType.LOSS,
     "tracking_number": None, "warehouse": Warehouse.ZGZ},
]


def seed() -> tuple[int, int, int]:
    """Insert whatever is missing. Returns (skus, entries, exits) added."""
    added_skus = added_entries = added_exits = 0

    with Session(inventory_engine()) as session:
        by_code: dict[str, SKU] = {}

        for row in SKUS:
            existing = session.exec(select(SKU).where(SKU.sku == row["sku"])).first()
            if existing is None:
                existing = SKU(**row)
                session.add(existing)
                session.commit()
                session.refresh(existing)
                added_skus += 1
            by_code[row["sku"]] = existing

        for row in ENTRIES:
            sku = by_code[row["sku"]]
            already = session.exec(
                select(StockEntry)
                .where(StockEntry.sku_id == sku.id)
                .where(StockEntry.reference == row["reference"])
            ).first()
            if already is not None:
                continue
            session.add(StockEntry(
                sku_id=sku.id, quantity=row["quantity"], reference=row["reference"],
                warehouse=row["warehouse"], user_uuid=SEED_USER_UUID,
            ))
            added_entries += 1
        session.commit()

        for row in EXITS:
            sku = by_code[row["sku"]]
            query = select(StockExit).where(StockExit.sku_id == sku.id)
            query = (
                query.where(StockExit.tracking_number == row["tracking_number"])
                if row["tracking_number"]
                else query.where(StockExit.exit_type == ExitType.LOSS)
            )
            if session.exec(query).first() is not None:
                continue
            session.add(StockExit(
                sku_id=sku.id, quantity=row["quantity"], exit_type=row["exit_type"],
                tracking_number=row["tracking_number"], warehouse=row["warehouse"],
                user_uuid=SEED_USER_UUID,
            ))
            added_exits += 1
        session.commit()

    return added_skus, added_entries, added_exits


def report() -> None:
    """Print the resulting net stock, so the seed can be eyeballed."""
    from routers.inventory import _stock_by_warehouse

    with Session(inventory_engine()) as session:
        skus = session.exec(select(SKU)).all()
        totals = _stock_by_warehouse(session, [s.id for s in skus if s.id])
        print("\n  net stock (entries minus exits), per SKU per warehouse:")
        for sku in sorted(skus, key=lambda s: s.sku):
            stock = totals.get((sku.id, sku.warehouse.value), 0)
            print(f"    {sku.sku:16} {sku.warehouse.value:4} {stock:>5}   {sku.name}")


def main() -> int:
    print("TrackFlow — inventory seeder")

    if database_url() is None:
        print(
            "\n  FAILED: DATABASE_URL is not set. Add the Supabase connection "
            "string to services/api/.env — see .env.example.",
            file=sys.stderr,
        )
        return 2

    try:
        create_inventory_schema()
        skus, entries, exits = seed()
    except Exception as exc:
        print(f"\n  FAILED: could not seed the inventory database ({exc})", file=sys.stderr)
        return 1

    print(f"  SKUs added ........ {skus}")
    print(f"  entries added ..... {entries}")
    print(f"  exits added ....... {exits}")
    if not any((skus, entries, exits)):
        print("\n  Nothing to do — the inventory was already seeded.")
    report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
