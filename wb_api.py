import asyncio
from datetime import datetime, timedelta, timezone
import httpx

MSK = timezone(timedelta(hours=3))

def msk_date(days_ago: int) -> str:
    return (datetime.now(MSK) - timedelta(days=days_ago)).strftime("%Y-%m-%d")

def msk_label(days_ago: int) -> str:
    return (datetime.now(MSK) - timedelta(days=days_ago)).strftime("%d.%m")

HEADERS = {}
ADS_HEADERS = {}

def init(api_key: str, ads_key: str = None):
    HEADERS["Authorization"] = api_key
    ADS_HEADERS["Authorization"] = ads_key or api_key

async def get_cards(client: httpx.AsyncClient) -> list[int]:
    resp = await client.post(
        "https://content-api.wildberries.ru/content/v2/get/cards/list",
        json={"settings": {"sort": {"ascending": False}, "cursor": {"limit": 100}, "filter": {"withPhoto": -1}}},
        headers=HEADERS,
    )
    resp.raise_for_status()
    data = resp.json()
    cards = data.get("cards") or data.get("data", {}).get("cards") or []
    nm_ids = list({int(c.get("nmID") or c.get("nmId") or 0) for c in cards if c.get("nmID") or c.get("nmId")})
    return nm_ids

async def get_sales_history(client: httpx.AsyncClient, nm_ids: list[int], date_start: str, date_end: str) -> list:
    results = []
    for i in range(0, len(nm_ids), 20):
        chunk = nm_ids[i:i+20]
        resp = await client.post(
            "https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products/history",
            json={
                "selectedPeriod": {"start": date_start, "end": date_end},
                "nmIds": chunk,
                "brandNames": [], "subjectIds": [], "tagIds": [],
                "skipDeletedNm": False,
                "orderBy": {"field": "ordersSumRub", "mode": "desc"},
                "limit": 20, "offset": 0,
            },
            headers=HEADERS,
        )
        resp.raise_for_status()
        body = resp.json()
        rows = body if isinstance(body, list) else body.get("data") or []
        if rows and not results:
            first = rows[0]
            hist = (first.get("history") or [{}])[0]
            print("[DEBUG] history day keys:", list(hist.keys()))
        results.extend(rows)
    return results

