"""Run with: python app.py --port 8020. Local single-user demonstration."""
import argparse
from collections import Counter
import io
import os
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from analytics import DEFINITIONS, bounds, inventory_summary, order_records, summarize
from data import Store, clean, columns, metadata, parse_file
from demo import generate_demo
from reports import csv_bytes, excel_bytes, rejected_rows

ROOT = Path(__file__).resolve().parent


def create_app(database=None):
    store = Store(database or Path(os.environ.get("OPS_DATA_DIR", ROOT / ".local")) / "operations.db")
    def demo():
        orders, inventory = generate_demo()
        for kind, rows in [("orders", orders), ("inventory", inventory)]:
            store.save(kind, f"Demo {kind}", clean(rows, kind), is_demo=True)
    if store.get("orders") is None or store.get("inventory") is None:
        demo()
    app = FastAPI(title="Operations Performance Dashboard", version="1.0.0")
    app.state.store = store

    @app.exception_handler(ValueError)
    async def invalid_input(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    def filters(start: str | None = None, end: str | None = None, region: str = "", category: str = "", days: int = Query(30, ge=1, le=3660)):
        return dict(start=start, end=end, region=region, category=category, days=days)

    from fastapi import Depends

    @app.get("/api/health")
    def health():
        return {"status": "ok", "app": "Operations Performance Dashboard"}

    @app.get("/api/meta")
    def meta():
        orders, inventory = store.get("orders"), store.get("inventory")
        dates = sorted(row["order_date"] for row in orders["rows"])
        rows = orders["rows"] + inventory["rows"]
        return {"datasets": [metadata(orders), metadata(inventory)], "regions": sorted({row["region"] for row in rows}),
                "categories": sorted({row["category"] for row in rows}), "min_date": dates[0] if dates else None,
                "max_date": dates[-1] if dates else None, "definitions": DEFINITIONS, "currency": "INR"}

    @app.get("/api/overview")
    def overview(scope=Depends(filters)):
        summary = summarize(store.get("orders"), **scope)
        inv = inventory_summary(store.get("inventory"), scope["region"], scope["category"])
        summary["inventory"] = {k: v for k, v in inv.items() if k != "rows"}
        summary["inventory"]["exceptions"] = [row for row in inv["rows"] if row["low_stock"]][:5]
        return summary

    @app.get("/api/orders")
    def orders(scope=Depends(filters), search: str = Query("", max_length=100), status: str = "",
               page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=100)):
        if status and status not in ("Delivered", "Processing", "Cancelled"):
            raise ValueError("Unknown order status")
        return order_records(store.get("orders"), **scope, search=search, status=status, page=page, page_size=page_size)

    @app.get("/api/inventory")
    def inventory(region: str = "", category: str = "", search: str = Query("", max_length=100)):
        return inventory_summary(store.get("inventory"), region, category, search)

    @app.get("/api/quality")
    def quality(kind: str = "orders", page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=100)):
        data = store.get(kind)
        counts = Counter(reason.split(":")[0] for row in data["rejected"] for reason in row["reasons"])
        return {**metadata(data), "issues": [{"field": key, "count": value} for key, value in counts.most_common()],
                "rejected": data["rejected"][(page-1)*page_size:page*page_size], "repairs": data["repairs"][:20],
                "page": page, "total": data["rejected_count"]}

    @app.post("/api/imports/preview")
    async def preview(kind: str = "orders", file: UploadFile = File(...)):
        columns(kind)
        content = await file.read(5 * 1024 * 1024 + 1)
        name = Path((file.filename or "upload").replace("\\", "/")).name[:120]
        rows = parse_file(name, content, kind)
        result = clean(rows, kind)
        token = store.preview(kind, name, result)
        return {"token": token, "name": name, "kind": kind, "columns": columns(kind),
                **{k: result[k] for k in ("raw_count", "accepted_count", "rejected_count", "normalized_count", "pass_rate")},
                "sample": result["rows"][:5], "rejected": result["rejected"][:8]}

    class ApplyRequest(BaseModel):
        token: str = Field(min_length=32, max_length=32)

    @app.post("/api/imports/apply")
    def apply_import(payload: ApplyRequest):
        identifier = store.apply(payload.token)
        return {"id": identifier, "message": "Dataset applied. The previous revision is retained in source history."}

    @app.post("/api/demo")
    def restore_demo():
        demo()
        return {"ok": True}

    @app.get("/api/history")
    def history():
        import json
        with store.connect() as db:
            rows = db.execute("SELECT id,kind,name,created_at,payload,is_demo FROM datasets ORDER BY rowid DESC LIMIT 30").fetchall()
        return [{"id": row[0], "kind": row[1], "name": row[2], "created_at": row[3],
                 "accepted_count": json.loads(row[4])["accepted_count"], "is_demo": bool(row[5])} for row in rows]

    @app.post("/api/history/{identifier}/activate")
    def activate(identifier: str):
        with store.connect() as db:
            row = db.execute("SELECT kind FROM datasets WHERE id=?", (identifier,)).fetchone()
            if not row:
                raise HTTPException(404, "Revision not found")
            db.execute("INSERT OR REPLACE INTO active VALUES (?,?)", (row[0], identifier))
        return {"ok": True, "kind": row[0]}

    def download(body, media, name):
        return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @app.get("/api/templates/{kind}.csv")
    def template(kind: str):
        demo_orders, demo_inventory = generate_demo()
        rows = demo_orders[:3] if kind == "orders" else demo_inventory[:3]
        return download(csv_bytes(rows, columns(kind)), "text/csv", f"{kind}-template.csv")

    @app.get("/api/export/orders.csv")
    def export_orders(scope=Depends(filters), search: str = Query("", max_length=100), status: str = ""):
        if status and status not in ("Delivered", "Processing", "Cancelled"):
            raise ValueError("Unknown order status")
        rows = order_records(store.get("orders"), **scope, search=search, status=status, page_size=0)["rows"]
        return download(csv_bytes(rows, columns("orders") + ["order_value", "net_sales"]), "text/csv", "operations-orders.csv")

    @app.get("/api/export/rejected/{kind}.csv")
    def export_rejected(kind: str):
        data = store.get(kind)
        return download(csv_bytes(rejected_rows(data), ["source_row", "record_key", "reason"] + columns(kind)), "text/csv", f"{kind}-excluded.csv")

    @app.get("/api/export/report.xlsx")
    def export_report(scope=Depends(filters)):
        orders, inventory = store.get("orders"), store.get("inventory")
        summary = summarize(orders, **scope)
        records = order_records(orders, **scope, page_size=0)["rows"]
        inv = inventory_summary(inventory, scope["region"], scope["category"])
        body = excel_bytes(summary, records, inv, [orders, inventory])
        return download(body, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "operations-performance.xlsx")

    app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
    return app


app = create_app()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8020)
    args = parser.parse_args()
    import uvicorn
    print(f"Operations dashboard: http://127.0.0.1:{args.port}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, http="h11", ws="none")
