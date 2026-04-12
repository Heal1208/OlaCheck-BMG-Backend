from flask import Blueprint, request, jsonify, send_file
from database import get_db
from utils import token_required, role_required, MANAGER_AND_ABOVE
import io, csv
from datetime import datetime

stats_bp = Blueprint("stats", __name__, url_prefix="/api/stats")

# ================================================================
# A-11: Staff Schedule / Work Monitoring
# ================================================================
@stats_bp.route("/staff-schedule", methods=["GET"])
@token_required
@role_required(*MANAGER_AND_ABOVE)
def staff_schedule(current_user):
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    conn = get_db()

    staff_list = conn.execute("""
        SELECT u.user_id, u.full_name, u.email, u.phone,
               COUNT(DISTINCT s.store_id) AS total_assigned_stores
        FROM users u
        JOIN roles r ON u.role_id = r.role_id
        LEFT JOIN stores s ON s.assigned_staff_id = u.user_id AND s.is_active = 1
        WHERE r.role_name = 'Staff' AND u.is_active = 1
        GROUP BY u.user_id
    """).fetchall()

    result = []
    for staff in staff_list:
        uid = staff["user_id"]
        checkins = conn.execute("""
            SELECT c.check_id, c.store_id, c.check_time, c.status, c.note,
                   s.store_name, s.district, s.city
            FROM store_checks c
            JOIN stores s ON c.store_id = s.store_id
            WHERE c.staff_id = ? AND DATE(c.check_time) = ?
            ORDER BY c.check_time ASC
        """, (uid, date)).fetchall()

        checkin_details = []
        for c in checkins:
            stock_count = conn.execute(
                "SELECT COUNT(*) FROM stock_entries WHERE check_id = ?", (c["check_id"],)
            ).fetchone()[0]
            expiry_count = conn.execute("""
                SELECT COUNT(*) FROM expiry_records er
                JOIN stock_entries se ON er.entry_id = se.entry_id
                WHERE se.check_id = ?
            """, (c["check_id"],)).fetchone()[0]
            checkin_details.append({
                "check_id": c["check_id"], "store_id": c["store_id"],
                "store_name": c["store_name"], "district": c["district"],
                "city": c["city"], "check_time": c["check_time"],
                "status": c["status"], "note": c["note"],
                "stock_entered": stock_count > 0,
                "expiry_checked": expiry_count > 0,
                "steps_done": 1 + (1 if stock_count > 0 else 0) + (1 if expiry_count > 0 else 0),
            })

        total = staff["total_assigned_stores"]
        done = len([c for c in checkin_details if c["status"] == "completed"])
        result.append({
            "user_id": uid, "full_name": staff["full_name"],
            "email": staff["email"], "phone": staff["phone"],
            "total_stores": total, "done_stores": done,
            "completion_pct": round((done / total * 100) if total > 0 else 0),
            "checkins": checkin_details,
        })

    conn.close()
    return jsonify({"success": True, "data": {"date": date, "schedule": result}}), 200


