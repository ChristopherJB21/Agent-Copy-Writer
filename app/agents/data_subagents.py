"""Sub-agents data: 3 fungsi SQL (bukan agent LLM) yang menghasilkan context dict
untuk diinjeksi ke prompt copywriter & reviewer (lightweight context injection)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.db.connection import fetch_all, fetch_one

DEADSTOCK_MIN_STOCK = 40
DEADSTOCK_MIN_AGE_DAYS = 30
DEADSTOCK_MAX_ORDERS_7D = 2

SALES_VELOCITY_SQL = """
    SELECT i.sku_id,
           i.sku_code,
           i.product_name,
           i.category,
           i.unit_price,
           i.discount_pct,
           i.stock_qty,
           COUNT(o.order_id) FILTER (
               WHERE o.created_at >= now() - interval '24 hours'
           ) AS orders_24h,
           COUNT(o.order_id) FILTER (
               WHERE o.created_at >= now() - interval '7 days'
           ) AS orders_7d,
           COALESCE(SUM(o.total_amount) FILTER (
               WHERE o.created_at >= now() - interval '7 days'
           ), 0) AS revenue_7d
    FROM inventory i
    LEFT JOIN orders o ON o.sku_id = i.sku_id
    WHERE i.is_active = TRUE
    GROUP BY i.sku_id
    ORDER BY orders_24h DESC, orders_7d DESC
    LIMIT 3
"""

DEADSTOCK_SQL = """
    SELECT i.sku_id,
           i.sku_code,
           i.product_name,
           i.category,
           i.unit_price,
           i.discount_pct,
           i.stock_qty,
           i.listed_at,
           COUNT(o.order_id) FILTER (
               WHERE o.created_at >= now() - interval '7 days'
           ) AS orders_7d
    FROM inventory i
    LEFT JOIN orders o ON o.sku_id = i.sku_id
    WHERE i.is_active = TRUE
      AND i.stock_qty >= %s
      AND i.listed_at <= now() - (%s::int * interval '1 day')
    GROUP BY i.sku_id
    HAVING COUNT(o.order_id) FILTER (
        WHERE o.created_at >= now() - interval '7 days'
    ) <= %s
    ORDER BY i.stock_qty DESC
    LIMIT 3
"""

SOCIAL_PROOF_SQL = """
    SELECT review_id, sku_id, customer_name, rating, review_text, created_at
    FROM reviews
    WHERE sku_id = %s AND rating = 5
    ORDER BY created_at DESC
    LIMIT 3
"""

RATING_SQL = """
    SELECT COUNT(*) AS total_reviews,
           ROUND(AVG(rating)::numeric, 1) AS avg_rating
    FROM reviews
    WHERE sku_id = %s
"""


async def get_sales_velocity() -> list[dict[str, Any]]:
    """Sub-agent 1: SKU dengan order terbanyak 24 jam / 7 hari terakhir (efek FOMO)."""
    return await fetch_all(SALES_VELOCITY_SQL)


async def get_deadstock() -> list[dict[str, Any]]:
    """Sub-agent 2: SKU menumpuk (stok tinggi, listed >30 hari, order 7 hari rendah)."""
    return await fetch_all(
        DEADSTOCK_SQL,
        (DEADSTOCK_MIN_STOCK, DEADSTOCK_MIN_AGE_DAYS, DEADSTOCK_MAX_ORDERS_7D),
    )


async def get_social_proof(sku_id: int) -> list[dict[str, Any]]:
    """Sub-agent 3: 3 review bintang 5 terbaru untuk SKU target."""
    return await fetch_all(SOCIAL_PROOF_SQL, (sku_id,))


async def get_rating(sku_id: int) -> dict[str, Any]:
    row = await fetch_one(RATING_SQL, (sku_id,))
    return row if row else {"total_reviews": 0, "avg_rating": None}


def _to_number(value: Any) -> int | float:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return value
    return int(value)


async def build_context() -> dict[str, Any]:
    """Susun context JSON lengkap: velocity + deadstock + social proof + SKU primary."""
    velocity, deadstock = await _run_queries()
    primary, reviews, rating = await _select_primary(deadstock, velocity)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "sales_velocity": velocity,
        "deadstock": deadstock,
        "primary": primary,
        "reviews": reviews,
        "rating": rating,
    }


async def _run_queries() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import asyncio

    velocity_task = asyncio.create_task(get_sales_velocity())
    deadstock_task = asyncio.create_task(get_deadstock())
    velocity, deadstock = await asyncio.gather(velocity_task, deadstock_task)
    return velocity, deadstock


async def _select_primary(
    deadstock: list[dict[str, Any]], velocity: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Prioritas: deadstock sebagai target promo (sesuai contoh blueprint),
    fallback ke SKU terlaris bila tidak ada deadstock."""
    if deadstock:
        primary = deadstock[0]
    elif velocity:
        primary = velocity[0]
    else:
        raise RuntimeError(
            "Tidak ada SKU target: tabel inventory kosong. Jalankan dulu 'uv run python -m app.cli seed'."
        )

    reviews = await get_social_proof(_to_number(primary["sku_id"]))
    rating = await get_rating(_to_number(primary["sku_id"]))
    return primary, reviews, rating
