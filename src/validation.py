"""Validation interactive des anomalies, puis écriture de data/processed/.

La console affiche les anomalies une par une (mêmes contrôles que
cleaning.py) avec la ligne complète du CSV, et propose pour chacune :
- modifier la valeur qui pose problème ;
- supprimer la ligne ;
- garder la ligne telle quelle (seulement si l'anomalie n'empêche pas le
  chargement en base, ex. montant négatif = remboursement) ;
- quitter.

Les contrôles sont relancés après chaque décision : une anomalie réglée
indirectement (ex. doublon dont l'autre ligne a été supprimée) disparaît,
et une nouvelle anomalie créée par une modification est proposée à son tour.

Les fichiers de data/raw/ ne sont jamais modifiés. À la fin, après
confirmation, les données corrigées sont écrites dans data/processed/ et
chaque décision est ajoutée au journal anomalies/corrections.csv. Ce journal
est réappliqué à chaque lancement (console ou main.py) : une correction
n'est faite qu'une fois.

Usage : python src/validation.py   (main.py utilise auto_validate())
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

import cleaning

ROOT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
CORRECTIONS_FILE = ROOT_DIR / "anomalies" / "corrections.csv"

# Fichier brut -> fichier nettoyé, dans l'ordre des contrôles.
PROCESSED_FILES = {
    "customers.csv": "customers_clean.csv",
    "subscriptions.csv": "subscriptions_clean.csv",
    "payments.csv": "payments_clean.csv",
}

CORRECTION_COLUMNS = [
    "date",
    "file_name",
    "row_number",
    "column_name",
    "error_message",
    "action",
    "old_value",
    "new_value",
]

# Anomalies qu'on peut accepter telles quelles : elles n'empêchent pas le
# chargement en base. Les autres (valeur manquante, doublon, date ou nombre
# illisible, référence inconnue) feraient échouer database.py.
KEEPABLE_PREFIXES = (
    "Montant négatif",
    "Prix négatif",
    "Email invalide",
    "Date de fin antérieure",
)

SEPARATOR = "-" * 64


# ---------------------------------------------------------------------------
# Données et contrôles
# ---------------------------------------------------------------------------

def load_frames():
    """Charge les trois CSV bruts. L'index pandas d'origine est conservé
    jusqu'au bout : il donne toujours le bon numéro de ligne du CSV, même
    après des suppressions."""
    return {name: cleaning.load_csv(name) for name in PROCESSED_FILES}


def run_checks(frames):
    """Relance les contrôles de cleaning.py sur l'état actuel des données."""
    customers = frames["customers.csv"]
    subscriptions = frames["subscriptions.csv"]
    payments = frames["payments.csv"]
    return (
        cleaning.check_customers(customers)
        + cleaning.check_subscriptions(subscriptions, customers)
        + cleaning.check_payments(payments, subscriptions)
    )


def anomaly_key(anomaly):
    return (
        anomaly["file_name"],
        anomaly["row_number"],
        anomaly["column_name"],
        anomaly["error_message"],
    )


def row_index(anomaly):
    """Numéro de ligne du CSV -> index pandas (en-tête = ligne 1)."""
    return anomaly["row_number"] - 2


def can_keep(anomaly):
    return anomaly["error_message"].startswith(KEEPABLE_PREFIXES)
