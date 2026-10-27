"""Tests de src/analytics.py.

Chaque test travaille sur une base SQLite en mémoire, remplie avec un petit
jeu de données dont on connaît à l'avance tous les indicateurs.

Lancer les tests depuis la racine du projet :  python -m pytest -v
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import analytics  # noqa: E402
import database  # noqa: E402


# ---------------------------------------------------------------------------
# Jeu de données de référence
#
#   C1 : S1 Starter 29 € (actif, depuis janvier) + S3 Pro 79 € (actif, mars)
#   C2 : S2 Pro 79 € (février -> 31 mars, résilié)
#   C3 : aucun abonnement
#
#   P1  S1  2026-01-10   29 success
#   P2  S1  2026-02-10   29 success   <- abonnement de janvier, payé en février
#   P3  S2  2026-02-15   79 success
#   P4  S2  2026-03-15   79 failed
#   P5  S3  2026-03-01   79 success
# ---------------------------------------------------------------------------

CUSTOMERS = [
    ("C1", "NovaTech"),
    ("C2", "Greenlytic"),
    ("C3", "BrightDesk"),
]

SUBSCRIPTIONS = [
    ("S1", "C1", "Starter", "29.0", "2026-01-10", "", "active"),
    ("S2", "C2", "Pro", "79.0", "2026-02-15", "2026-03-31", "cancelled"),
    ("S3", "C1", "Pro", "79.0", "2026-03-01", "", "active"),
]

PAYMENTS = [
    ("P1", "S1", "2026-01-10", "29.0", "success"),
    ("P2", "S1", "2026-02-10", "29.0", "success"),
    ("P3", "S2", "2026-02-15", "79.0", "success"),
    ("P4", "S2", "2026-03-15", "79.0", "failed"),
    ("P5", "S3", "2026-03-01", "79.0", "success"),
]


def new_connection():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    database.create_tables(connection)
    return connection


def load(connection, customers=(), subscriptions=(), payments=()):
    """Insère les lignes via database.upsert (mêmes conversions qu'en vrai)."""
    tables = [
        ("customers", "customer_id", customers, lambda c: {
            "customer_id": c[0], "company_name": c[1],
            "email": "contact@example.com", "signup_date": "2026-01-01",
            "country": "France",
        }),
        ("subscriptions", "subscription_id", subscriptions, lambda s: {
            "subscription_id": s[0], "customer_id": s[1], "plan": s[2],
            "monthly_price": s[3], "start_date": s[4], "end_date": s[5],
            "status": s[6], "calculation_eligible": "True",
        }),
        ("payments", "payment_id", payments, lambda p: {
            "payment_id": p[0], "subscription_id": p[1], "payment_date": p[2],
            "amount": p[3], "status": p[4], "payment_method": "card",
            "calculation_eligible": "True",
            "revenue_eligible": str(p[4] == "success"),
        }),
    ]
    for table, key, rows, to_dict in tables:
        if rows:
            df = pd.DataFrame([to_dict(row) for row in rows], dtype=str)
            database.upsert(connection, table, df, key)


@pytest.fixture
def connection():
    connection = new_connection()
    load(connection, CUSTOMERS, SUBSCRIPTIONS, PAYMENTS)
    yield connection
    connection.close()


@pytest.fixture
def empty_connection():
    connection = new_connection()
    yield connection
    connection.close()


# ---------------------------------------------------------------------------
# 1. Indicateurs simples
# ---------------------------------------------------------------------------

def test_collected_revenue_sums_successful_payments_only(connection):
    assert analytics.collected_revenue(connection) == 29 + 29 + 79 + 79


def test_active_customers_counts_each_customer_once(connection):
    """C1 a deux abonnements actifs mais ne compte qu'une fois ; C2 a résilié."""
    assert analytics.active_customers(connection) == 1


def test_average_basket_uses_successful_payments(connection):
    assert analytics.average_basket(connection) == pytest.approx(216 / 4)


def test_failure_rate_is_failed_over_all_payments(connection):
    assert analytics.failure_rate(connection) == pytest.approx(1 / 5)


def test_current_mrr_sums_active_subscriptions(connection):
    assert analytics.current_mrr(connection) == 29 + 79


# ---------------------------------------------------------------------------
# 2. Revenu encaissé vs revenu récurrent théorique
# ---------------------------------------------------------------------------

def test_monthly_revenue_uses_payment_date(connection):
    """P2 (abonnement de janvier) est encaissé en février : il compte en février."""
    monthly = analytics.monthly_revenue(connection)
    assert list(monthly["month"]) == ["2026-01", "2026-02", "2026-03"]
    assert list(monthly["collected_revenue"]) == [29, 29 + 79, 79]


def test_monthly_recurring_revenue_follows_subscription_periods(connection):
    """Mars : S1 + S3 + S2 (résilié le 31 mars, donc encore dû en mars)."""
    recurring = analytics.monthly_recurring_revenue(connection)
    assert list(recurring["month"]) == ["2026-01", "2026-02", "2026-03"]
    assert list(recurring["recurring_revenue"]) == [29, 29 + 79, 29 + 79 + 79]
    assert list(recurring["running_subscriptions"]) == [1, 2, 3]


def test_revenue_comparison_shows_gap(connection):
    comparison = analytics.revenue_comparison(connection)
    assert list(comparison["gap"]) == [0, 0, 79 - 187]


def test_revenue_comparison_keeps_months_without_payment(connection):
    """Un mois sans aucun paiement doit apparaître avec 0 encaissé."""
    load(connection, subscriptions=[
        ("S4", "C3", "Starter", "29.0", "2026-05-01", "", "active"),
    ])
    comparison = analytics.revenue_comparison(connection)
    april = comparison[comparison["month"] == "2026-04"].iloc[0]
    assert april["collected_revenue"] == 0
    assert april["recurring_revenue"] == 29 + 79


# ---------------------------------------------------------------------------
# 3. Répartition par formule et synthèse
# ---------------------------------------------------------------------------

def test_subscriptions_by_plan(connection):
    plans = analytics.subscriptions_by_plan(connection)
    assert plans.to_dict("list") == {
        "plan": ["Pro", "Starter"],
        "subscriptions": [2, 1],
        "active_subscriptions": [1, 1],
        "share_pct": [66.7, 33.3],
    }


def test_summary_lists_the_key_indicators(connection):
    values = dict(analytics.summary(connection).values)
    assert values["Chiffre d'affaires encaissé (€)"] == 216
    assert values["Clients actifs"] == 1
    assert values["Taux d'échec des paiements (%)"] == 20.0
