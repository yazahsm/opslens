"""KPI definitions and calculations, shared by the UI and report exports."""
from datetime import date, timedelta
import math
import pandas as pd
from data import ORDER_COLUMNS

DEFINITIONS = [
    ("Net sales (INR)", "Units x unit price on Delivered orders only. Excludes Processing and Cancelled orders. No tax, shipping or refunds are modeled."),
    ("Orders", "All valid orders placed in the selected dates, including processing and cancelled orders. One source row represents one order for one product."),
    ("On-time delivery", "Delivered orders with delivery_days <= target_delivery_days / all Delivered orders. Processing and Cancelled orders are excluded."),
    ("Gross margin", "(Net sales - units x unit cost on Delivered orders) / net sales. This is gross margin, before overhead and taxes."),
    ("Comparison", "The preceding period of equal length, with the same region and category. Revenue and orders show relative change; rates show percentage-point change."),
    ("Data pass rate", "Accepted source rows / all non-blank source rows. Normalized whitespace/case counts as accepted; invalid rows and later duplicate keys are excluded."),
    ("Inventory", "Latest imported snapshot, independent of the order date filter. Reorder when stock_on_hand <= reorder_point. Coverage is stock_on_hand / avg_daily_units."),
    ("Anomaly", "Daily delivered sales differs by at least 30% and 2.5 population standard deviations from the preceding 7 calendar days. At least 7 prior days and a positive baseline are required."),
]


def frame(dataset):
    df = pd.DataFrame(dataset["rows"], columns=ORDER_COLUMNS)
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["sales"] = (df["units"] * df["unit_price"]).round(2)
    df["cost"] = (df["units"] * df["unit_cost"]).round(2)
    return df


def bounds(dataset, start=None, end=None, days=30):
    dates = [row["order_date"] for row in dataset["rows"]]
    latest = date.fromisoformat(max(dates)) if dates else date.today()
    finish = date.fromisoformat(end) if end else latest
    begin = date.fromisoformat(start) if start else finish - timedelta(days=days - 1)
    if begin > finish:
        raise ValueError("Start date must be on or before end date")
    if (finish - begin).days > 3660:
        raise ValueError("Choose a reporting period of at most 10 years")
    return begin, finish


def select(df, start, end, region="", category=""):
    result = df[(df["order_date"] >= pd.Timestamp(start)) & (df["order_date"] <= pd.Timestamp(end))]
    if region:
        result = result[result["region"] == region]
    if category:
        result = result[result["category"] == category]
    return result


def kpis(df):
    delivered = df[df["status"] == "Delivered"]
    sales = float(delivered["sales"].sum())
    cost = float(delivered["cost"].sum())
    on_time = int((delivered["delivery_days"] <= delivered["target_delivery_days"]).sum())
    return {"sales": round(sales, 2), "orders": len(df), "delivered": len(delivered),
            "processing": int((df["status"] == "Processing").sum()),
            "cancelled": int((df["status"] == "Cancelled").sum()),
            "on_time": round(on_time / len(delivered) * 100, 2) if len(delivered) else None,
            "margin": round((sales - cost) / sales * 100, 2) if sales else None,
            "gross_profit": round(sales - cost, 2), "units": int(delivered["units"].sum()),
            "average_order_value": round(sales / len(delivered), 2) if len(delivered) else None}


def delta(current, previous, percentage_points=False):
    if current is None or previous is None or (not percentage_points and previous == 0):
        return None
    return round(current - previous if percentage_points else (current - previous) / abs(previous) * 100, 2)


