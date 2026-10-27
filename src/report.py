"""Génération du rapport Excel reports/monthly_report.xlsx.

Feuilles :
- Dashboard     : indicateurs clés et graphiques ;
- Revenue       : évolution mensuelle des paiements réussis ;
- Customers     : liste et statistiques des clients ;
- Subscriptions : répartition par formule et par statut ;
- Data Quality  : résumé des anomalies détectées par cleaning.py.

Les chiffres viennent de analytics.py (agrégations SQL) ; ce module ne fait
que la mise en forme (openpyxl) et les graphiques (matplotlib).

Usage : python src/report.py   (après cleaning.py et database.py)
"""

from datetime import datetime
from io import BytesIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # pas de fenêtre : les graphiques deviennent des images

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.drawing.image import Image  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

import analytics  # noqa: E402
from cleaning import ANOMALIES_FILE, ANOMALY_COLUMNS  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parent.parent
REPORT_FILE = ROOT_DIR / "reports" / "monthly_report.xlsx"

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

# Couleurs des graphiques : palette lisible y compris par les daltoniens.
BLUE = "#2a78d6"
ORANGE = "#eb6834"
INK = "#0b0b0b"
INK_MUTED = "#52514e"
GRID = "#e4e3df"

TITLE_FONT = Font(size=16, bold=True, color="1F3A5F")
SUBTITLE_FONT = Font(size=10, italic=True, color="52514E")
SECTION_FONT = Font(size=12, bold=True, color="1F3A5F")
HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
ZEBRA_FILL = PatternFill("solid", fgColor="F4F6F9")
TILE_FILL = PatternFill("solid", fgColor="EEF3FA")
THIN = Side(style="thin", color="D0D5DD")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

EURO = '#,##0.00 "€"'
PERCENT = "0.0%"
INTEGER = "0"

# Libellés français des colonnes renvoyées par analytics.py.
LABELS = {
    "indicator": "Indicateur",
    "value": "Valeur",
    "month": "Mois",
    "recurring_revenue": "Revenu récurrent théorique",
    "collected_revenue": "Revenu encaissé",
    "gap": "Écart",
    "running_subscriptions": "Abonnements en cours",
    "successful_payments": "Paiements réussis",
    "plan": "Formule",
    "subscriptions": "Abonnements",
    "active_subscriptions": "Abonnements actifs",
    "share_pct": "Part (%)",
    "active": "Actifs",
    "cancelled": "Résiliés",
    "total": "Total",
    "customer_id": "ID client",
    "company_name": "Entreprise",
    "email": "Email",
    "country": "Pays",
    "signup_date": "Inscription",
    "active_plans": "Formules actives",
    "total_paid": "Total payé",
    "last_payment_date": "Dernier paiement",
    "is_active": "Client actif",
    "customers": "Clients",
    "active_customers": "Clients actifs",
    "file_name": "Fichier",
    "row_number": "Ligne",
    "column_name": "Colonne",
    "error_message": "Message",
    "error_type": "Type d'erreur",
    "anomalies": "Anomalies",
}
EURO_COLUMNS = {"recurring_revenue", "collected_revenue", "gap", "total_paid"}
