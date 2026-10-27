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


def average_basket(connection):
    """Panier moyen : montant moyen des paiements réussis (None si aucun)."""
    return scalar(
        connection,
        "SELECT AVG(amount) FROM payments WHERE status = ?",
        (SUCCESS,),
    )


def failure_rate(connection):
    """Taux d'échec : paiements échoués / total des paiements (None si aucun)."""
    return scalar(
        connection,
        "SELECT CAST(SUM(status = ?) AS REAL) / NULLIF(COUNT(*), 0) "
        "FROM payments",
        (FAILED,),
    )


def current_mrr(connection):
    """Revenu récurrent théorique actuel : prix mensuels des abonnements actifs."""
    return scalar(
        connection,
        "SELECT COALESCE(SUM(monthly_price), 0) FROM subscriptions "
        "WHERE status = ?",
        (ACTIVE,),
    )


# ---------------------------------------------------------------------------
# Indicateurs par mois et par formule (tableaux)
# ---------------------------------------------------------------------------

def monthly_revenue(connection):
    """Revenu encaissé par mois, selon la date du paiement."""
    return pd.read_sql_query(
        """
        SELECT substr(payment_date, 1, 7) AS month,
               SUM(amount)                AS collected_revenue,
               COUNT(*)                   AS successful_payments
        FROM payments
        WHERE status = ?
        GROUP BY month
        ORDER BY month
        """,
        connection,
        params=(SUCCESS,),
    )


def monthly_recurring_revenue(connection):
    """Revenu récurrent théorique par mois.

    Un abonnement compte pour un mois s'il a commencé avant la fin du mois
    et n'est pas terminé avant son début (end_date NULL = en cours). Les mois
    vont du premier début d'abonnement à la dernière date connue.
    """
    return pd.read_sql_query(
        """
        WITH RECURSIVE months (month_start) AS (
            SELECT date(MIN(start_date), 'start of month')
            FROM subscriptions
            HAVING MIN(start_date) IS NOT NULL
            UNION ALL
            SELECT date(month_start, '+1 month')
            FROM months
            WHERE month_start < (
                SELECT date(MAX(day), 'start of month')
                FROM (
                    SELECT payment_date AS day FROM payments
                    UNION ALL
                    SELECT start_date FROM subscriptions
                )
            )
        )
        SELECT strftime('%Y-%m', m.month_start)        AS month,
               COALESCE(SUM(s.monthly_price), 0)        AS recurring_revenue,
               COUNT(s.subscription_id)                 AS running_subscriptions
        FROM months m
        LEFT JOIN subscriptions s
               ON s.start_date <= date(m.month_start, '+1 month', '-1 day')
              AND (s.end_date IS NULL OR s.end_date >= m.month_start)
        GROUP BY m.month_start
        ORDER BY m.month_start
        """,
        connection,
    )


def revenue_comparison(connection):
    """Compare, mois par mois, le revenu encaissé au revenu récurrent théorique."""
    recurring = monthly_recurring_revenue(connection)
    collected = monthly_revenue(connection)

    comparison = recurring.merge(collected, on="month", how="outer")
    comparison = comparison.fillna(0).sort_values("month", ignore_index=True)
    for column in ("running_subscriptions", "successful_payments"):
        comparison[column] = comparison[column].astype(int)

    # Écart négatif : on a encaissé moins que ce que les abonnements prévoient.
    comparison["gap"] = (
        comparison["collected_revenue"] - comparison["recurring_revenue"]
    )
    return comparison[[
        "month",
        "recurring_revenue",
        "collected_revenue",
        "gap",
        "running_subscriptions",
        "successful_payments",
    ]]
