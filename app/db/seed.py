from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.db.connection import execute, fetch_all, fetch_one

SEED_RANDOM_SEED = 42

SKU_DEFS: list[dict] = [
    {
        "sku_code": "KEMEJA-LINEN",
        "product_name": "Kemeja Linen Premium",
        "category": "Kemeja",
        "unit_price": "149000",
        "discount_pct": "30",
        "stock_qty": 45,
        "reorder_point": 10,
        "listed_days_ago": 120,
        "plan_14d_orders": 4,
        "plan_24h_orders": 0,
    },
    {
        "sku_code": "KAOS-PREMIUM",
        "product_name": "Kaos Premium Cotton Combed 30s",
        "category": "Kaos",
        "unit_price": "89000",
        "discount_pct": "0",
        "stock_qty": 22,
        "reorder_point": 15,
        "listed_days_ago": 10,
        "plan_14d_orders": 26,
        "plan_24h_orders": 9,
    },
    {
        "sku_code": "KEMEJA-OXFORD",
        "product_name": "Kemeja Oxford Slim Fit",
        "category": "Kemeja",
        "unit_price": "139000",
        "discount_pct": "10",
        "stock_qty": 18,
        "reorder_point": 10,
        "listed_days_ago": 15,
        "plan_14d_orders": 15,
        "plan_24h_orders": 3,
    },
    {
        "sku_code": "CELANA-CHINO",
        "product_name": "Celana Chino Relaxed Fit",
        "category": "Celana",
        "unit_price": "159000",
        "discount_pct": "0",
        "stock_qty": 30,
        "reorder_point": 12,
        "listed_days_ago": 12,
        "plan_14d_orders": 18,
        "plan_24h_orders": 4,
    },
    {
        "sku_code": "DRESS-VNECK",
        "product_name": "Dress V-Neck A-Line",
        "category": "Dress",
        "unit_price": "179000",
        "discount_pct": "15",
        "stock_qty": 14,
        "reorder_point": 8,
        "listed_days_ago": 9,
        "plan_14d_orders": 12,
        "plan_24h_orders": 2,
    },
    {
        "sku_code": "HOODIE-OVERSIZE",
        "product_name": "Hoodie Oversize Heavyweight",
        "category": "Outerwear",
        "unit_price": "199000",
        "discount_pct": "0",
        "stock_qty": 26,
        "reorder_point": 10,
        "listed_days_ago": 20,
        "plan_14d_orders": 10,
        "plan_24h_orders": 1,
    },
    {
        "sku_code": "BLOUSE-RAYON",
        "product_name": "Blouse Rayon Putih",
        "category": "Blouse",
        "unit_price": "129000",
        "discount_pct": "20",
        "stock_qty": 20,
        "reorder_point": 8,
        "listed_days_ago": 14,
        "plan_14d_orders": 9,
        "plan_24h_orders": 1,
    },
]

SKU_REVIEWS: dict[str, list[tuple[str, int, str, int]]] = {
    "KEMEJA-LINEN": [
        ("Sari A.", 5, "Bahan adem gak gampang lecek, dipakai seharian tetap rapi", 1),
        ("Budi P.", 5, "Pantesan ratingnya bintang 5! Kemejanya enak banget buat kerja", 3),
        ("Rina M.", 5, "Tekstur linennya premium, warnanya juga cantik. Recommended!", 6),
        ("Dewi K.", 5, "Bagus, cuma ukurannya agak gede dikit buat saya", 9),
    ],
    "KAOS-PREMIUM": [
        ("Andi R.", 5, "Adem banget, bahan 30s emang juara! Sudah repeat order 2x", 1),
        ("Maya S.", 5, "Warna gak luntur, ukuran pas. Pengiriman juga cepet", 2),
        ("Fajar N.", 5, "Kualitas oke untuk harga segini, bakal beli lagi", 4),
        ("Intan W.", 4, "Bagus tapi jahitannya kecil di area leher", 7),
    ],
    "KEMEJA-OXFORD": [
        ("Gilang T.", 5, "Jadi andalan kerja, bahannya tebel tapi tetep enak dipake", 1),
        ("Putri L.", 5, "Slim fit-nya pas di badan, gak nerobos. Recommended", 3),
        ("Rizky A.", 5, "Cocok buat acara formal kantor, kualitas premium", 5),
    ],
    "CELANA-CHINO": [
        ("Yoga K.", 5, "Pas dipake malah keliatan rapi, jatuhnya cakep", 2),
        ("Nadia F.", 5, "Bahannya tebal dan gak gampang kusut, worth it", 4),
        ("Dimas H.", 5, "Ukuran standar, gak perlu resize. Enak buat hangout", 6),
    ],
    "DRESS-VNECK": [
        ("Rara P.", 5, "Potongannya manis banget, adem dipake seharian", 1),
        ("Tasya M.", 5, "Langsung jadi favorite! Warnanya sesuai foto", 3),
        ("Nita D.", 5, "Jahitan rapi, bahan jatuh, bakal beli warna lain", 5),
    ],
    "HOODIE-OVERSIZE": [
        ("Kevin S.", 5, "Berat dan tebel, pas buat cuaca dingin", 2),
        ("Ayu B.", 5, "Oversize-nya pas, warnanya juga jarang banget orang punya", 4),
        ("Bagas D.", 5, "Kualitas gak beda sama brand mahal. Mantap", 6),
    ],
    "BLOUSE-RAYON": [
        ("Cantika R.", 5, "Adem dan flowy, cocok buat ke kantor maupun hangout", 1),
        ("Laras W.", 5, "Rayonnya jatuh cantik, gak nerawang. Puas!", 3),
        ("Salsa E.", 5, "Bahannya adem banget, jahitan rapi. Recommended", 5),
    ],
}


