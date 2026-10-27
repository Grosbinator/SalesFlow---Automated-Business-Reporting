"""Contrôle qualité des CSV bruts et génération de anomalies/anomalies.csv.

Chaque anomalie est normalisée avec les colonnes :
file_name, row_number, column_name, error_message

`row_number` correspond au numéro de ligne dans le fichier CSV d'origine
(l'en-tête est la ligne 1, le premier enregistrement la ligne 2).
"""

import re
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
ANOMALIES_DIR = ROOT_DIR / "anomalies"
ANOMALIES_FILE = ANOMALIES_DIR / "anomalies.csv"

ANOMALY_COLUMNS = ["file_name", "row_number", "column_name", "error_message"]
DATE_FORMAT = "%Y-%m-%d"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

REQUIRED_COLUMNS = {
    "customers.csv": [
        "customer_id",
        "company_name",
        "email",
        "signup_date",
        "country",
    ],
    "subscriptions.csv": [
        "subscription_id",
        "customer_id",
        "plan",
        "monthly_price",
        "start_date",
        "end_date",
        "status",
    ],
    "payments.csv": [
        "payment_id",
        "subscription_id",
        "payment_date",
        "amount",
        "status",
        "payment_method",
    ],
}


def load_csv(filename):
    """Charge un CSV (tout en texte) et vérifie ses colonnes obligatoires."""
    path = RAW_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {path}"
        )

    # Tout est lu en texte pour contrôler les valeurs brutes :
    # une cellule vide devient "" et non NaN.
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = df.apply(lambda column: column.str.strip())

    missing_columns = (
        set(REQUIRED_COLUMNS[filename]) - set(df.columns)
    )

    if missing_columns:
        raise ValueError(
            f"{filename} : colonnes manquantes : "
            f"{sorted(missing_columns)}"
        )

    return df


# ---------------------------------------------------------------------------
# Outils de détection
# ---------------------------------------------------------------------------

def add_anomaly(anomalies, file_name, index, column_name, message):
    """Ajoute une anomalie. `index` est la position dans le DataFrame."""
    anomalies.append(
        {
            "file_name": file_name,
            "row_number": index + 2,  # +1 pour l'en-tête, +1 car base 1
            "column_name": column_name,
            "error_message": message,
        }
    )


def check_missing(anomalies, file_name, df, column):
    """Signale les cellules vides."""
    for index in df.index[df[column] == ""]:
        add_anomaly(
            anomalies, file_name, index, column, "Valeur manquante"
        )


def check_duplicates(anomalies, file_name, df, column):
    """Signale toutes les lignes partageant le même identifiant."""
    filled = df[df[column] != ""]
    duplicated = filled.index[filled[column].duplicated(keep=False)]
    for index in duplicated:
        add_anomaly(
            anomalies,
            file_name,
            index,
            column,
            f"Identifiant dupliqué : {df.at[index, column]}",
        )


def check_dates(anomalies, file_name, df, column):
    """Signale les dates non vides au format invalide ; renvoie les dates."""
    parsed = pd.to_datetime(
        df[column], format=DATE_FORMAT, errors="coerce"
    )
    for index in df.index[parsed.isna() & (df[column] != "")]:
        add_anomaly(
            anomalies,
            file_name,
            index,
            column,
            f"Date invalide (attendu AAAA-MM-JJ) : {df.at[index, column]}",
        )
    return parsed


def check_numbers(anomalies, file_name, df, column, label):
    """Signale les valeurs non numériques et négatives ; renvoie les nombres."""
    numbers = pd.to_numeric(df[column], errors="coerce")
    for index in df.index[numbers.isna() & (df[column] != "")]:
        add_anomaly(
            anomalies,
            file_name,
            index,
            column,
            f"{label} non numérique : {df.at[index, column]}",
        )
    for index in df.index[numbers < 0]:
        add_anomaly(
            anomalies,
            file_name,
            index,
            column,
            f"{label} négatif : {df.at[index, column]}",
        )
    return numbers


