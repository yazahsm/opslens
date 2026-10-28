# OpsLens — Operations Analytics Dashboard

An operations analytics MVP with sales KPIs, inventory monitoring, data quality checks, CSV/XLSX imports, revision history, and Excel reports. Built with Python, Pandas, FastAPI, SQLite, and HTML/CSS/JavaScript. All initial business records are fictional.

## Quick start

Requires Python 3.11 or newer. Run from the repository root.

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

**macOS / Linux**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Open **http://127.0.0.1:8020**. API documentation: **http://127.0.0.1:8020/docs**. Stop with Ctrl+C; use `--port 8021` for another port. Fictional demo data is generated on first run.

## Try the demo

1. **Overview:** change the period, region or category. Compare delivered sales with the preceding period. Switch the sales chart between daily and weekly buckets. Click a category bar to filter.
2. **Orders:** search order IDs, products or SKUs; filter statuses; inspect a record; paginate; export matching rows to CSV.
3. **Inventory:** review stock by location, reorder exceptions and stock coverage. This is a dated snapshot; it intentionally ignores the order date range. Region and category filters apply.
4. **Data quality:** inspect input, accepted and excluded row counts, validation reasons, normalization counts and original source row numbers. Download excluded records with their source values.
5. **Reports:** export a formatted nine-sheet Excel workbook, including the KPI summary, daily trend, category breakdown and native chart, order records, inventory, quality results, exclusions, definitions and provenance.
6. **Import data:** download the appropriate template, choose CSV or XLSX, preview validation, then apply the accepted records. Orders and inventory are independent datasets; changing one does not replace the other. A mixed demo/imported source label makes this visible.
7. **Source history:** restore an earlier revision or reload the demo. Previous data revisions are retained. The interface lists the 30 most recent revisions.

## Demo data

The initial dataset covers 90 calendar days ending on the first-run date, plus 48 SKU/location inventory records. It includes four regions, five product categories and three sales channels. A fixed random seed makes it reproducible for a given end date. A recent sales dip and a regional delivery slowdown exercise the anomaly and fulfilment views.

The order source deliberately contains 12 later duplicate keys, nine missing-field records, six invalid-quantity records and 18 accepted records requiring text normalization. Rejected rows do not contribute to KPIs. Counts and pass rates are calculated from source records, not hardcoded display values.

## Definitions and limits

- One source row is one order for one product, not a line in a multi-product order. `order_id` must be unique.
- Currency is INR for all data and reports. There is no exchange-rate conversion.
- Exports include both `order_value` (all order statuses) and `net_sales` (Delivered only), so exported net sales reconcile with the dashboard.
- Net sales count Delivered orders only. Processing and Cancelled orders are excluded. Tax, shipping and refunds are not modeled.
- Total orders count all valid order statuses. On-time delivery counts Delivered orders with actual delivery days less than or equal to the target.
- Gross margin is `(delivered sales - delivered product cost) / delivered sales`. Overhead is excluded.
- The comparison uses the preceding equal-length period with matching region/category filters. A missing or zero comparison baseline displays “No comparison.” Rate differences use percentage points.
- An anomaly requires at least seven prior calendar days, a positive sales baseline, a change of at least 30%, and a deviation of at least 2.5 population standard deviations. These are review signals, not forecasts or proof of a business cause.
- Stock value is stock on hand multiplied by unit cost. Low stock means stock is at or below its reorder point. Coverage is stock divided by average daily units; zero demand displays “No demand.”
- Quality results and excluded-row downloads describe the complete source dataset, independently of dashboard filters.
- Import up to 10,000 rows and 5 MB per file. XLSX is read from its first sheet. Workbook formulas are not evaluated; required numeric/date fields must contain values. `.xls` and macro-enabled workbooks are not supported.
- Required dates use `YYYY-MM-DD`, without future dates. Money uses at most two decimals. Blank source rows are ignored. Duplicate handling keeps the first valid key. Inventory keys are `(sku, region)`.

## Persistence and privacy

The database lives at `.local/operations.db`. Datasets, excluded source values, normalization details, revision hashes and active dataset choices persist across restarts. Import previews expire after one day. Set `OPS_DATA_DIR` before starting to choose a different data directory. Browser filters are session state and reset on reload.

This app binds to loopback for a single local user and has no login, cloud integration or external analytics. Do not expose it as a shared server without adding the appropriate authentication and deployment controls. This rebuild does not include native Power BI, Tableau or VBA project files.

## Checks

From the repository root:

```powershell
.\.venv\Scripts\python.exe -X utf8 tests/test_operations.py
node tests/check_frontend.cjs
```

The backend suite checks calculations against small known examples, validation, CSV/XLSX import, non-mutating previews, source persistence/restoration, filters, exports, empty selections, anomaly thresholds and formula-injection handling. Frontend checks cover syntax, element references, formatting, chart generation and safe rendering. Browser automation was unavailable during development, so visual layout and click-through acceptance remain unverified.
