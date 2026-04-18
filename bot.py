import asyncio
import os
import httpx
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

import wb_api
from formatters import (
    format_sales, format_stock, format_campaigns,
    format_finance, format_funnel,
    format_ratings, format_abc,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WB_API_KEY = os.getenv("WB_API_KEY")
WB_ADS_KEY = os.getenv("WB_ADS_KEY") or WB_API_KEY

wb_api.init(WB_API_KEY, WB_ADS_KEY)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_chat_ids: set[int] = set()

MENU_KB = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="📊 Продажи", callback_data="sales"),
        InlineKeyboardButton(text="📦 Склад", callback_data="stock"),
        InlineKeyboardButton(text="📢 Кампании", callback_data="campaigns"),
    ],
    [
        InlineKeyboardButton(text="💰 Финансы", callback_data="finance"),
        InlineKeyboardButton(text="📈 Воронка", callback_data="funnel"),
    ],
    [
        InlineKeyboardButton(text="⭐ Рейтинг", callback_data="ratings"),
        InlineKeyboardButton(text="🏆 ABC", callback_data="abc"),
    ],
])

def register_chat(chat_id: int):
    user_chat_ids.add(chat_id)

@dp.message(CommandStart())
async def cmd_start(message: Message):
    register_chat(message.chat.id)
    await message.answer("Привет! Выбери отчет.", reply_markup=MENU_KB)

# ─── ПРОДАЖИ ─────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "sales")
async def cb_sales(call: CallbackQuery):
    await call.answer()
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
    register_chat(call.message.chat.id)
    msg = await call.message.answer("⏳ Загружаю финансовый отчёт...")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            rows = await wb_api.get_finance_report(client)
        text = format_finance(rows)
        await msg.delete()
        await call.message.answer(text, parse_mode="Markdown", reply_markup=MENU_KB)
    except Exception as e:
        await msg.delete()
        await call.message.answer(f"❌ Ошибка: {e}", reply_markup=MENU_KB)

# ─── ВОРОНКА ─────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "funnel")
async def cb_funnel(call: CallbackQuery):
    await call.answer()
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
