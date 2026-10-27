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


# ---------------------------------------------------------------------------
# Outils d'écriture dans les feuilles
# ---------------------------------------------------------------------------

def to_excel_value(value):
    """Convertit une valeur pandas/numpy en valeur que openpyxl sait écrire."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if hasattr(value, "item"):  # types numpy -> types Python
        value = value.item()
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    return value


def write_title(sheet, title, subtitle=None):
    sheet["A1"] = title
    sheet["A1"].font = TITLE_FONT
    if subtitle:
        sheet["A2"] = subtitle
        sheet["A2"].font = SUBTITLE_FONT


def write_table(sheet, df, row, column=1, title=None, formats=None):
    """Écrit un DataFrame sous forme de tableau mis en forme.

    `formats` associe un nom de colonne à un format de nombre Excel (les
    colonnes en euros sont formatées automatiquement). Renvoie la première
    ligne libre sous le tableau.
    """
    formats = {**{name: EURO for name in EURO_COLUMNS}, **(formats or {})}

    if title:
        sheet.cell(row, column, title).font = SECTION_FONT
        row += 1

    for offset, name in enumerate(df.columns):
        cell = sheet.cell(row, column + offset, LABELS.get(name, name))
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for line, values in enumerate(df.itertuples(index=False), start=1):
        for offset, (name, value) in enumerate(zip(df.columns, values)):
            cell = sheet.cell(row + line, column + offset, to_excel_value(value))
            cell.border = BORDER
            if name in formats:
                cell.number_format = formats[name]
            if line % 2 == 0:
                cell.fill = ZEBRA_FILL

    if df.empty:
        sheet.cell(row + 1, column, "Aucune donnée").font = SUBTITLE_FONT

    return row + max(len(df), 1) + 2


def write_kpi(sheet, row, column, label, value, number_format):
    """Écrit une tuile KPI sur deux colonnes : libellé puis valeur."""
    for line in (row, row + 1):
        sheet.merge_cells(
            start_row=line, start_column=column,
            end_row=line, end_column=column + 1,
        )
        for offset in (0, 1):
            cell = sheet.cell(line, column + offset)
            cell.fill = TILE_FILL
            cell.border = BORDER

    label_cell = sheet.cell(row, column, label)
    label_cell.font = Font(size=10, color="52514E")
    label_cell.alignment = Alignment(horizontal="center")

    value_cell = sheet.cell(row + 1, column, "n/d" if value is None else value)
    value_cell.font = Font(size=18, bold=True, color="1F3A5F")
    value_cell.alignment = Alignment(horizontal="center", vertical="center")
    value_cell.number_format = number_format
    sheet.row_dimensions[row + 1].height = 32


def autosize_columns(sheet, minimum=10, maximum=45):
    """Ajuste la largeur des colonnes au contenu des tableaux (cellules bordées)."""
    widths = {}
    for row in sheet.iter_rows():
        for cell in row:
            if cell.value is None or cell.border.left.style is None:
                continue
            length = len(str(cell.value))
            widths[cell.column] = max(widths.get(cell.column, 0), length)
    for column, length in widths.items():
        width = min(max(length + 2, minimum), maximum)
        sheet.column_dimensions[get_column_letter(column)].width = width


# ---------------------------------------------------------------------------
# Graphiques (matplotlib -> image PNG insérée dans Excel)
# ---------------------------------------------------------------------------

def euro_axis(value, _position):
    return f"{value:,.0f} €".replace(",", " ")


def style_axes(ax, title):
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=12)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=8, length=0)
    ax.set_axisbelow(True)


def to_image(figure, width_px):
    """Convertit une figure matplotlib en image openpyxl de largeur donnée."""
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    plt.close(figure)
    buffer.seek(0)
    image = Image(buffer)
    image.height = image.height * width_px / image.width
    image.width = width_px
    return image


def revenue_chart(comparison, width_px=620):
    """Barres : revenu encaissé ; ligne : revenu récurrent théorique."""
    figure, ax = plt.subplots(figsize=(8, 3.8))
    positions = range(len(comparison))
    ax.bar(
        positions, comparison["collected_revenue"], width=0.6,
        color=BLUE, label="Revenu encaissé",
    )
    ax.plot(
        positions, comparison["recurring_revenue"], color=ORANGE,
        linewidth=2, marker="o", markersize=5,
        label="Revenu récurrent théorique",
    )
    ax.set_xticks(list(positions), comparison["month"], rotation=45, ha="right")
    ax.yaxis.set_major_formatter(FuncFormatter(euro_axis))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.legend(loc="upper left", frameon=False, fontsize=8, labelcolor=INK_MUTED)
    style_axes(ax, "Revenu encaissé vs revenu récurrent théorique, par mois")
    return to_image(figure, width_px)


def collected_chart(monthly, width_px=560):
    """Évolution du revenu encaissé (paiements réussis) par mois."""
    figure, ax = plt.subplots(figsize=(7, 3.6))
    positions = range(len(monthly))
    ax.bar(positions, monthly["collected_revenue"], width=0.6, color=BLUE)
    ax.set_xticks(list(positions), monthly["month"], rotation=45, ha="right")
    ax.yaxis.set_major_formatter(FuncFormatter(euro_axis))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    style_axes(ax, "Revenu encaissé par mois (paiements réussis)")
    return to_image(figure, width_px)


def plan_chart(plans, width_px=420):
    """Nombre d'abonnements par formule (barres horizontales)."""
    figure, ax = plt.subplots(figsize=(5, 2.8))
    ordered = plans.iloc[::-1]  # la formule la plus fréquente en haut
    bars = ax.barh(ordered["plan"], ordered["subscriptions"], height=0.6, color=BLUE)
    ax.bar_label(bars, padding=4, fontsize=8, color=INK)
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    style_axes(ax, "Abonnements par formule")
    return to_image(figure, width_px)