def check_references(
    anomalies, file_name, df, column, reference_values, reference_file
):
    """Vérifie que chaque valeur de `column` existe dans le fichier lié."""
    known = set(reference_values)
    unknown = df.index[(df[column] != "") & ~df[column].isin(known)]
    for index in unknown:
        add_anomaly(
            anomalies,
            file_name,
            index,
            column,
            f"{column} inexistant dans {reference_file} : "
            f"{df.at[index, column]}",
        )


# ---------------------------------------------------------------------------
# Contrôles par fichier
# ---------------------------------------------------------------------------

def check_customers(customers):
    file_name = "customers.csv"
    anomalies = []

    for column in REQUIRED_COLUMNS[file_name]:
        check_missing(anomalies, file_name, customers, column)
    check_duplicates(anomalies, file_name, customers, "customer_id")
    check_dates(anomalies, file_name, customers, "signup_date")

    invalid_emails = customers.index[
        (customers["email"] != "")
        & ~customers["email"].str.match(EMAIL_PATTERN)
    ]
    for index in invalid_emails:
        add_anomaly(
            anomalies,
            file_name,
            index,
            "email",
            f"Email invalide : {customers.at[index, 'email']}",
        )

    return anomalies


def check_subscriptions(subscriptions, customers):
    file_name = "subscriptions.csv"
    anomalies = []

    # end_date est volontairement facultative (abonnement en cours).
    for column in REQUIRED_COLUMNS[file_name]:
        if column != "end_date":
            check_missing(anomalies, file_name, subscriptions, column)
    check_duplicates(anomalies, file_name, subscriptions, "subscription_id")
    check_numbers(
        anomalies, file_name, subscriptions, "monthly_price", "Prix"
    )

    start_dates = check_dates(
        anomalies, file_name, subscriptions, "start_date"
    )
    end_dates = check_dates(anomalies, file_name, subscriptions, "end_date")
    for index in subscriptions.index[end_dates < start_dates]:
        add_anomaly(
            anomalies,
            file_name,
            index,
            "end_date",
            "Date de fin antérieure à la date de début",
        )

    # Relation : chaque customer_id doit exister dans customers.csv.
    check_references(
        anomalies,
        file_name,
        subscriptions,
        "customer_id",
        customers["customer_id"],
        "customers.csv",
    )

    return anomalies


def check_payments(payments, subscriptions):
    file_name = "payments.csv"
    anomalies = []

    for column in REQUIRED_COLUMNS[file_name]:
        check_missing(anomalies, file_name, payments, column)
    check_duplicates(anomalies, file_name, payments, "payment_id")
    check_dates(anomalies, file_name, payments, "payment_date")
    check_numbers(anomalies, file_name, payments, "amount", "Montant")

    # Relation : chaque subscription_id doit exister dans subscriptions.csv.
    check_references(
        anomalies,
        file_name,
        payments,
        "subscription_id",
        subscriptions["subscription_id"],
        "subscriptions.csv",
    )

    return anomalies


def save_anomalies(anomalies):
    """Écrit anomalies/anomalies.csv (en-tête seul s'il n'y a rien)."""
    ANOMALIES_DIR.mkdir(parents=True, exist_ok=True)
    report = pd.DataFrame(anomalies, columns=ANOMALY_COLUMNS)
    # utf-8-sig : les accents restent lisibles à l'ouverture dans Excel.
    report.to_csv(ANOMALIES_FILE, index=False, encoding="utf-8-sig")
    return report


def main():
    customers = load_csv("customers.csv")
    subscriptions = load_csv("subscriptions.csv")
    payments = load_csv("payments.csv")

    print("Les trois fichiers ont été chargés.")
    print("Customers :", customers.shape)
    print("Subscriptions :", subscriptions.shape)
    print("Payments :", payments.shape)

    anomalies = (
        check_customers(customers)
        + check_subscriptions(subscriptions, customers)
        + check_payments(payments, subscriptions)
    )
    report = save_anomalies(anomalies)

    print(f"{len(report)} anomalie(s) écrite(s) dans {ANOMALIES_FILE}")
    if not report.empty:
        print(report["file_name"].value_counts().to_string())


if __name__ == "__main__":
    main()
