"""Stockage des données nettoyées (data/processed/) dans la base SQLite
data/salesflow.db.

La base relie les trois fichiers par des clés étrangères :
customers <- subscriptions (customer_id) <- payments (subscription_id),
ce qui permet de retrouver en SQL les abonnements et paiements d'un client.

Le script peut être relancé autant de fois que voulu : les tables ne sont
créées qu'une fois et chaque ligne est insérée ou mise à jour selon sa clé
primaire (pas de doublons).
"""

import sqlite3
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
DB_FILE = ROOT_DIR / "data" / "salesflow.db"

# Tables dans l'ordre d'insertion : une table « parent » doit être remplie
# avant les tables qui la référencent, sinon les clés étrangères échouent.
TABLES = {
    "customers": ("customers_clean.csv", "customer_id"),
    "subscriptions": ("subscriptions_clean.csv", "subscription_id"),
    "payments": ("payments_clean.csv", "payment_id"),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id     TEXT PRIMARY KEY,
    company_name    TEXT NOT NULL,
    email           TEXT NOT NULL,
    signup_date     TEXT NOT NULL,      -- AAAA-MM-JJ
    country         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id      TEXT PRIMARY KEY,
    customer_id          TEXT NOT NULL,
    plan                 TEXT NOT NULL,
    monthly_price        REAL NOT NULL,
    start_date           TEXT NOT NULL,  -- AAAA-MM-JJ
    end_date             TEXT,           -- NULL = abonnement en cours
    status               TEXT NOT NULL,
    calculation_eligible INTEGER NOT NULL,  -- 1 = vrai, 0 = faux
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id           TEXT PRIMARY KEY,
    subscription_id      TEXT NOT NULL,
    payment_date         TEXT NOT NULL,  -- AAAA-MM-JJ
    amount               REAL NOT NULL,
    status               TEXT NOT NULL,
    payment_method       TEXT NOT NULL,
    calculation_eligible INTEGER NOT NULL,
    revenue_eligible     INTEGER NOT NULL,
    FOREIGN KEY (subscription_id) REFERENCES subscriptions (subscription_id)
);

-- Index sur les clés étrangères : accélèrent les jointures.
CREATE INDEX IF NOT EXISTS idx_subscriptions_customer_id
    ON subscriptions (customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_subscription_id
    ON payments (subscription_id);
"""
