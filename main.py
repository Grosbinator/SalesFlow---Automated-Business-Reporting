"""Point d'entrée de SalesFlow : lance toute la chaîne de traitement.

    python main.py                  # chaîne complète, sans interaction
    python main.py --interactive    # traite les anomalies une par une
    python main.py --skip-import    # réutilise data/raw/ (pas de Téléchargements)

Étapes, dans l'ordre :
1. Import des fichiers sources (Téléchargements -> data/raw/)
2. Nettoyage (anomalies/anomalies.csv) et validation (data/processed/)
3. Chargement dans SQLite (data/salesflow.db)
4. Calcul des indicateurs
5. Génération du rapport Excel (reports/monthly_report.xlsx)

Si une étape échoue, les suivantes ne sont pas lancées : le programme
affiche l'étape, la cause de l'erreur et une piste de résolution, puis se
termine avec le code 1. Aucun rapport incomplet n'est produit.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import analytics  # noqa: E402
import cleaning  # noqa: E402
import database  # noqa: E402
import import_data  # noqa: E402
import report  # noqa: E402
import validation  # noqa: E402


class PipelineError(Exception):
    """Erreur bloquante détectée par le pipeline lui-même."""


# ---------------------------------------------------------------------------
# Étapes
# ---------------------------------------------------------------------------

def step_import():
    import_data.import_csv_files()


def step_clean_and_validate(interactive):
    cleaning.main()
    print()
    if interactive:
        if not validation.main():
            raise PipelineError(
                "validation non enregistrée : data/processed/ n'a pas été "
                "mis à jour."
            )
    else:
        validation.auto_validate()


def step_load():
    database.main()
    connection = analytics.get_connection()
    try:
        empty = [
            table for table in database.TABLES
            if database.count_rows(connection, table) == 0
        ]
    finally:
        connection.close()
    if empty:
        raise PipelineError(
            f"aucune donnée exploitable dans : {', '.join(empty)}. "
            "Le rapport serait vide."
        )


def step_indicators():
    analytics.main()


def step_report():
    report.main()
