# SalesFlow — Automated Business Reporting

**SalesFlow** is a Python-based data processing and reporting project designed to automate the transformation of raw business data into reliable, actionable insights.

The project simulates a common challenge faced by SaaS startups: consolidating customer, subscription, and payment data from multiple CSV files to monitor business performance and reduce manual reporting tasks.

> **Project status:** In development  
> **Purpose:** Portfolio project demonstrating Python automation, data cleaning, SQL, and business reporting.

## Objectives

- Automate the import of customer, subscription, and payment data.
- Validate data structures and detect data quality issues.
- Clean and prepare datasets for analysis.
- Store structured data in a SQLite database.
- Calculate business KPIs using SQL and Python.
- Generate an Excel report with tables and visualizations.
- Build a reproducible, maintainable, and testable data pipeline.

## Architecture

```text
Raw CSV files
     |
     v
Data Import
     |
     v
Data Validation & Cleaning
     |
     +------> Data Quality Report
     |
     v
SQLite Database
     |
     v
Business Analytics
     |
     v
Automated Excel Report
```

## Dataset

The project uses synthetic data representing a fictional SaaS company.

| File | Description |
|---|---|
| `customers.csv` | Customer information, registration dates, and countries |
| `subscriptions.csv` | Subscription plans, prices, dates, and statuses |
| `payments.csv` | Payment dates, amounts, statuses, and payment methods |

The dataset intentionally includes data quality issues to test the validation and cleaning pipeline, such as duplicate identifiers, missing amounts, invalid dates, negative values, and inconsistent references between files.

All data is fictional and intended for demonstration purposes only.

## Key Features

### 1. Data Import

- Read CSV files from a dedicated input directory.
- Check file availability and required columns.
- Load datasets using pandas.

### 2. Data Quality & Cleaning

- Detect missing and invalid values.
- Validate date formats and numerical fields.
- Identify duplicate records.
- Detect inconsistent customer and subscription references.
- Record detected issues in a data quality report.
- Separate validated data from records requiring review.

### 3. Database Management

- Store validated data in SQLite.
- Structure customer, subscription, and payment tables.
- Define relationships using primary and foreign keys.
- Use SQL queries to retrieve and aggregate business data.

### 4. Business Analytics

The pipeline is designed to calculate indicators such as:

- Total successful payments.
- Number of active customers.
- Average successful payment amount.
- Monthly revenue trends.
- Payment failure rate.
- Subscription distribution by plan and status.

### 5. Automated Reporting

The reporting module will generate an Excel workbook containing:

- A business KPI summary.
- Monthly revenue analysis.
- Customer and subscription statistics.
- Data quality indicators.
- Tables and charts to support business decisions.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Pipeline development and automation |
| pandas | Data manipulation and cleaning |
| SQL | Data querying and aggregation |
| SQLite | Relational data storage |
| openpyxl | Excel report generation |
| matplotlib | Data visualization |
| pytest | Automated testing |
| Git & GitHub | Version control and project documentation |

## Project Structure

```text
salesflow/
├── data/
│   ├── raw/
│   └── processed/
├── reports/
├── src/
│   ├── import_data.py
│   ├── cleaning.py
│   ├── database.py
│   ├── analytics.py
│   ├── report.py
│   └── main.py
├── tests/
├── requirements.txt
├── .gitignore
└── README.md
```

The structure may evolve as the project develops.

## Getting Started

### Prerequisites

- Python 3.10 or later
- pip

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd salesflow
```

Replace the placeholder with the actual URL of your repository.

### 2. Create a virtual environment

**Windows:**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add the input datasets

Place the three CSV files in `data/raw/`:

```text
data/raw/
├── customers.csv
├── subscriptions.csv
└── payments.csv
```

### 5. Run the pipeline

Once the main pipeline has been implemented:

```bash
python -m src.main
```

The pipeline is intended to generate cleaned datasets, update the SQLite database, calculate KPIs, and produce the Excel report.

## Testing

Tests will be implemented with pytest to verify:

- Data validation and cleaning rules.
- Duplicate detection.
- KPI calculation accuracy.
- Referential integrity.
- Pipeline behavior when input data is invalid.

Run the test suite with:

```bash
pytest
```

## Future Improvements

- Add a Streamlit interface for uploading files and downloading reports.
- Support Excel files in addition to CSV.
- Add configurable validation rules.
- Implement structured logging and error handling.
- Containerize the application with Docker.
- Add automated execution through a scheduled job.
- Compare processing metrics before and after automation.

## Learning Outcomes

This project is an opportunity to develop practical skills in:

- ETL pipeline design.
- Data quality management.
- Relational database modeling.
- SQL-based business analytics.
- Reporting automation.
- Software testing and maintainability.

## Disclaimer

SalesFlow is a personal portfolio project built with synthetic data. It is not affiliated with a real company and does not represent a production-ready financial reporting system.

---

**Author:** Robin Philis  
**Focus:** Python Automation · Data Engineering · SQL · Business Intelligence