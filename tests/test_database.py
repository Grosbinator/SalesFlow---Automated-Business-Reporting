"""Tests de src/database.py.

Chaque test travaille sur une base et des CSV créés dans un dossier
temporaire : data/salesflow.db et data/processed/ ne sont jamais touchés.

Lancer les tests depuis la racine du projet :  python -m pytest -v
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import database  # noqa: E402


# ---------------------------------------------------------------------------
# Jeux de données de référence : une ligne valide par fichier nettoyé.
# ---------------------------------------------------------------------------

VALID_CUSTOMER = {
    "customer_id": "C001",
    "company_name": "NovaTech",
    "email": "contact@novatech.example",
    "signup_date": "2026-01-12",
    "country": "France",
}

VALID_SUBSCRIPTION = {
    "subscription_id": "S001",
    "customer_id": "C001",
    "plan": "Starter",
    "monthly_price": "29.0",
    "start_date": "2026-01-12",
    "end_date": "",
    "status": "active",
    "calculation_eligible": "True",
}

VALID_PAYMENT = {
    "payment_id": "P001",
    "subscription_id": "S001",
    "payment_date": "2026-01-12",
    "amount": "29.0",
    "status": "success",
    "payment_method": "card",
    "calculation_eligible": "True",
    "revenue_eligible": "True",
}


def make_df(base, *overrides):
    """Une ligne par dictionnaire `overrides`, complétée avec `base`."""
    overrides = overrides or ({},)
    return pd.DataFrame([{**base, **row} for row in overrides], dtype=str)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Redirige la base et le dossier processed vers un dossier temporaire,
    et y écrit trois CSV valides. Renvoie une fonction pour réécrire un CSV."""
    processed = tmp_path / "processed"
    processed.mkdir()
    monkeypatch.setattr(database, "PROCESSED_DIR", processed)
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "salesflow.db")

    def write(filename, df):
        df.to_csv(processed / filename, index=False)

    write("customers_clean.csv", make_df(VALID_CUSTOMER))
    write("subscriptions_clean.csv", make_df(VALID_SUBSCRIPTION))
    write("payments_clean.csv", make_df(VALID_PAYMENT))
    return write


def query(sql):
    connection = database.get_connection()
    try:
        return connection.execute(sql).fetchall()
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# 1. Création de la base
# ---------------------------------------------------------------------------

def test_main_creates_the_three_tables(env):
    database.main()
    tables = {row[0] for row in query(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    )}
    assert {"customers", "subscriptions", "payments"} <= tables


def test_foreign_keys_are_declared(env):
    database.main()
    subscription_fk = query("PRAGMA foreign_key_list(subscriptions)")
    payment_fk = query("PRAGMA foreign_key_list(payments)")
    # (table référencée, colonne locale, colonne référencée)
    assert [(r[2], r[3], r[4]) for r in subscription_fk] == [
        ("customers", "customer_id", "customer_id")
    ]
    assert [(r[2], r[3], r[4]) for r in payment_fk] == [
        ("subscriptions", "subscription_id", "subscription_id")
    ]


# ---------------------------------------------------------------------------
# 2. Insertion et conversion des valeurs
# ---------------------------------------------------------------------------

def test_values_are_converted_for_sqlite(env):
    """end_date vide -> NULL, booléens -> 1/0, prix -> nombre."""
    database.main()
    assert query(
        "SELECT monthly_price, end_date, calculation_eligible FROM subscriptions"
    ) == [(29.0, None, 1)]


def test_customer_can_be_joined_to_payments(env):
    """But de la base : retrouver les paiements d'un client en SQL."""
    database.main()
    rows = query("""
        SELECT c.company_name, s.plan, p.amount
        FROM customers c
        JOIN subscriptions s ON s.customer_id = c.customer_id
        JOIN payments p ON p.subscription_id = s.subscription_id
    """)
    assert rows == [("NovaTech", "Starter", 29.0)]


# ---------------------------------------------------------------------------
# 3. Relancer le script ne crée pas de doublons
# ---------------------------------------------------------------------------

def test_running_twice_creates_no_duplicates(env):
    database.main()
    database.main()
    for table in database.TABLES:
        assert query(f"SELECT COUNT(*) FROM {table}") == [(1,)]


def test_running_again_updates_existing_rows(env):
    """Une ligne modifiée dans le CSV est mise à jour, pas ajoutée."""
    database.main()
    env("customers_clean.csv", make_df(VALID_CUSTOMER, {"country": "Belgium"}))
    database.main()
    assert query("SELECT customer_id, country FROM customers") == [
        ("C001", "Belgium")
    ]
