from wb_api import msk_date, msk_label

def fmt(v) -> str:
    return f"{int(v):,}".replace(",", "\u202f")

def fmtf(v, dec=1) -> str:
    return f"{float(v):.{dec}f}"

# ─── ПРОДАЖИ ─────────────────────────────────────────────────────────────────

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
            orders_sum = _num(day, "ordersSumRub", "ordersSumRUB", "ordersSum", "orderSum", "sumRub")
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

# ─── СКЛАД ────────────────────────────────────────────────────────────────────

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

# ─── КАМПАНИИ ────────────────────────────────────────────────────────────────

def format_campaigns(campaigns: list) -> str:
    if not campaigns:
        return "📢 Активных кампаний со статистикой нет."
    lines = ["📢 *КАМПАНИИ WB*", ""]
    low_balance = []
    for c in campaigns:
        ctr = round(c["clicks"] / c["views"] * 100, 2) if c["views"] > 0 else 0
        bal_icon = "🔴" if c["balance"] < 100 else "💰"
        lines.append(f"*{c['name']}*")
        lines.append(f"{bal_icon} Баланс: {fmt(c['balance'])} ₽")
        lines.append(f"💸 Затраты: {fmt(c['spend'])} ₽")
        lines.append(f"👁 Показы: {fmt(c['views'])} | CTR: {ctr}%")
        lines.append(f"🛒 Заказы: {c['orders']}")
        lines.append("")
        if c["balance"] < 100:
            low_balance.append(c["name"])
    if low_balance:
        lines.append("⚠️ *Пополни баланс:*")
        for name in low_balance:
            lines.append(f"— {name}")
    return "\n".join(lines)

# ─── ФИНАНСЫ ─────────────────────────────────────────────────────────────────

def format_finance(rows: list) -> str:
    sales_sum = commission = logistics = storage = penalties = to_pay = correction = acceptance = 0

    for r in rows:
        to_pay      += float(r.get("ppvz_for_pay") or 0)
        commission  += float(r.get("ppvz_vw") or 0)       # приходит < 0 из API
        logistics   += float(r.get("delivery_rub") or 0)  # приходит > 0 из API (расход)
        storage     += float(r.get("storage_fee") or 0)   # приходит > 0 из API (расход)
        penalties   += float(r.get("penalty") or 0)
        correction  += float(r.get("ppvz_reward") or 0)
        acceptance  += float(r.get("acceptance") or 0)    # приходит > 0 из API (расход)
        doc = str(r.get("doc_type_name") or r.get("supplier_oper_name") or "")
        if "продажа" in doc.lower():
            sales_sum += float(r.get("retail_price_withdisc_rub") or 0)

    # комиссия уже отрицательная → abs; остальные расходы положительные → as-is
    expenses = abs(commission) + logistics + storage + abs(penalties) + abs(acceptance)
    label = msk_label(7)
    today = msk_label(1)

    corr_str = f"+{fmt(correction)}" if correction >= 0 else f"-{fmt(abs(correction))}"

    lines = [
        f"💰 *ФИНАНСЫ WB* ({label} — {today})",
        "",
        f"📈 Приход: {fmt(sales_sum)} ₽",
        f"📉 Расход: -{fmt(expenses)} ₽",
        "",
        "Детализация:",
        f"💵 Продажи: {fmt(sales_sum)} ₽",
        f"🏦 Комиссия WB: -{fmt(abs(commission))} ₽",
        f"🚚 Логистика: -{fmt(logistics)} ₽",
        f"🏪 Хранение: -{fmt(storage)} ₽",
        f"🔄 Корректировка: {corr_str} ₽",
        f"⚠️ Штрафы: -{fmt(abs(penalties))} ₽",
        f"📥 Операции при приёмке: -{fmt(abs(acceptance))} ₽",
        "",
        f"✅ *Итого к получению: {fmt(to_pay)} ₽*",
    ]
    return "\n".join(lines)

# ─── ВОЗВРАТЫ ────────────────────────────────────────────────────────────────

def format_returns(rows: list) -> str:
    returns_by_art = {}
    for r in rows:
        doc = str(r.get("doc_type_name") or r.get("supplier_oper_name") or "")
        if "возврат" not in doc.lower():
            continue
        art = r.get("sa_name") or r.get("supplierArticle") or "—"
        retail = float(r.get("retail_price_withdisc_rub") or 0)
        qty = int(r.get("quantity") or 1)
        if art not in returns_by_art:
            returns_by_art[art] = {"count": 0, "sum": 0}
        returns_by_art[art]["count"] += qty
        returns_by_art[art]["sum"] += abs(retail)

    if not returns_by_art:
        return "↩️ *ВОЗВРАТЫ*\n\nВозвратов за 7 дней нет."

    items = sorted(returns_by_art.items(), key=lambda x: -x[1]["count"])
    label = msk_label(7)
    today = msk_label(1)
    total_count = sum(v["count"] for v in returns_by_art.values())
    total_sum = sum(v["sum"] for v in returns_by_art.values())

    lines = [
        f"↩️ *ВОЗВРАТЫ WB* ({label} — {today})",
        f"Всего: {total_count} шт на {fmt(total_sum)} ₽",
        "",
    ]
    for art, data in items[:10]:
        lines.append(f"🔴 {art}: {data['count']} шт ({fmt(data['sum'])} ₽)")

    return "\n".join(lines)