def summarize(dataset, start=None, end=None, region="", category="", days=30):
    begin, finish = bounds(dataset, start, end, days)
    length = (finish - begin).days + 1
    previous_begin = begin - timedelta(days=length)
    previous_end = begin - timedelta(days=1)
    df = frame(dataset)
    current = select(df, begin, finish, region, category)
    previous = select(df, previous_begin, previous_end, region, category)
    current_kpis, previous_kpis = kpis(current), kpis(previous)
    delivered = current[current["status"] == "Delivered"]
    def revenue_by(data):
        return data[data["status"] == "Delivered"].groupby("order_date")["sales"].sum()
    daily, previous_daily = revenue_by(current), revenue_by(previous)
    trend = []
    for offset in range(length):
        day = begin + timedelta(days=offset)
        prior = previous_begin + timedelta(days=offset)
        trend.append({"date": day.isoformat(), "sales": round(float(daily.get(pd.Timestamp(day), 0)), 2),
                      "previous": round(float(previous_daily.get(pd.Timestamp(prior), 0)), 2)})
    categories = [{"category": name, "sales": round(float(group["sales"].sum()), 2), "orders": len(group)}
                  for name, group in delivered.groupby("category")]
    categories.sort(key=lambda row: row["sales"], reverse=True)
    regions = []
    for name, group in delivered.groupby("region"):
        on_time = int((group["delivery_days"] <= group["target_delivery_days"]).sum())
        regions.append({"region": name, "orders": len(group), "on_time": round(on_time / len(group) * 100, 1),
                        "average_days": round(float(group["delivery_days"].mean()), 1),
                        "sales": round(float(group["sales"].sum()), 2)})
    regions.sort(key=lambda row: row["sales"], reverse=True)
    anomalies = []
    # Include days before the selected period so a short selection can still be evaluated.
    historical = select(df, begin - timedelta(days=7), finish, region, category)
    series = revenue_by(historical).reindex(pd.date_range(begin - timedelta(days=7), finish), fill_value=0)
    first_source = df["order_date"].min() if len(df) else None
    for offset, item in enumerate(trend):
        day = pd.Timestamp(item["date"])
        if first_source is None or day - pd.Timedelta(days=7) < first_source:
            continue
        history = series.loc[day - pd.Timedelta(days=7):day - pd.Timedelta(days=1)]
        baseline = float(history.mean())
        std = float(history.std(ddof=0))
        change = (item["sales"] - baseline) / baseline * 100 if baseline > 0 else 0
        z = abs(item["sales"] - baseline) / std if std > 0 else (math.inf if item["sales"] != baseline else 0)
        if abs(change) >= 30 and z >= 2.5:
            anomalies.append({"date": item["date"], "sales": item["sales"], "baseline": round(baseline, 2), "change": round(change, 1)})
    anomalies.sort(key=lambda row: abs(row["change"]), reverse=True)
    return {"period": {"start": begin.isoformat(), "end": finish.isoformat(), "previous_start": previous_begin.isoformat(),
                       "previous_end": previous_end.isoformat(), "days": length, "region": region, "category": category},
            "kpis": current_kpis, "previous": previous_kpis,
            "deltas": {key: delta(current_kpis[key], previous_kpis[key], key in ("on_time", "margin"))
                       for key in ("sales", "orders", "on_time", "margin")},
            "trend": trend, "categories": categories, "regions": regions, "anomalies": anomalies[:6]}


def order_records(dataset, start=None, end=None, region="", category="", days=30, search="", status="", page=1, page_size=15):
    begin, finish = bounds(dataset, start, end, days)
    df = select(frame(dataset), begin, finish, region, category)
    if status:
        df = df[df["status"] == status]
    if search:
        search = search.casefold()
        df = df[df.apply(lambda row: search in " ".join(str(row[c]) for c in ("order_id", "product", "sku")).casefold(), axis=1)]
    total = len(df)
    df = df.sort_values(["order_date", "order_id"], ascending=[False, False])
    if page_size:
        df = df.iloc[(page-1)*page_size:page*page_size]
    rows = []
    for row in df.to_dict(orient="records"):
        row["order_date"] = row["order_date"].date().isoformat()
        row = {key: None if pd.isna(value) else value for key, value in row.items()}
        row["order_value"] = row["sales"]
        row["net_sales"] = row["sales"] if row["status"] == "Delivered" else 0
        rows.append(row)
    return {"rows": rows, "total": total, "page": page, "page_size": page_size}


def inventory_summary(dataset, region="", category="", search=""):
    rows = []
    for source in dataset["rows"]:
        if region and source["region"] != region or category and source["category"] != category:
            continue
        if search and search.casefold() not in (source["sku"] + " " + source["product"]).casefold():
            continue
        row = dict(source)
        row["low_stock"] = row["stock_on_hand"] <= row["reorder_point"]
        row["coverage_days"] = round(row["stock_on_hand"] / row["avg_daily_units"], 1) if row["avg_daily_units"] else None
        row["stock_value"] = round(row["stock_on_hand"] * row["unit_cost"], 2)
        rows.append(row)
    rows.sort(key=lambda row: (not row["low_stock"], row["coverage_days"] if row["coverage_days"] is not None else math.inf))
    return {"rows": rows, "sku_locations": len(rows), "low_stock": sum(row["low_stock"] for row in rows),
            "stock_units": sum(row["stock_on_hand"] for row in rows),
            "stock_value": round(sum(row["stock_value"] for row in rows), 2),
            "snapshot_dates": sorted({row["snapshot_date"] for row in rows})}
