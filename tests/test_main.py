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