# ─── ВОРОНКА ─────────────────────────────────────────────────────────────────

def format_funnel(history: list) -> str:
    if not history:
        return "📈 *ВОРОНКА*\n\nДанные не найдены."

    label = msk_label(7)
    today = msk_label(1)
    lines = [f"📈 *ВОРОНКА ПРОДАЖ* ({label} — {today})", ""]

    total_opens = total_cart = total_orders = total_buyouts = 0
    rows = []
    for item in history:
        opens = int(item.get("openCardCount") or 0)
        cart = int(item.get("addToCartCount") or 0)
        orders = int(item.get("ordersCount") or 0)
        buyouts = int(item.get("buyoutsCount") or 0)
        vendor = item.get("vendorCode") or str(item.get("nmID") or "?")
        total_opens += opens
        total_cart += cart
        total_orders += orders
        total_buyouts += buyouts
        if opens > 0:
            rows.append({"vendor": vendor, "opens": opens, "cart": cart, "orders": orders, "buyouts": buyouts})

    rows.sort(key=lambda x: -x["orders"])

    # Итого
    ctr_cart = round(total_cart / total_opens * 100, 1) if total_opens else 0
    ctr_order = round(total_orders / total_cart * 100, 1) if total_cart else 0
    ctr_buyout = round(total_buyouts / total_orders * 100, 1) if total_orders else 0

    lines.append(f"👁 Просмотры: {fmt(total_opens)}")
    lines.append(f"🛒 В корзину: {fmt(total_cart)} ({ctr_cart}%)")
    lines.append(f"📦 Заказы: {fmt(total_orders)} ({ctr_order}% из корзины)")
    lines.append(f"✅ Выкупы: {fmt(total_buyouts)} ({ctr_buyout}% из заказов)")
    lines.append("")
    lines.append("*По товарам:*")

    for r in rows[:8]:
        c2o = round(r["orders"] / r["cart"] * 100, 1) if r["cart"] else 0
        lines.append(f"• {r['vendor']}: {r['opens']}→{r['cart']}→{r['orders']}→{r['buyouts']} | C→O: {c2o}%")

    return "\n".join(lines)

# ─── РЕЙТИНГ ─────────────────────────────────────────────────────────────────

def format_ratings(data: dict) -> str:
    unanswered = data.get("unanswered", 0)
    feedbacks = data.get("feedbacks") or []

    lines = ["⭐ *ОТЗЫВЫ WB*", ""]
    lines.append(f"💬 Без ответа: *{unanswered}* отзывов")
    lines.append("")

    if feedbacks:
        ratings = [f.get("productValuation") or 0 for f in feedbacks if f.get("productValuation")]
        if ratings:
            avg = round(sum(ratings) / len(ratings), 1)
            lines.append(f"Средний рейтинг (последние {len(ratings)}): *{avg}* ⭐")
            lines.append("")

        lines.append("*Последние без ответа:*")
        for f in feedbacks[:5]:
            rating = f.get("productValuation") or "?"
            text = (f.get("text") or "").strip()[:80]
            product = f.get("subjectName") or f.get("productName") or "—"
            stars = "⭐" * int(rating) if isinstance(rating, int) else ""
            lines.append(f"{stars} *{product}*")
            if text:
                lines.append(f"_{text}_")
            lines.append("")
    else:
        lines.append("Непрочитанных отзывов нет!")

    return "\n".join(lines)

# ─── ABC-АНАЛИЗ ───────────────────────────────────────────────────────────────

def format_abc(products: list) -> str:
    if not products:
        return "🏆 *ABC-АНАЛИЗ*\n\nДанных нет."

    label = msk_label(30)
    today = msk_label(1)
    lines = [f"🏆 *ABC-АНАЛИЗ* ({label} — {today})", ""]

    by_class = {"A": [], "B": [], "C": []}
    for p in products:
        by_class[p["class"]].append(p)

    total = sum(p["sum"] for p in products)

    for cls, emoji, desc in [("A", "🟢", "80% выручки — фокус"), ("B", "🟡", "15% — поддержка"), ("C", "🔴", "5% — пересмотр")]:
        items = by_class[cls]
        if not items:
            continue
        cls_sum = sum(p["sum"] for p in items)
        pct = round(cls_sum / total * 100, 1) if total else 0
        lines.append(f"{emoji} *Класс {cls}* — {len(items)} товаров, {pct}% выручки ({desc})")
        for p in items[:5]:
            lines.append(f"  • {p['vendorCode']}: {fmt(p['sum'])} ₽ ({p['count']} шт)")
        if len(items) > 5:
            lines.append(f"  ...ещё {len(items)-5}")
        lines.append("")

    return "\n".join(lines)
