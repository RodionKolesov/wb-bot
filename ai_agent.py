import httpx

SYSTEM_PROMPT = """Ты опытный коммерческий директор и аналитик Wildberries с 10-летним опытом.
У тебя есть актуальные данные по магазину: продажи, реклама, воронка карточек, финансы.

Бенчмарки WB которые ты используешь при анализе:
- CTR рекламы: отлично >5%, норма 3-5%, плохо <2% → нужно менять креатив/ставку
- Конверсия карточки (просмотры→корзина): отлично >8%, норма 4-8%, плохо <3% → нужно улучшить фото/заголовок/цену
- Конверсия корзина→заказ: норма >40%, плохо <25% → проблема с описанием/ценой
- Выкуп: отлично >85%, норма 70-85%, плохо <60% → проблема с качеством/описанием товара
- Маржа: хорошо >40%, норма 25-40%, плохо <20%
- ДРР (доля рекламных расходов): норма <15% от выручки, плохо >25%

При анализе:
1. Называй конкретные товары и кампании с проблемами
2. Сравнивай цифры с бенчмарками и говори плохо это или хорошо
3. Давай конкретные действия: "у товара X CTR 1.2% — это плохо, смени главное фото и заголовок"
4. Приоритизируй: сначала самое важное
5. Отвечай кратко и по делу. Используй числа. Пиши по-русски."""

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

_api_key: str = ""
_histories: dict[int, list] = {}
_contexts: dict[int, str] = {}

def init_groq(api_key: str):
    global _api_key
    _api_key = api_key
    print(f"[AI] Groq инициализирован, модель: {MODEL}")

def set_context(chat_id: int, context: str):
    _contexts[chat_id] = context
    _histories[chat_id] = []

def clear_history(chat_id: int):
    _histories.pop(chat_id, None)
    _contexts.pop(chat_id, None)

async def generate_feedback_reply(product: str, rating: int, review: str) -> str:
    """Одиночный запрос к Groq — генерация ответа на отзыв без сохранения в историю."""
    if not _api_key:
        return "❌ GROQ_API_KEY не настроен."
    prompt = (
        f"Ты — менеджер WB-магазина. Напиши вежливый профессиональный ответ на отзыв покупателя. "
        f"2–3 предложения, только русский язык, без вступлений и подписей.\n\n"
        f"Товар: {product}\nОценка: {rating}/5\nОтзыв: {review}"
    )
    messages = [
        {"role": "system", "content": "Ты менеджер по работе с клиентами интернет-магазина на Wildberries."},
        {"role": "user",   "content": prompt},
    ]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {_api_key}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": messages, "max_tokens": 300, "temperature": 0.8},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

async def ask(chat_id: int, question: str) -> str:
    if not _api_key:
        return "❌ GROQ_API_KEY не настроен. Добавь его в переменные Railway."

    history = _histories.get(chat_id, [])
    context = _contexts.get(chat_id, "")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if context:
        messages.append({
            "role": "user",
            "content": f"Вот актуальные данные магазина:\n\n{context}"
        })
        messages.append({
            "role": "assistant",
            "content": "Данные получил, готов анализировать."
        })

    messages.extend(history)

    if question:
        messages.append({"role": "user", "content": question})
    else:
        messages.append({"role": "user", "content": "Проанализируй данные и дай главные рекомендации."})

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {_api_key}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": messages, "max_tokens": 1024, "temperature": 0.7},
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]

    history.append({"role": "user", "content": question or "Анализ данных"})
    history.append({"role": "assistant", "content": text})
    _histories[chat_id] = history[-20:]

    return text
