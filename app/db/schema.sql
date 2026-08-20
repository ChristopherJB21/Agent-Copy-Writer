-- Idempotent schema for the AI Marketing Copilot MVP (3 tables; brand profile lives in a config file)
-- Note: the inventory.discount_pct column was added so promo figures (e.g. a "30% discount") are
-- stored and reviewable based on data rather than invented by the LLM.

CREATE TABLE IF NOT EXISTS inventory (
    sku_id        SERIAL PRIMARY KEY,
    sku_code      TEXT NOT NULL UNIQUE,
    product_name  TEXT NOT NULL,
    category      TEXT NOT NULL,
    unit_price    NUMERIC(12, 2) NOT NULL,
    discount_pct  NUMERIC(5, 2) NOT NULL DEFAULT 0,
    stock_qty     INTEGER NOT NULL DEFAULT 0,
    reorder_point INTEGER NOT NULL DEFAULT 10,
    listed_at     TIMESTAMPTZ NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS orders (
    order_id     SERIAL PRIMARY KEY,
    order_code   TEXT NOT NULL UNIQUE,
    sku_id       INTEGER NOT NULL REFERENCES inventory (sku_id) ON DELETE CASCADE,
    qty          INTEGER NOT NULL CHECK (qty > 0),
    total_amount NUMERIC(14, 2) NOT NULL,
    status       TEXT NOT NULL DEFAULT 'completed',
    created_at   TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders (created_at);
CREATE INDEX IF NOT EXISTS idx_orders_sku_id ON orders (sku_id);

CREATE TABLE IF NOT EXISTS reviews (
    review_id     SERIAL PRIMARY KEY,
    sku_id        INTEGER NOT NULL REFERENCES inventory (sku_id) ON DELETE CASCADE,
    customer_name TEXT NOT NULL,
    rating        INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text   TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reviews_sku_id ON reviews (sku_id);
CREATE INDEX IF NOT EXISTS idx_reviews_created_at ON reviews (created_at);