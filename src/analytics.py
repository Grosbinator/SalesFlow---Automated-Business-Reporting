"""Calcul des indicateurs commerciaux à partir de data/salesflow.db.

Les agrégations sont faites en SQL ; pandas sert à mettre les résultats en
forme (tableaux, fusion, pourcentages).

Deux notions de revenu sont distinguées :
- revenu encaissé : somme des paiements réussis, rattachés au mois de leur
  date de paiement (payment_date), pas à la date de début de l'abonnement ;
- revenu récurrent théorique (MRR) : somme des prix mensuels des abonnements
  en cours, c'est-à-dire ce qui devrait être encaissé chaque mois.
L'écart entre les deux révèle les paiements échoués ou manquants.

Usage : python src/analytics.py   (après python src/database.py)
"""

import sqlite3

import pandas as pd

import database

SUCCESS = "success"
FAILED = "failed"
ACTIVE = "active"


def get_connection():
    """Ouvre la base existante (sans la créer, contrairement à database.py)."""
    if not database.DB_FILE.exists():
        raise FileNotFoundError(
            f"Base introuvable : {database.DB_FILE}. "
            "Lancer d'abord : python src/database.py"
        )
    return sqlite3.connect(database.DB_FILE)


def scalar(connection, query, params=()):
    """Exécute une requête qui renvoie une seule valeur."""
    return connection.execute(query, params).fetchone()[0]


# ---------------------------------------------------------------------------
# Indicateurs simples (une valeur)
# ---------------------------------------------------------------------------

def collected_revenue(connection):
    """Chiffre d'affaires encaissé : somme des paiements réussis."""
    return scalar(
        connection,
        "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = ?",
        (SUCCESS,),
    )


def active_customers(connection):
    """Nombre de clients distincts ayant au moins un abonnement actif."""
    return scalar(
        connection,
        "SELECT COUNT(DISTINCT customer_id) FROM subscriptions WHERE status = ?",
        (ACTIVE,),
    )