# ---------------------------------------------------------------------------
# Anomalies (fichier produit par cleaning.py)
# ---------------------------------------------------------------------------

def load_anomalies():
    """Charge anomalies/anomalies.csv ; None si cleaning.py n'a pas été lancé."""
    if not ANOMALIES_FILE.exists():
        return None
    return pd.read_csv(ANOMALIES_FILE, encoding="utf-8-sig")


def anomalies_by(anomalies, column):
    """Nombre d'anomalies par valeur de `column`, de la plus fréquente à la moins."""
    counts = anomalies.groupby(column).size().reset_index(name="anomalies")
    return counts.sort_values(
        ["anomalies", column], ascending=[False, True], ignore_index=True
    )


def with_error_type(anomalies):
    """Ajoute le type d'erreur : le message sans la valeur fautive."""
    anomalies = anomalies.copy()
    anomalies["error_type"] = anomalies["error_message"].str.split(" : ").str[0]
    return anomalies


# ---------------------------------------------------------------------------
# Feuilles
# ---------------------------------------------------------------------------

def build_dashboard(sheet, connection, comparison, plans, anomalies):
    write_title(
        sheet,
        "SalesFlow — Tableau de bord",
        f"Généré le {datetime.now():%d/%m/%Y à %H:%M}",
    )
    for column in range(1, 13):
        sheet.column_dimensions[get_column_letter(column)].width = 16

    kpis = [
        ("Chiffre d'affaires encaissé", analytics.collected_revenue(connection), EURO),
        ("Revenu récurrent mensuel", analytics.current_mrr(connection), EURO),
        ("Clients actifs", analytics.active_customers(connection), INTEGER),
        ("Panier moyen", analytics.average_basket(connection), EURO),
        ("Taux d'échec des paiements", analytics.failure_rate(connection), PERCENT),
        ("Anomalies détectées", None if anomalies is None else len(anomalies), INTEGER),
    ]
    for index, (label, value, number_format) in enumerate(kpis):
        write_kpi(sheet, 4, 1 + 2 * index, label, value, number_format)

    if not comparison.empty:
        sheet.add_image(revenue_chart(comparison), "A8")
    if not plans.empty:
        sheet.add_image(plan_chart(plans), "H8")


def build_revenue_sheet(sheet, comparison):
    write_title(
        sheet,
        "Revenue — évolution mensuelle",
        "Revenu encaissé = paiements réussis, au mois de la date de paiement. "
        "Revenu récurrent théorique = prix mensuels des abonnements en cours.",
    )
    end_row = write_table(sheet, comparison, 4)
    autosize_columns(sheet)
    sheet.freeze_panes = "A5"

    monthly = comparison[comparison["successful_payments"] > 0]
    if not monthly.empty:
        anchor_column = get_column_letter(len(comparison.columns) + 2)
        sheet.add_image(collected_chart(monthly), f"{anchor_column}4")
    return end_row
