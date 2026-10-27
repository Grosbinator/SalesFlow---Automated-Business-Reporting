"""Tests de src/report.py.

Le classeur est construit à partir d'une base SQLite en mémoire (même jeu
de données que tests/test_analytics.py) et d'anomalies fabriquées en
mémoire : data/, anomalies/ et reports/ ne sont jamais touchés.

Lancer les tests depuis la racine du projet :  python -m pytest -v
"""

import sys
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import analytics  # noqa: E402
import report  # noqa: E402
from test_analytics import (  # noqa: E402
    CUSTOMERS,
    PAYMENTS,
    SUBSCRIPTIONS,
    load,
    new_connection,
)

ANOMALIES = pd.DataFrame(
    [
        ("payments.csv", 18, "amount", "Valeur manquante"),
        ("payments.csv", 20, "payment_id", "Identifiant dupliqué : P019"),
        ("payments.csv", 21, "payment_id", "Identifiant dupliqué : P019"),
        ("subscriptions.csv", 17, "customer_id",
         "customer_id inexistant dans customers.csv : C999"),
    ],
    columns=report.ANOMALY_COLUMNS,
)


@pytest.fixture
def connection():
    connection = new_connection()
    load(connection, CUSTOMERS, SUBSCRIPTIONS, PAYMENTS)
    yield connection
    connection.close()


def column_values(sheet, column, first_row, last_row):
    return [sheet.cell(row, column).value for row in range(first_row, last_row + 1)]


def find_table(sheet, title):
    """Renvoie les lignes (valeurs) du tableau placé sous le titre `title`."""
    for row in sheet.iter_rows():
        if row[0].value == title:
            start = row[0].row + 2  # titre, puis en-tête
            break
    else:
        raise AssertionError(f"Tableau introuvable : {title}")
    rows = []
    for values in sheet.iter_rows(min_row=start, values_only=True):
        if values[0] is None:
            break
        rows.append(tuple(v for v in values if v is not None))
    return rows


# ---------------------------------------------------------------------------
# 1. Structure du classeur
# ---------------------------------------------------------------------------

def test_report_has_the_five_sheets(connection):
    workbook = report.build_report(connection, ANOMALIES)
    assert workbook.sheetnames == [
        "Dashboard", "Revenue", "Customers", "Subscriptions", "Data Quality",
    ]


def test_main_writes_the_excel_file(connection, tmp_path, monkeypatch):
    """main() enregistre le classeur (dossier reports/ créé si besoin)."""
    output = tmp_path / "reports" / "monthly_report.xlsx"
    monkeypatch.setattr(report, "REPORT_FILE", output)
    monkeypatch.setattr(report, "ANOMALIES_FILE", tmp_path / "absent.csv")
    monkeypatch.setattr(analytics, "get_connection", lambda: connection)

    report.main()

    assert load_workbook(output).sheetnames[0] == "Dashboard"
