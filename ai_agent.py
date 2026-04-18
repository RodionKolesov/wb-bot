import google.generativeai as genai

SYSTEM_PROMPT = """Ты опытный коммерческий директор и аналитик Wildberries.
У тебя есть актуальные данные по магазину продавца (продажи, склад, реклама, финансы).
Анализируй цифры, находи проблемы, давай конкретные практические советы.
Отвечай кратко и по делу. Используй числа из данных. Пиши по-русски."""

# История диалога per chat_id: {chat_id: [{"role": "user/model", "parts": ["..."]}]}
_histories: dict[int, list] = {}
# Контекст WB данных per chat_id
_contexts: dict[int, str] = {}

model = None

def init_gemini(api_key: str):
    global model
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT,
    )

def set_context(chat_id: int, context: str):
    _contexts[chat_id] = context
    _histories[chat_id] = []

def clear_history(chat_id: int):
    _histories.pop(chat_id, None)
    _contexts.pop(chat_id, None)

async def ask(chat_id: int, question: str) -> str:
    if model is None:
        return "❌ Gemini API не настроен. Добавь GEMINI_API_KEY в переменные Railway."

    history = _histories.get(chat_id, [])
    context = _contexts.get(chat_id, "")

    # Первый вопрос — добавляем контекст WB
    if not history and context:
        full_question = f"Вот актуальные данные магазина:\n\n{context}\n\nТвой первый анализ и главные рекомендации:"
    else:
        full_question = question

    chat = model.start_chat(history=history)
    response = await chat.send_message_async(full_question)
    text = response.text

    # Сохранить историю
    history.append({"role": "user", "parts": [full_question]})
    history.append({"role": "model", "parts": [text]})
    _histories[chat_id] = history[-20:]  # последние 10 пар

    return text
