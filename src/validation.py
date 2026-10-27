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


# ---------------------------------------------------------------------------
# Affichage et saisie
# ---------------------------------------------------------------------------

def describe(anomaly, frames, remaining):
    """Texte affiché pour une anomalie : où, quoi, et la ligne complète."""
    df = frames[anomaly["file_name"]]
    index = row_index(anomaly)
    lines = [
        SEPARATOR,
        f"Anomalie ({remaining} restante(s))",
        f"  Fichier : {anomaly['file_name']}   "
        f"Ligne : {anomaly['row_number']}   "
        f"Colonne : {anomaly['column_name']}",
        f"  Problème : {anomaly['error_message']}",
        "  Ligne complète :",
    ]
    width = max(len(column) for column in df.columns)
    for column in df.columns:
        value = df.at[index, column]
        marker = ">" if column == anomaly["column_name"] else " "
        lines.append(f"  {marker} {column:<{width}}  {value if value != '' else '(vide)'}")
    return "\n".join(lines)


def ask_choice(ask, question, choices):
    """Repose la question tant que la réponse n'est pas une des `choices`."""
    menu = "  ".join(f"[{letter}] {label}" for letter, label in choices.items())
    while True:
        answer = ask(f"{menu}\n{question} ").strip().lower()
        if answer in choices:
            return answer


def ask_yes_no(ask, question):
    return ask_choice(ask, question, {"o": "Oui", "n": "Non"}) == "o"


def ask_new_value(ask, column, old_value):
    """Demande la nouvelle valeur ; None si l'utilisateur annule."""
    value = ask(
        f"Nouvelle valeur pour {column} "
        f"(actuelle : {old_value or '(vide)'}, Entrée = annuler) : "
    ).strip()
    if value:
        return value
    if ask_yes_no(ask, "Vider la cellule ? (sinon : annuler)"):
        return ""
    return None