# ================================================================
# A-12: Inventory Statistics
# ================================================================
@stats_bp.route("/inventory", methods=["GET"])
@token_required
@role_required(*MANAGER_AND_ABOVE)
def inventory_stats(current_user):
    date_from = request.args.get("date_from", "")
    date_to   = request.args.get("date_to", "")
    store_id  = request.args.get("store_id", "")
    product_id = request.args.get("product_id", "")

    where, params = "WHERE 1=1", []
    if date_from: where += " AND DATE(c.check_time) >= ?"; params.append(date_from)
    if date_to:   where += " AND DATE(c.check_time) <= ?"; params.append(date_to)
    if store_id:  where += " AND c.store_id = ?";          params.append(store_id)
    if product_id: where += " AND se.product_id = ?";      params.append(product_id)

    conn = get_db()
    by_product = conn.execute(f"""
        SELECT p.product_id, p.product_name, p.sku, p.unit,
               SUM(se.quantity_on_shelf) AS total_qty,
               COUNT(DISTINCT c.store_id) AS store_count,
               AVG(se.quantity_on_shelf) AS avg_qty
        FROM stock_entries se
        JOIN store_checks c ON se.check_id = c.check_id
        JOIN products p ON se.product_id = p.product_id
        {where}
        GROUP BY p.product_id ORDER BY total_qty DESC
    """, params).fetchall()

    by_store = conn.execute(f"""
        SELECT s.store_id, s.store_name, s.store_type, s.district, s.city,
               SUM(se.quantity_on_shelf) AS total_qty,
               MAX(c.check_time) AS last_checkin
        FROM stock_entries se
        JOIN store_checks c ON se.check_id = c.check_id
        JOIN stores s ON c.store_id = s.store_id
        {where}
        GROUP BY s.store_id ORDER BY total_qty DESC
    """, params).fetchall()

    timeline = conn.execute(f"""
        SELECT DATE(c.check_time) AS report_date,
               SUM(se.quantity_on_shelf) AS total_qty
        FROM stock_entries se
        JOIN store_checks c ON se.check_id = c.check_id
        {where}
        GROUP BY DATE(c.check_time) ORDER BY report_date ASC LIMIT 30
    """, params).fetchall()

    products = conn.execute(
        "SELECT product_id, product_name, sku FROM products WHERE is_active=1 ORDER BY product_name"
    ).fetchall()
    stores = conn.execute(
        "SELECT store_id, store_name, district FROM stores WHERE is_active=1 ORDER BY store_name"
    ).fetchall()
    open_alerts = conn.execute(
        "SELECT COUNT(*) FROM stock_alerts WHERE is_resolved=0 AND alert_type='low_stock'"
    ).fetchone()[0]
    conn.close()

    return jsonify({"success": True, "data": {
        "summary": {
            "total_products": len(by_product), "total_stores": len(by_store),
            "open_low_stock": open_alerts,
            "grand_total_qty": sum(r["total_qty"] or 0 for r in by_product),
        },
        "by_product": [dict(r) for r in by_product],
        "by_store":   [dict(r) for r in by_store],
        "timeline":   [dict(r) for r in timeline],
        "filter_options": {
            "products": [dict(p) for p in products],
            "stores":   [dict(s) for s in stores],
        },
    }}), 200


# ================================================================
# A-15: Export CSV
# ================================================================
@stats_bp.route("/export", methods=["GET"])
@token_required
@role_required(*MANAGER_AND_ABOVE)
def export_report(current_user):
    date_from = request.args.get("date_from", "")
    date_to   = request.args.get("date_to", "")
    store_id  = request.args.get("store_id", "")
    product_id = request.args.get("product_id", "")

    where, params = "WHERE 1=1", []
    if date_from: where += " AND DATE(c.check_time) >= ?"; params.append(date_from)
    if date_to:   where += " AND DATE(c.check_time) <= ?"; params.append(date_to)
    if store_id:  where += " AND c.store_id = ?";          params.append(store_id)
    if product_id: where += " AND se.product_id = ?";      params.append(product_id)

    conn = get_db()
    rows = conn.execute(f"""
        SELECT s.store_name, s.district, s.city,
               p.product_name, p.sku, se.quantity_on_shelf,
               DATE(c.check_time) AS report_date, u.full_name AS staff_name
        FROM stock_entries se
        JOIN store_checks c ON se.check_id = c.check_id
        JOIN stores s ON c.store_id = s.store_id
        JOIN products p ON se.product_id = p.product_id
        JOIN users u ON c.staff_id = u.user_id
        {where}
        ORDER BY c.check_time DESC LIMIT 5000
    """, params).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Cửa hàng", "Quận/Huyện", "Thành phố",
                     "Sản phẩm", "SKU", "Số lượng tồn", "Ngày báo cáo", "Nhân viên"])
    for r in rows:
        writer.writerow([r["store_name"], r["district"], r["city"],
                         r["product_name"], r["sku"], r["quantity_on_shelf"],
                         r["report_date"], r["staff_name"]])

    output.seek(0)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv", as_attachment=True,
        download_name=f"BMG_inventory_{ts}.csv"
    )