async def get_active_campaigns(client: httpx.AsyncClient) -> list:
    # Шаг 1: получить список кампаний сгруппированных по статусу
    r = await client.get(
        "https://advert-api.wildberries.ru/adv/v1/promotion/count",
        headers=ADS_HEADERS,
    )
    r.raise_for_status()
    data = r.json()

    # Извлечь только активные (status=9)
    groups = data.get("adverts") or []
    campaign_ids = []
    for group in groups:
        if group.get("status") == 9:
            for adv in (group.get("advert_list") or []):
                adv_id = adv.get("advertId") or adv.get("id")
                if adv_id:
                    campaign_ids.append(int(adv_id))

    if not campaign_ids:
        return []

    # Шаг 2: детали кампаний
    info_resp = await client.post(
        "https://advert-api.wildberries.ru/adv/v2/adverts",
        json={"ids": campaign_ids},
        headers=ADS_HEADERS,
    )
    info_list = []
    if info_resp.status_code == 200:
        raw = info_resp.json()
        info_list = raw if isinstance(raw, list) else (raw.get("data") or [])

    # Шаг 3: статистика за 7 дней (v3!)
    date_from = msk_date(6)
    date_to = msk_date(0)
    ids_str = ",".join(str(i) for i in campaign_ids)
    stats_resp = await client.get(
        f"https://advert-api.wildberries.ru/adv/v3/fullstats?ids={ids_str}&beginDate={date_from}&endDate={date_to}",
        headers=ADS_HEADERS,
    )
    stats_list = []
    if stats_resp.status_code == 200:
        raw = stats_resp.json()
        stats_list = raw if isinstance(raw, list) else (raw.get("data") or [])

    # Шаг 4: баланс каждой кампании
    budgets = {}
    for camp_id in campaign_ids:
        try:
            b_resp = await client.get(
                "https://advert-api.wildberries.ru/adv/v1/budget",
                params={"id": camp_id},
                headers=ADS_HEADERS,
            )
            if b_resp.status_code == 200:
                budgets[camp_id] = float(b_resp.json().get("total") or 0)
        except Exception:
            budgets[camp_id] = 0

    # Собрать карты
    info_by_id = {}
    for row in info_list:
        rid = int(row.get("id") or row.get("advertId") or 0)
        if rid:
            info_by_id[rid] = row

    stats_by_id = {}
    for row in stats_list:
        rid = int(row.get("advertId") or row.get("id") or 0)
        if not rid:
            continue
        views = clicks = orders = 0
        spend = 0.0
        views = int(row.get("views") or 0)
        clicks = int(row.get("clicks") or 0)
        orders = int(row.get("orders") or 0)
        spend = float(row.get("sum") or row.get("spend") or 0)
        if not (views or clicks or orders or spend):
            for d in (row.get("days") or []):
                views += int(d.get("views") or 0)
                clicks += int(d.get("clicks") or 0)
                orders += int(d.get("orders") or 0)
                spend += float(d.get("sum") or d.get("spend") or 0)
        stats_by_id[rid] = {"views": views, "clicks": clicks, "orders": orders, "spend": spend}

    # Собрать итог
    campaigns = []
    for camp_id in campaign_ids:
        info = info_by_id.get(camp_id) or {}
        stat = stats_by_id.get(camp_id) or {"views": 0, "clicks": 0, "orders": 0, "spend": 0.0}
        name = (info.get("name") or info.get("advert_name") or
                (info.get("settings") or {}).get("name") or f"Кампания {camp_id}")
        campaigns.append({
            "id": camp_id,
            "name": name,
            "balance": round(budgets.get(camp_id, 0)),
            "views": stat["views"],
            "clicks": stat["clicks"],
            "orders": stat["orders"],
            "spend": round(stat["spend"]),
        })

    # Только кампании с активностью, сортировка по затратам
    campaigns = [c for c in campaigns if c["views"] > 0 or c["orders"] > 0 or c["spend"] > 0]
    campaigns.sort(key=lambda x: -x["spend"])
    return campaigns

    # Для каждой кампании получить баланс и статистику
    result = []
    date_from = msk_date(7)
    date_to = msk_date(0)

    for camp in campaigns:
        camp_id = camp.get("advertId") or camp.get("id") or 0
        name = camp.get("name") or f"Кампания {camp_id}"

        # Баланс
        balance = 0
        try:
            b_resp = await client.get(
                "https://advert-api.wildberries.ru/adv/v1/budget",
                params={"id": camp_id},
                headers=HEADERS,
            )
            if b_resp.status_code == 200:
                b_data = b_resp.json()
                balance = float(b_data.get("total") or b_data.get("balance") or 0)
        except Exception:
            pass

        # Статистика за 7 дней
        views = orders = spend = ctr = 0
        try:
            s_resp = await client.post(
                "https://advert-api.wildberries.ru/adv/v2/fullstats",
                json=[{"id": camp_id, "intervals": [{"begin": date_from, "end": date_to}]}],
                headers=HEADERS,
            )
            if s_resp.status_code == 200:
                s_data = s_resp.json()
                stats = s_data[0] if isinstance(s_data, list) and s_data else {}
                days = stats.get("days") or []
                for day in days:
                    apps = day.get("apps") or []
                    for app in apps:
                        nm_list = app.get("nm") or []
                        for nm in nm_list:
                            views += int(nm.get("views") or 0)
                            orders += int(nm.get("orders") or 0)
                            spend += float(nm.get("sum") or 0)
                ctr = round(spend / views * 100, 2) if views > 0 else 0
        except Exception:
            pass

        result.append({
            "id": camp_id,
            "name": name,
            "balance": round(balance),
            "views": views,
            "orders": orders,
            "spend": round(spend),
            "ctr": ctr,
        })

    return result

async def get_stock_report(client: httpx.AsyncClient) -> list:
    # Создать задачу
    resp = await client.get(
        "https://seller-analytics-api.wildberries.ru/api/v1/warehouse_remains",
        params={"groupBySa": "true"},
        headers=HEADERS,
    )
    resp.raise_for_status()
    task_id = resp.json()["data"]["taskId"]

    # Ждать готовности — опрашиваем статус каждые 5 сек до 60 сек
    for _ in range(12):
        await asyncio.sleep(5)
        status_resp = await client.get(
            f"https://seller-analytics-api.wildberries.ru/api/v1/warehouse_remains/tasks/{task_id}/status",
            headers=HEADERS,
        )
        status_resp.raise_for_status()
        body = status_resp.json()
        status = (body.get("data") or {}).get("status") or body.get("status") or ""
        print(f"[DEBUG] stock status: {status}")
        if status in ("done", "complete", "completed", "finish", "finished"):
            break

    # Скачать отчёт
    dl_resp = await client.get(
        f"https://seller-analytics-api.wildberries.ru/api/v1/warehouse_remains/tasks/{task_id}/download",
        headers=HEADERS,
    )
    dl_resp.raise_for_status()
    data = dl_resp.json()
    return data if isinstance(data, list) else data.get("data") or []
