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

async def get_stock_report(client: httpx.AsyncClient) -> list:
    # Создать задачу
    resp = await client.get(
        "https://seller-analytics-api.wildberries.ru/api/v1/warehouse_remains",
        params={"groupBySa": "true"},
        headers=HEADERS,
    )
    resp.raise_for_status()
    task_id = resp.json()["data"]["taskId"]

    # Ждать готовности
    for _ in range(12):
        await asyncio.sleep(10)
        status_resp = await client.get(
            f"https://seller-analytics-api.wildberries.ru/api/v1/warehouse_remains/tasks/{task_id}/status",
            headers=HEADERS,
        )
        status_resp.raise_for_status()
        status = status_resp.json().get("data", {}).get("status") or status_resp.json().get("status", "")
        if status in ("done", "complete", "completed"):
            break

    # Скачать отчёт
    dl_resp = await client.get(
        f"https://seller-analytics-api.wildberries.ru/api/v1/warehouse_remains/tasks/{task_id}/download",
        headers=HEADERS,
    )
    dl_resp.raise_for_status()
    data = dl_resp.json()
    return data if isinstance(data, list) else data.get("data") or []
