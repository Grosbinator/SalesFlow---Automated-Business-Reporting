"""Point d'entrée de SalesFlow : lance toute la chaîne de traitement.

    python main.py                  # chaîne complète sur data/sample/ ; une
                                    # fenêtre s'ouvre pour traiter les anomalies
    python main.py --source DOSSIER # importe les CSV d'un autre dossier
    python main.py --interactive    # anomalies traitées dans la console
    python main.py --auto           # sans fenêtre : lignes en anomalie écartées
    python main.py --skip-import    # réutilise data/raw/ sans réimporter

Le dossier source peut aussi être donné par la variable d'environnement
SALESFLOW_SOURCE_DIR (voir src/import_data.py).

Étapes, dans l'ordre :
1. Import des fichiers sources (dossier source -> data/raw/)
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
import validation_gui  # noqa: E402


class PipelineError(Exception):
    """Erreur bloquante détectée par le pipeline lui-même."""


# ---------------------------------------------------------------------------
# Étapes
# ---------------------------------------------------------------------------

def step_import(source=None):
    import_data.import_csv_files(source)


def step_clean_and_validate(mode="gui"):
    """Contrôle qualité, puis validation des anomalies selon `mode` :
    "gui" (fenêtre), "console" ou "auto" (lignes en anomalie écartées)."""
    cleaning.main()
    print()
    if mode == "auto":
        validation.auto_validate()
        return

    if mode == "gui":
        try:
            saved = validation_gui.gui_validate()
        except validation_gui.tk.TclError as error:
            # Pas d'écran (serveur, tâche planifiée) : pas de blocage.
            print(f"Fenêtre impossible à ouvrir ({error}) : validation automatique.")
            validation.auto_validate()
            return
    else:
        saved = validation.main()

    if not saved:
        raise PipelineError(
            "validation annulée : data/processed/ n'a pas été mis à jour."
        )


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


def build_steps(validation_mode="gui", skip_import=False, source=None):
    """Liste des étapes : (titre, fonction, piste de résolution en cas d'échec)."""
    steps = [
        (
            "Import des fichiers sources",
            lambda: step_import(source),
            "Vérifier que customers.csv, subscriptions.csv et payments.csv sont "
            "dans le dossier source (--source DOSSIER ou SALESFLOW_SOURCE_DIR), "
            "ou relancer avec --skip-import pour réutiliser data/raw/.",
        ),
        (
            "Nettoyage et validation",
            lambda: step_clean_and_validate(validation_mode),
            "Vérifier les colonnes des CSV de data/raw/.",
        ),
        (
            "Chargement dans SQLite",
            step_load,
            "Vérifier les données nettoyées : python src/validation.py",
        ),
        ("Calcul des indicateurs", step_indicators, None),
        (
            "Génération du rapport Excel",
            step_report,
            "Fermer le rapport s'il est ouvert dans Excel, puis relancer.",
        ),
    ]
    return steps[1:] if skip_import else steps


# ---------------------------------------------------------------------------
# Exécution
# ---------------------------------------------------------------------------

def run_pipeline(steps, show=print):
    """Exécute les étapes dans l'ordre ; s'arrête à la première erreur.

    Renvoie le code de sortie : 0 si tout a réussi, 1 en cas d'échec,
    130 si l'utilisateur a interrompu (Ctrl+C).
    """
    total = len(steps)
    started = time.perf_counter()

    for number, (title, action, hint) in enumerate(steps, start=1):
        show(f"\n=== [{number}/{total}] {title} ===")
        step_started = time.perf_counter()
        try:
            action()
        except KeyboardInterrupt:
            show(f"\nInterrompu pendant l'étape {number}/{total} ({title}).")
            return 130
        except Exception as error:  # toute erreur arrête proprement la chaîne
            cause = (
                str(error) if isinstance(error, PipelineError)
                else f"{type(error).__name__} : {error}"
            )
            show(f"\nÉCHEC à l'étape {number}/{total} ({title})")
            show(f"  Cause : {cause}")
            if hint:
                show(f"  Piste : {hint}")
            show("Pipeline arrêté : les étapes suivantes n'ont pas été lancées "
                 "et le rapport n'a pas été mis à jour.")
            return 1
        show(f"-> OK ({time.perf_counter() - step_started:.1f} s)")

    show(f"\nPipeline terminé en {time.perf_counter() - started:.1f} s. "
         f"Rapport : {report.REPORT_FILE}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="SalesFlow : import, nettoyage, base SQLite, "
                    "indicateurs et rapport Excel."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--interactive", action="store_true",
        help="traiter les anomalies dans la console au lieu de la fenêtre",
    )
    mode.add_argument(
        "--auto", action="store_true",
        help="sans fenêtre ni question : les lignes en anomalie sont écartées",
    )
    parser.add_argument(
        "--skip-import", action="store_true",
        help="ne pas réimporter, réutiliser les fichiers de data/raw/",
    )
    parser.add_argument(
        "--source", metavar="DOSSIER",
        help="dossier des CSV sources (défaut : SALESFLOW_SOURCE_DIR, "
             "sinon data/sample/)",
    )
    args = parser.parse_args(argv)
    if args.skip_import and args.source:
        parser.error("--source et --skip-import sont incompatibles")
    validation_mode = (
        "console" if args.interactive else "auto" if args.auto else "gui"
    )
    return run_pipeline(
        build_steps(validation_mode, args.skip_import, args.source)
    )


if __name__ == "__main__":
    sys.exit(main())
