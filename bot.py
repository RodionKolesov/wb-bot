import asyncio
import os
import httpx
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

import wb_api
from formatters import format_sales, format_stock

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WB_API_KEY = os.getenv("WB_API_KEY")

wb_api.init(WB_API_KEY)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

MENU_KB = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="📊 Продажи", callback_data="sales"),
        InlineKeyboardButton(text="📦 Склад", callback_data="stock"),
    ]
])

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Привет! Выбери отчет.", reply_markup=MENU_KB)

@dp.callback_query(F.data == "sales")
async def cb_sales(call: CallbackQuery):
    await call.answer()
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

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
