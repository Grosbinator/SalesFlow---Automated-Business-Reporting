# Sample data

Synthetic exports of a fictional SaaS company, used by default by `python main.py`.
All companies and email addresses are fictional (`.example` domains).

| File | Rows |
|---|---|
| `customers.csv` | 15 customers |
| `subscriptions.csv` | 16 subscriptions |
| `payments.csv` | 21 payments |

## Intentional data quality issues

The files contain errors on purpose, to show how the pipeline detects and handles them
(line numbers refer to the CSV file, the header being line 1):

| File | Line | Issue |
|---|---|---|
| `subscriptions.csv` | 17 | `S016` belongs to customer `C999`, who does not exist |
| `payments.csv` | 18 | `P017` has no amount |
| `payments.csv` | 19 | `P018` refers to subscription `S999`, which does not exist |
| `payments.csv` | 20 | `P019` is duplicated, and this copy has an invalid date (`2026-13-40`) |
| `payments.csv` | 21 | second `P019` (duplicate identifier) |
| `payments.csv` | 22 | `P020` has a negative amount (`-29.0`) |

Run `python main.py` and open `anomalies/anomalies.csv` or the **Data Quality** sheet of the
Excel report to see them; run `python main.py --interactive` to fix them one by one.
