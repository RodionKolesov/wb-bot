import asyncio
import os
import httpx
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

import wb_api
import ai_agent
from formatters import (
    format_sales, format_stock, format_campaigns,
    format_income_weeks, format_funnel,
    format_ratings, format_abc,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WB_API_KEY = os.getenv("WB_API_KEY")
WB_ADS_KEY = os.getenv("WB_ADS_KEY") or WB_API_KEY
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

wb_api.init(WB_API_KEY, WB_ADS_KEY)
if GROQ_API_KEY:
    ai_agent.init_groq(GROQ_API_KEY)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_chat_ids: set[int] = set()
ai_mode: set[int] = set()  # пользователи в режиме AI-диалога

MENU_KB = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="📊 Продажи", callback_data="sales"),
        InlineKeyboardButton(text="📦 Склад", callback_data="stock"),
        InlineKeyboardButton(text="📢 Кампании", callback_data="campaigns"),
    ],
    [
        InlineKeyboardButton(text="💵 Приходы", callback_data="finance"),
        InlineKeyboardButton(text="📈 Воронка", callback_data="funnel"),
    ],
    [
        InlineKeyboardButton(text="⭐ Рейтинг", callback_data="ratings"),
        InlineKeyboardButton(text="🏆 ABC", callback_data="abc"),
    ],
    [
        InlineKeyboardButton(text="🤖 AI Директор", callback_data="ai"),
    ],
])

async def refresh_kb(call: CallbackQuery):
    try:
        await call.message.edit_reply_markup(reply_markup=MENU_KB)
    except Exception:
        pass

def register_chat(chat_id: int, clear_ai: bool = True):
    user_chat_ids.add(chat_id)
    if clear_ai:
        ai_mode.discard(chat_id)

@dp.message(CommandStart())
async def cmd_start(message: Message):
    register_chat(message.chat.id)
    await message.answer("Привет! Выбери отчет.", reply_markup=MENU_KB)

# ─── ПРОДАЖИ ─────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "sales")
async def cb_sales(call: CallbackQuery):
    await call.answer()
    await refresh_kb(call)
    register_chat(call.message.chat.id)
    msg = await call.message.answer("⏳ Загружаю данные по продажам...")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            nm_ids = await wb_api.get_cards(client)
            rows = await wb_api.get_sales_history(client, nm_ids, wb_api.msk_date(2), wb_api.msk_date(1))
        text = format_sales(rows)
        await msg.delete()
        await call.message.answer(text, parse_mode="Markdown", reply_markup=MENU_KB)
    except Exception as e:
        await msg.delete()
        await call.message.answer(f"❌ Ошибка: {e}", reply_markup=MENU_KB)

# ─── СКЛАД ────────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "stock")
async def cb_stock(call: CallbackQuery):
    await call.answer()
    await refresh_kb(call)
    register_chat(call.message.chat.id)
    msg = await call.message.answer("⏳ Формирую отчёт по складу (~30 сек)...")
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            items = await wb_api.get_stock_report(client)
        text = format_stock(items)
        await msg.delete()
        await call.message.answer(text, reply_markup=MENU_KB)
    except Exception as e:
        await msg.delete()
        await call.message.answer(f"❌ Ошибка: {e}", reply_markup=MENU_KB)

# ─── КАМПАНИИ ────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "campaigns")
async def cb_campaigns(call: CallbackQuery):
    await call.answer()
    await refresh_kb(call)
    register_chat(call.message.chat.id)
    msg = await call.message.answer("⏳ Загружаю кампании...")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            campaigns = await wb_api.get_active_campaigns(client)
        text = format_campaigns(campaigns)
        await msg.delete()
        await call.message.answer(text, parse_mode="Markdown", reply_markup=MENU_KB)
    except Exception as e:
        await msg.delete()
        await call.message.answer(f"❌ Ошибка: {e}", reply_markup=MENU_KB)

# ─── ФИНАНСЫ ─────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "finance")
async def cb_finance(call: CallbackQuery):
    await call.answer()
    await refresh_kb(call)
    register_chat(call.message.chat.id)
    msg = await call.message.answer("⏳ Загружаю приходы за 4 недели...")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            rows = await wb_api.get_finance_report(client)
        text = format_income_weeks(rows)
        await msg.delete()
        await call.message.answer(text, parse_mode="Markdown", reply_markup=MENU_KB)
    except Exception as e:
        await msg.delete()
        await call.message.answer(f"❌ Ошибка: {e}", reply_markup=MENU_KB)

# ─── ВОРОНКА ─────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "funnel")
async def cb_funnel(call: CallbackQuery):
    await call.answer()
    await refresh_kb(call)
    register_chat(call.message.chat.id)
    msg = await call.message.answer("⏳ Загружаю воронку продаж...")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            nm_ids = await wb_api.get_cards(client)
            history = await wb_api.get_funnel(client, nm_ids)
        text = format_funnel(history)
        await msg.delete()
        await call.message.answer(text, parse_mode="Markdown", reply_markup=MENU_KB)
    except Exception as e:
        await msg.delete()
        await call.message.answer(f"❌ Ошибка: {e}", reply_markup=MENU_KB)

# ─── РЕЙТИНГ ─────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "ratings")
async def cb_ratings(call: CallbackQuery):
    await call.answer()
    await refresh_kb(call)
    register_chat(call.message.chat.id)
    msg = await call.message.answer("⏳ Загружаю отзывы...")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            data = await wb_api.get_ratings(client)
        text = format_ratings(data)
        await msg.delete()
        await call.message.answer(text, parse_mode="Markdown", reply_markup=MENU_KB)
    except Exception as e:
        await msg.delete()
        await call.message.answer(f"❌ Ошибка: {e}", reply_markup=MENU_KB)

