"""Tests de src/cleaning.py.

Principe : on fabrique de petits jeux de données en mémoire (ou dans un
dossier temporaire) dont on connaît à l'avance les erreurs, puis on vérifie
que cleaning.py les détecte, avec le bon fichier, la bonne ligne et la
bonne colonne. Les vrais fichiers de data/ ne sont jamais touchés.

Lancer les tests depuis la racine du projet :  python -m pytest -v
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cleaning  # noqa: E402


# ---------------------------------------------------------------------------
# Jeux de données de référence : une ligne 100 % valide par fichier.
# Chaque test copie cette ligne et y casse UNE seule valeur.
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
    """Construit un DataFrame de texte : une ligne par dictionnaire `overrides`,
    complétée avec les valeurs valides de `base`. Sans argument : une ligne valide."""
    overrides = overrides or ({},)
    return pd.DataFrame([{**base, **row} for row in overrides], dtype=str)


def found(anomalies):
    """Réduit les anomalies à (fichier, ligne, colonne) pour comparer simplement."""
    return {
        (a["file_name"], a["row_number"], a["column_name"])
        for a in anomalies
    }


# ---------------------------------------------------------------------------
# 1. Numéro de ligne : la base de tout le fichier d'anomalies
# ---------------------------------------------------------------------------

def test_row_number_matches_line_in_csv_file():
    """Le 1er enregistrement doit être signalé « ligne 2 » (la ligne 1 est
    l'en-tête), pour retrouver l'erreur directement dans le CSV."""
    anomalies = []
    cleaning.add_anomaly(anomalies, "payments.csv", 0, "amount", "x")
    cleaning.add_anomaly(anomalies, "payments.csv", 3, "amount", "x")
    assert [a["row_number"] for a in anomalies] == [2, 5]
