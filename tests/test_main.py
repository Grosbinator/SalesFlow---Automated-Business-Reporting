"""Tests de main.py (pipeline complet).

Les tests de bout en bout redirigent tous les chemins (data/, anomalies/,
reports/) vers un dossier temporaire : les vrais fichiers ne sont jamais
touchés.

Lancer les tests depuis la racine du projet :  python -m pytest -v
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

import cleaning  # noqa: E402
import database  # noqa: E402
import main  # noqa: E402
import report  # noqa: E402
import validation  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Enchaînement des étapes
# ---------------------------------------------------------------------------

def test_steps_run_in_order():
    calls = []
    steps = [(name, lambda name=name: calls.append(name), None) for name in "ABC"]
    assert main.run_pipeline(steps, show=lambda text="": None) == 0
    assert calls == ["A", "B", "C"]


def test_failure_stops_the_pipeline_with_explicit_message():
    calls = []
    output = []

    def broken():
        raise FileNotFoundError("Fichier introuvable : customers.csv")

    steps = [
        ("Import", lambda: calls.append("import"), None),
        ("Chargement", broken, "Vérifier les données."),
        ("Rapport", lambda: calls.append("rapport"), None),
    ]
    assert main.run_pipeline(steps, show=output.append) == 1
    assert calls == ["import"]  # le rapport n'est jamais lancé
    text = "\n".join(output)
    assert "ÉCHEC à l'étape 2/3 (Chargement)" in text
    assert "FileNotFoundError : Fichier introuvable : customers.csv" in text
    assert "Piste : Vérifier les données." in text


def test_skip_import_removes_the_first_step():
    titles = [title for title, _, _ in main.build_steps(skip_import=True)]
    assert titles == [
        "Nettoyage et validation",
        "Chargement dans SQLite",
        "Calcul des indicateurs",
        "Génération du rapport Excel",
    ]
    assert len(main.build_steps()) == 5


# ---------------------------------------------------------------------------
# 2. Bout en bout sur de petits CSV (dossier temporaire)
# ---------------------------------------------------------------------------

CUSTOMERS = (
    "customer_id,company_name,email,signup_date,country\n"
    "C001,NovaTech,contact@novatech.example,2026-01-12,France\n"
    "C002,Greenlytic,hello@greenlytic.example,2026-02-19,France\n"
)
SUBSCRIPTIONS = (
    "subscription_id,customer_id,plan,monthly_price,start_date,end_date,status\n"
    "S001,C001,Starter,29.0,2026-01-12,,active\n"
    "S002,C002,Pro,79.0,2026-02-19,,active\n"
)
PAYMENTS = (
    "payment_id,subscription_id,payment_date,amount,status,payment_method\n"
    "P001,S001,2026-01-12,29.0,success,card\n"
    "P002,S002,2026-02-19,79.0,success,card\n"
    "P003,S999,2026-02-20,49.0,success,card\n"  # abonnement inconnu
)


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Projet complet dans un dossier temporaire, avec trois CSV bruts."""
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "customers.csv").write_text(CUSTOMERS, encoding="utf-8")
    (raw / "subscriptions.csv").write_text(SUBSCRIPTIONS, encoding="utf-8")
    (raw / "payments.csv").write_text(PAYMENTS, encoding="utf-8")

    anomalies = tmp_path / "anomalies"
    processed = tmp_path / "data" / "processed"
    monkeypatch.setattr(cleaning, "RAW_DIR", raw)
    monkeypatch.setattr(cleaning, "ANOMALIES_DIR", anomalies)
    monkeypatch.setattr(cleaning, "ANOMALIES_FILE", anomalies / "anomalies.csv")
    monkeypatch.setattr(report, "ANOMALIES_FILE", anomalies / "anomalies.csv")
    monkeypatch.setattr(validation, "PROCESSED_DIR", processed)
    monkeypatch.setattr(validation, "CORRECTIONS_FILE", anomalies / "corrections.csv")
    monkeypatch.setattr(database, "PROCESSED_DIR", processed)
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "data" / "salesflow.db")
    monkeypatch.setattr(report, "REPORT_FILE", tmp_path / "reports" / "monthly_report.xlsx")
    return tmp_path


def test_full_pipeline_produces_the_report(project):
    assert main.main(["--skip-import"]) == 0

    workbook = load_workbook(project / "reports" / "monthly_report.xlsx")
    assert workbook.sheetnames == [
        "Dashboard", "Revenue", "Customers", "Subscriptions", "Data Quality",
    ]
    # Le paiement lié à un abonnement inconnu a été écarté avant la base.
    connection = sqlite3.connect(project / "data" / "salesflow.db")
    payments = [row[0] for row in connection.execute("SELECT payment_id FROM payments")]
    connection.close()
    assert sorted(payments) == ["P001", "P002"]
    # Mais il reste signalé dans le rapport d'anomalies.
    anomalies = pd.read_csv(project / "anomalies" / "anomalies.csv", encoding="utf-8-sig")
    assert list(anomalies["column_name"]) == ["subscription_id"]


def test_critical_error_produces_no_report(project, capsys):
    (project / "data" / "raw" / "customers.csv").unlink()

    assert main.main(["--skip-import"]) == 1

    assert not (project / "reports" / "monthly_report.xlsx").exists()
    output = capsys.readouterr().out
    assert "ÉCHEC à l'étape 1/4 (Nettoyage et validation)" in output
    assert "FileNotFoundError" in output


def test_running_twice_gives_the_same_database(project):
    assert main.main(["--skip-import"]) == 0
    assert main.main(["--skip-import"]) == 0
    connection = sqlite3.connect(project / "data" / "salesflow.db")
    assert connection.execute("SELECT COUNT(*) FROM payments").fetchone() == (2,)
    connection.close()
