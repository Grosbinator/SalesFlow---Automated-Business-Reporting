"""Tests de src/validation.py.

La console est pilotée par une liste de réponses simulées (`answers`) à la
place du clavier, et les données sont de petits DataFrames en mémoire :
data/ et anomalies/ ne sont jamais touchés.

Lancer les tests depuis la racine du projet :  python -m pytest -v
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import validation  # noqa: E402


# ---------------------------------------------------------------------------
# Jeux de données : des CSV bruts valides, chaque test y ajoute ses erreurs.
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
}

VALID_PAYMENT = {
    "payment_id": "P001",
    "subscription_id": "S001",
    "payment_date": "2026-01-12",
    "amount": "29.0",
    "status": "success",
    "payment_method": "card",
}


def make_df(base, *overrides):
    overrides = overrides or ({},)
    return pd.DataFrame([{**base, **row} for row in overrides], dtype=str)


def make_frames(customers=None, subscriptions=None, payments=None):
    return {
        "customers.csv": customers if customers is not None else make_df(VALID_CUSTOMER),
        "subscriptions.csv": (
            subscriptions if subscriptions is not None else make_df(VALID_SUBSCRIPTION)
        ),
        "payments.csv": payments if payments is not None else make_df(VALID_PAYMENT),
    }


def answers(*replies):
    """Simule le clavier : renvoie les réponses dans l'ordre."""
    replies = iter(replies)
    return lambda prompt: next(replies)


class Console:
    """Récupère ce que la console affiche."""

    def __init__(self):
        self.lines = []

    def __call__(self, text=""):
        self.lines.append(text)

    @property
    def text(self):
        return "\n".join(self.lines)


# ---------------------------------------------------------------------------
# 1. Affichage
# ---------------------------------------------------------------------------

def test_describe_shows_file_line_column_and_full_row():
    frames = make_frames(payments=make_df(VALID_PAYMENT, {"amount": ""}))
    anomaly = validation.run_checks(frames)[0]
    text = validation.describe(anomaly, frames, remaining=1)
    assert "payments.csv" in text
    assert "Ligne : 2" in text
    assert "Valeur manquante" in text
    assert "> amount" in text and "(vide)" in text
    assert "payment_method" in text  # la ligne complète est affichée


def test_ask_choice_repeats_until_answer_is_valid():
    ask = answers("x", "", "S")
    assert validation.ask_choice(ask, "?", {"s": "Supprimer"}) == "s"
