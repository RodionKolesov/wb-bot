import asyncio
from datetime import datetime, timedelta, timezone
import httpx

MSK = timezone(timedelta(hours=3))

def msk_date(days_ago: int) -> str:
    return (datetime.now(MSK) - timedelta(days=days_ago)).strftime("%Y-%m-%d")

def msk_label(days_ago: int) -> str:
    return (datetime.now(MSK) - timedelta(days=days_ago)).strftime("%d.%m")

HEADERS = {}

def init(api_key: str):
    HEADERS["Authorization"] = api_key

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
    # Получить активные кампании (status=9)
    resp = await client.get(
        "https://advert-api.wildberries.ru/adv/v1/promotion/adverts",
        params={"status": 9, "limit": 50, "offset": 0},
        headers=HEADERS,
    )
    resp.raise_for_status()
    data = resp.json()
    campaigns = data if isinstance(data, list) else (data.get("adverts") or data.get("data") or [])

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