# ─── ABC ─────────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "abc")
async def cb_abc(call: CallbackQuery):
    await call.answer()
    await refresh_kb(call)
    register_chat(call.message.chat.id)
    msg = await call.message.answer("⏳ Считаю ABC-анализ за 30 дней...")
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            nm_ids = await wb_api.get_cards(client)
            products = await wb_api.get_abc(client, nm_ids)
        text = format_abc(products)
        await msg.delete()
        await call.message.answer(text, parse_mode="Markdown", reply_markup=MENU_KB)
    except Exception as e:
        await msg.delete()
        await call.message.answer(f"❌ Ошибка: {e}", reply_markup=MENU_KB)

# ─── AI ДИРЕКТОР ─────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "ai")
async def cb_ai(call: CallbackQuery):
    await call.answer()
    await refresh_kb(call)
    chat_id = call.message.chat.id
    register_chat(chat_id, clear_ai=False)
    ai_mode.add(chat_id)
    msg = await call.message.answer("🤖 Собираю данные магазина для анализа...")
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            summary = await wb_api.get_ai_summary(client)
        ai_agent.set_context(chat_id, summary)
        await msg.edit_text("🤖 Анализирую данные...")
        answer = await ai_agent.ask(chat_id, "")
        await msg.delete()
        await call.message.answer(
            f"🤖 *AI Директор*\n\n{answer}\n\n_Задай любой вопрос текстом. Для выхода нажми другую кнопку._",
            parse_mode="Markdown",
            reply_markup=MENU_KB,
        )
    except Exception as e:
        await msg.delete()
        ai_mode.discard(chat_id)
        await call.message.answer(f"❌ Ошибка: {e}", reply_markup=MENU_KB)

@dp.message(F.text & F.text.startswith("/debug_finance"))
async def cmd_debug_finance(message: Message):
    msg = await message.answer("⏳ Читаю данные API...")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            rows = await wb_api.get_finance_report(client)
        # Группируем по realizationreport_id
        from collections import defaultdict
        reports = defaultdict(lambda: {"ppvz_for_pay":0,"delivery_rub":0,"storage_fee":0,"acceptance":0,"penalty":0,"ppvz_reward":0,"rr_dt_min":"","rr_dt_max":""})
        for r in rows:
            rid = r.get("realizationreport_id") or 0
            if not rid:
                continue
            reports[rid]["ppvz_for_pay"] += float(r.get("ppvz_for_pay") or 0)
            reports[rid]["delivery_rub"] += float(r.get("delivery_rub") or 0)
            reports[rid]["storage_fee"] += float(r.get("storage_fee") or 0)
            reports[rid]["acceptance"] += float(r.get("acceptance") or 0)
            reports[rid]["penalty"] += float(r.get("penalty") or 0)
            reports[rid]["ppvz_reward"] += float(r.get("ppvz_reward") or 0)
            dt = str(r.get("rr_dt") or "")[:10]
            if dt:
                if not reports[rid]["rr_dt_min"] or dt < reports[rid]["rr_dt_min"]:
                    reports[rid]["rr_dt_min"] = dt
                if dt > reports[rid]["rr_dt_max"]:
                    reports[rid]["rr_dt_max"] = dt
        lines = [f"📊 Отчётов: {len(reports)}", ""]
        for rid, d in sorted(reports.items())[-6:]:
            net = d["ppvz_for_pay"] - d["delivery_rub"] - d["storage_fee"] - d["acceptance"] - d["penalty"] + d["ppvz_reward"]
            lines.append(f"ID {rid} ({d['rr_dt_min']}..{d['rr_dt_max']})")
            lines.append(f"  pay={int(d['ppvz_for_pay'])} del={int(d['delivery_rub'])} sto={int(d['storage_fee'])} acc={int(d['acceptance'])} pen={int(d['penalty'])} rew={int(d['ppvz_reward'])}")
            lines.append(f"  ➜ net={int(net)}")
        await msg.delete()
        await message.answer("\n".join(lines))
    except Exception as e:
        await msg.delete()
        await message.answer(f"❌ {e}")

@dp.message(F.text)
async def handle_text(message: Message):
    chat_id = message.chat.id
    if chat_id not in ai_mode:
        return
    msg = await message.answer("🤖 Думаю...")
    try:
        answer = await ai_agent.ask(chat_id, message.text)
        await msg.delete()
        await message.answer(
            f"🤖 {answer}\n\n_Продолжай задавать вопросы или нажми кнопку меню._",
            parse_mode="Markdown",
            reply_markup=MENU_KB,
        )
    except Exception as e:
        await msg.delete()
        await message.answer(f"❌ Ошибка AI: {e}", reply_markup=MENU_KB)

# ─── ФОНОВАЯ ПРОВЕРКА БЮДЖЕТОВ ───────────────────────────────────────────────

async def check_budgets_loop():
    await asyncio.sleep(60)
    while True:
        try:
            if user_chat_ids:
                async with httpx.AsyncClient(timeout=60) as client:
                    campaigns = await wb_api.get_active_campaigns(client)
                low = [c for c in campaigns if c.get("balance", 0) < 100]
                if low:
                    lines = ["⚠️ *НИЗКИЙ БАЛАНС КАМПАНИИ*", ""]
                    for c in low:
                        lines.append(f"🔴 {c['name']} — остаток *{c['balance']} ₽*")
                    lines.append("\nПополни рекламный кабинет WB!")
                    text = "\n".join(lines)
                    for chat_id in user_chat_ids:
                        try:
                            await bot.send_message(chat_id, text, parse_mode="Markdown")
                        except Exception:
                            pass
        except Exception as e:
            print(f"[budget check error] {e}")
        await asyncio.sleep(30 * 60)

async def main():
    asyncio.create_task(check_budgets_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
