"""Data sub-agents: 3 SQL functions (not LLM agents) that produce a context dict
injected into the copywriter and reviewer prompts (lightweight context injection)."""

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
    """Sub-agent 1: SKUs with the most orders in the last 24h / 7 days (FOMO effect)."""
    return await fetch_all(SALES_VELOCITY_SQL)


async def get_deadstock() -> list[dict[str, Any]]:
    """Sub-agent 2: SKUs piling up (high stock, listed > 30 days ago, low 7-day orders)."""
    return await fetch_all(
        DEADSTOCK_SQL,
        (DEADSTOCK_MIN_STOCK, DEADSTOCK_MIN_AGE_DAYS, DEADSTOCK_MAX_ORDERS_7D),
    )


async def get_social_proof(sku_id: int) -> list[dict[str, Any]]:
    """Sub-agent 3: 3 most recent 5-star reviews for the target SKU."""
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
    """Assemble the full context JSON: velocity + deadstock + social proof + primary SKU."""
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
    """Deadstock is the promo target by default (as in the blueprint example);
    fall back to the top seller when there is no deadstock."""
    if deadstock:
        primary = deadstock[0]
    elif velocity:
        primary = velocity[0]
    else:
        raise RuntimeError(
            "No target SKU: the inventory table is empty. "
            "Run 'uv run python -m app.cli seed' first."
        )

    reviews = await get_social_proof(_to_number(primary["sku_id"]))
    rating = await get_rating(_to_number(primary["sku_id"]))
    return primary, reviews, rating
