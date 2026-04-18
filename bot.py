import asyncio
import os
import httpx
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

import wb_api
from formatters import format_sales, format_stock, format_campaigns

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WB_API_KEY = os.getenv("WB_API_KEY")

wb_api.init(WB_API_KEY)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Храним chat_id всех пользователей для уведомлений
user_chat_ids: set[int] = set()

MENU_KB = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="📊 Продажи", callback_data="sales"),
        InlineKeyboardButton(text="📦 Склад", callback_data="stock"),
        InlineKeyboardButton(text="📢 Кампании", callback_data="campaigns"),
    ]
])

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_chat_ids.add(message.chat.id)
    await message.answer("Привет! Выбери отчет.", reply_markup=MENU_KB)

@dp.callback_query(F.data == "sales")
async def cb_sales(call: CallbackQuery):
    await call.answer()
    user_chat_ids.add(call.message.chat.id)
    await call.message.answer("⏳ Загружаю данные по продажам...")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            nm_ids = await wb_api.get_cards(client)
            date1 = wb_api.msk_date(1)
            date2 = wb_api.msk_date(2)
            rows = await wb_api.get_sales_history(client, nm_ids, date2, date1)
        text = format_sales(rows)
        await call.message.answer(text, parse_mode="Markdown", reply_markup=MENU_KB)
    except Exception as e:
        await call.message.answer(f"❌ Ошибка: {e}", reply_markup=MENU_KB)

@dp.callback_query(F.data == "stock")
async def cb_stock(call: CallbackQuery):
    await call.answer()
    user_chat_ids.add(call.message.chat.id)
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

@dp.callback_query(F.data == "campaigns")
async def cb_campaigns(call: CallbackQuery):
    await call.answer()
    user_chat_ids.add(call.message.chat.id)
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

async def check_budgets_loop():
    """Проверяет баланс кампаний каждые 30 минут и шлёт уведомление если < 100 ₽"""
    await asyncio.sleep(60)  # первая проверка через минуту после старта
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
        await asyncio.sleep(30 * 60)  # каждые 30 минут

async def main():
    asyncio.create_task(check_budgets_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
