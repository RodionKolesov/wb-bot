import httpx

SYSTEM_PROMPT = """Ты опытный коммерческий директор и аналитик Wildberries.
У тебя есть актуальные данные по магазину продавца (продажи, склад, реклама, финансы).
Анализируй цифры, находи проблемы, давай конкретные практические советы.
Отвечай кратко и по делу. Используй числа из данных. Пиши по-русски."""

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