def _now() -> datetime:
    return datetime.now(UTC)


def _iso_ago(days: float | None = None, hours: float | None = None) -> datetime:
    now = _now()
    if days is not None:
        return now - timedelta(days=days)
    return now - timedelta(hours=hours or 0)


async def _seed_inventory() -> dict[str, int]:
    sku_ids: dict[str, int] = {}
    for sku in SKU_DEFS:
        row = await fetch_one(
            """
            INSERT INTO inventory
                (sku_code, product_name, category, unit_price, discount_pct,
                 stock_qty, reorder_point, listed_at, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            RETURNING sku_id
            """,
            (
                sku["sku_code"],
                sku["product_name"],
                sku["category"],
                sku["unit_price"],
                sku["discount_pct"],
                sku["stock_qty"],
                sku["reorder_point"],
                _iso_ago(days=sku["listed_days_ago"]),
            ),
        )
        sku_ids[sku["sku_code"]] = row["sku_id"]
    return sku_ids


async def _seed_orders(rng: random.Random, sku_ids: dict[str, int]) -> int:
    total = 0
    code_seq = 1
    for sku in SKU_DEFS:
        sku_id = sku_ids[sku["sku_code"]]
        plan24 = sku["plan_24h_orders"]
        plan14 = sku["plan_14d_orders"]
        hours_list: list[float] = []
        # Deadstock (0 order 24h terakhir) sengaja di-generate 8-14 hari lalu agar
        # benar-benar slow-moving dan lolos filter deadstock (order 7 hari rendah).
        older_lo = 192 if plan24 == 0 else 25
        for _ in range(plan14 - plan24):
            hours_list.append(rng.uniform(older_lo, 336))
        for _ in range(plan24):
            hours_list.append(rng.uniform(0.5, 24))
        hours_list.sort()
        for hours_ago in hours_list:
            qty = rng.randint(1, 3)
            price = Decimal(sku["unit_price"])
            await execute(
                """
                INSERT INTO orders (order_code, sku_id, qty, total_amount, status, created_at)
                VALUES (%s, %s, %s, %s, 'completed', %s)
                """,
                (f"ORD-{code_seq:06d}", sku_id, qty, price * qty, _iso_ago(hours=hours_ago)),
            )
            code_seq += 1
            total += 1
    return total


async def _seed_reviews(sku_ids: dict[str, int]) -> int:
    total = 0
    for sku_code, reviews in SKU_REVIEWS.items():
        for customer_name, rating, review_text, days_ago in reviews:
            await execute(
                """
                INSERT INTO reviews (sku_id, customer_name, rating, review_text, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (sku_ids[sku_code], customer_name, rating, review_text, _iso_ago(days=days_ago)),
            )
            total += 1
    return total


async def seed(force: bool = False) -> dict:
    """Isi dummy data deterministic. Hanya jalan bila inventory kosong (atau --force)."""
    count_row = await fetch_all("SELECT COUNT(*) AS n FROM inventory")
    if count_row[0]["n"] > 0 and not force:
        return {
            "skipped": True,
            "reason": "inventory sudah terisi (pakai --force untuk reset & isi ulang)",
            "existing": count_row[0]["n"],
        }

    if force:
        await execute("DELETE FROM reviews")
        await execute("DELETE FROM orders")
        await execute("DELETE FROM inventory")

    rng = random.Random(SEED_RANDOM_SEED)
    sku_ids = await _seed_inventory()
    orders = await _seed_orders(rng, sku_ids)
    reviews = await _seed_reviews(sku_ids)
    return {
        "skipped": False,
        "inventory": len(SKU_DEFS),
        "orders": orders,
        "reviews": reviews,
    }
