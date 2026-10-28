"""Reproducible fictional retail orders and inventory for the demonstration."""
from datetime import date, timedelta
import random

PRODUCTS = [
    ("EL-101", "Wireless headphones", "Electronics", 2499, 1420),
    ("EL-102", "Portable speaker", "Electronics", 1799, 980),
    ("EL-103", "USB-C power bank", "Electronics", 1299, 710),
    ("HM-201", "Ceramic coffee set", "Home", 899, 440),
    ("HM-202", "Cotton bed linen", "Home", 1899, 1080),
    ("HM-203", "Desk lamp", "Home", 1199, 690),
    ("OF-301", "Notebook bundle", "Office", 399, 190),
    ("OF-302", "Ergonomic desk mat", "Office", 699, 330),
    ("AP-401", "Everyday cotton tee", "Apparel", 599, 270),
    ("AP-402", "Canvas tote", "Apparel", 349, 140),
    ("GR-501", "Coffee beans 500g", "Grocery", 649, 380),
    ("GR-502", "Breakfast essentials", "Grocery", 499, 310),
]


def generate_demo(today=None):
    today = today or date.today()
    rng = random.Random(4217)
    orders = []
    counter = 0
    regions = ["South", "West", "North", "East"]
    for offset in range(90):
        day = today - timedelta(days=89-offset)
        count = rng.randint(20, 36) + (6 if day.weekday() >= 5 else 0)
        if offset == 80:
            count = 7
        for _ in range(count):
            counter += 1
            sku, name, category, price, cost = rng.choice(PRODUCTS)
            region = rng.choices(regions, weights=[36, 28, 23, 13])[0]
            status = rng.choices(["Delivered", "Processing", "Cancelled"], weights=[91, 4, 5])[0]
            if offset > 86:
                status = rng.choices(["Delivered", "Processing", "Cancelled"], weights=[60, 35, 5])[0]
            target = 3 if region in ("South", "West") else 4
            delay = rng.choices([-1, 0, 1, 2], weights=[28, 52, 14, 6])[0]
            if region == "North" and offset >= 70:
                delay += rng.choice([0, 1, 2])
            orders.append(dict(order_id=f"ORD-{day:%y%m%d}-{counter:05}", order_date=day.isoformat(),
                               sku=sku, product=name, region=region, category=category,
                               channel=rng.choices(["Online", "Retail", "Marketplace"], weights=[50, 30, 20])[0],
                               units=rng.choices([1, 2, 3, 4, 5], weights=[48, 29, 13, 7, 3])[0],
                               unit_price=round(price * rng.choice([1, 1, 1, .95, .9]), 2),
                               unit_cost=cost, status=status,
                               delivery_days=max(1, target+delay) if status == "Delivered" else "",
                               target_delivery_days=target))
    # Keep the original good records and append deliberately bad source records.
    for index in range(12):
        orders.append(dict(orders[index*73]))
    for index in range(9):
        row = dict(orders[index*91])
        row["order_id"] = f"BAD-MISSING-{index}"
        row["region" if index % 2 else "order_date"] = ""
        orders.append(row)
    for index in range(6):
        row = dict(orders[index*61])
        row["order_id"] = f"BAD-VALUE-{index}"
        row["units"] = -2 if index % 2 else "not a number"
        orders.append(row)
    for index in range(18):
        orders[index*47]["region"] = " " + orders[index*47]["region"].lower() + " "
    inventory = []
    for region in regions:
        for sku, name, category, _, cost in PRODUCTS:
            demand = round(rng.uniform(1.2, 8.5), 1)
            stock = rng.randint(8, 240)
            inventory.append(dict(sku=f"{sku}-{region[:1]}", product=name, region=region, category=category,
                                  stock_on_hand=stock, reorder_point=35, avg_daily_units=demand,
                                  unit_cost=cost, snapshot_date=today.isoformat()))
    return orders, inventory
