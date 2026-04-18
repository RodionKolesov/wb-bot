from wb_api import msk_date, msk_label

def fmt(v) -> str:
    return f"{int(v):,}".replace(",", "\u202f")

def format_sales(rows: list) -> str:
    day1_date = msk_date(1)
    day2_date = msk_date(2)
    day1_label = msk_label(1)
    day2_label = msk_label(2)

    stats = {
        day1_date: {"title": "Вчера", "label": day1_label, "sum": 0, "count": 0, "products": {}},
        day2_date: {"title": "Позавчера", "label": day2_label, "sum": 0, "count": 0, "products": {}},
    }

    for row in rows:
        product = row.get("product") or {}
        history = row.get("history") or []
        for day in history:
            date = str(day.get("date") or "")
            if date not in stats:
                continue
            def _num(d, *keys):
                for k in keys:
                    v = d.get(k)
                    if v is not None:
                        return float(v)
                return 0.0
            orders_sum = _num(day, "ordersSumRub", "ordersSumRUB", "ordersSum", "orderSum", "sumRub", "buyoutsSumRub")
            orders_count = int(_num(day, "ordersCount", "orderCount", "orders"))
            stats[date]["sum"] += orders_sum
            stats[date]["count"] += orders_count
            key = str(product.get("nmId") or product.get("nmID") or product.get("vendorCode") or "?")
            pm = stats[date]["products"]
            if key not in pm:
                pm[key] = {"vendorCode": product.get("vendorCode") or "", "count": 0, "sum": 0}
            pm[key]["count"] += orders_count
            pm[key]["sum"] += orders_sum

    lines = []
    for date in [day1_date, day2_date]:
        s = stats[date]
        lines.append(f"💰 *{s['title']} ({s['label']})*")
        lines.append(f"Сумма заказов: {fmt(s['sum'])} ₽")
        lines.append("")
        lines.append(f"ТОП-5 {s['title']} ({s['label']}):")
        top5 = sorted(s["products"].values(), key=lambda x: (-x["count"], -x["sum"]))[:5]
        if top5:
            for i, p in enumerate(top5, 1):
                lines.append(f"{i}️⃣ {p['vendorCode'] or '—'} — {p['count']} шт ({fmt(p['sum'])} ₽)")
        else:
            lines.append("— Нет заказов")
        lines.append("")

    d1_sum = stats[day1_date]["sum"]
    d2_sum = stats[day2_date]["sum"]
    diff = d1_sum - d2_sum
    prefix = "+" if diff > 0 else ""
    lines.append(f"📊 *Разница:* {prefix}{fmt(diff)} ₽")

    header = f"📊 *WB ЗАКАЗЫ: Вчера ({day1_label}) / Позавчера ({day2_label})*\n"
    return header + "\n" + "\n".join(lines)

def format_stock(items: list) -> str:
    THRESHOLD = 50
    processed = []
    for item in items:
        art = item.get("vendorCode") or "Без артикула"
        warehouses = item.get("warehouses") or []
        physical = [w for w in warehouses
                    if w.get("warehouseName") != "Всего находится на складах"
                    and "В пути" not in str(w.get("warehouseName") or "")]
        transit = [w for w in warehouses
                   if "В пути" in str(w.get("warehouseName") or "")]
        qty = sum(int(w.get("quantity") or 0) for w in physical)
        in_way = sum(int(w.get("quantity") or 0) for w in transit)
        if qty > 0 or in_way > 0:
            processed.append({"art": art, "qty": qty, "in_way": in_way})

    processed.sort(key=lambda x: x["qty"])

    lines = ["📦 ОСТАТКИ НА СКЛАДЕ", ""]
    for x in processed:
        icon = "🔴" if x["qty"] < THRESHOLD else "✅"
        lines.append(f"{icon} {x['art']}: {x['qty']} шт (в пути: {x['in_way']})")

    if not processed:
        lines.append("Данные не найдены.")

    return "\n".join(lines)
