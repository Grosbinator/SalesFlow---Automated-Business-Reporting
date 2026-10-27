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
