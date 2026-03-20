"""
Общие команды бота: /start, /help, /mode, /voice_on, /voice_off.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db.storage import set_user_mode
from config import BUSINESS_MODE_USERS

# Главное меню (ReplyKeyboard) — первая кнопка «Задачи»
from bot.keyboards.main_kb import main_menu_kb
# Onboarding коуча — для показа при первом /start
from db.session import get_async_session
from db import coaching_storage as cs
from bot.keyboards.coaching_keyboards import onboarding_kb

router = Router()


@router.message(Command("start"))
async def start_handler(message: Message, user_db: dict | None = None):
    """Приветствие и показ главного меню с первой кнопкой «Задачи»."""
    mode = user_db.get("mode", "personal") if user_db else "personal"
    mode_str = "🏢 Бизнес" if mode == "business" else "👤 Личный"
    text = (
        "Привет! Я мультиагентный ассистент.\n\n"
        f"Текущий режим: {mode_str}\n\n"
        "Нажмите «Задачи» для управления делами или «🎯 Коучинг» для целей и привычек.\n"
        "/help — список всех команд"
    )
    # Показываем ReplyKeyboard главного меню
    await message.answer(text, reply_markup=main_menu_kb())

    # При первом запуске предлагаем онбординг коуча
    user_id = message.from_user.id
    try:
        async with get_async_session() as session:
            onboarding = await cs.get_or_create_onboarding(session, user_id)
            await session.commit()
        if not onboarding.bot_onboarding_done:
            await message.answer(
                "\U0001f44b *Кстати, у меня есть AI-коуч!*\n\n"
                "Помогает ставить цели, формировать привычки и двигаться к результату.\n\n"
                "_Хочешь попробовать? Это займёт 2 минуты_ \U0001f680",
                reply_markup=onboarding_kb(),
                parse_mode="Markdown",
            )
    except Exception:
        pass  # Не блокируем /start если coaching DB недоступна


@router.message(Command("help"))
async def help_handler(message: Message):
    """Справка по всем доступным командам и модулям."""
    await message.answer(
        "🤖 *AI-ассистент — доступные модули:*\n\n"

        "✅ *Задачи*\n"
        "— добавь задачу написать отчёт до пятницы\n"
        "— покажи мои задачи\n"
        "— выполнил задачу 3\n\n"

        "📅 *Календарь*\n"
        "— создай встречу завтра в 15:00 с названием Планёрка\n"
        "— что у меня в календаре завтра?\n"
        "— перенеси встречу Планёрка на пятницу в 18:00\n\n"

        "🥗 *Питание*\n"
        "— записал завтрак: овсянка 300г\n"
        "— покажи калории за сегодня\n"
        "— что мне поесть на обед?\n\n"

        "💪 *Фитнес*\n"
        "— записал тренировку: бег 5 км\n"
        "— покажи мои тренировки за неделю\n"
        "— составь план тренировок\n\n"

        "🎯 *Коучинг*\n"
        "— поставь цель: выучить английский за 3 месяца\n"
        "— добавь привычку: читать 30 минут в день\n"
        "— покажи мой прогресс\n"
        "— /reset\\_coach — сбросить профиль коуча\n\n"

        "🏢 *Бизнес* (режим /mode business)\n"
        "— добавь контакт Иван Иванов, телефон +79001234567\n"
        "— покажи мои сделки\n"
        "— новая сделка: проект сайт на 150000 руб\n\n"

        "⚙️ *Настройки*\n"
        "— /mode personal — личный режим\n"
        "— /mode business — бизнес-режим\n"
        "— /voice\\_on / /voice\\_off — голосовые ответы\n"
        "— /web — открыть приложение в браузере\n\n"

        "💬 Просто общайся — я помню контекст разговора!",
        parse_mode="Markdown",
    )


@router.message(Command("mode"))
async def mode_handler(message: Message, user_db: dict | None = None):
    """Переключение режима работы: /mode personal или /mode business."""
    if not message.text:
        return

    # Парсим аргумент команды
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2 or parts[1] not in ("personal", "business"):
        await message.answer(
            "Укажи режим:\n/mode personal — личный\n/mode business — бизнес"
        )
        return

    new_mode = parts[1]
    user_id = message.from_user.id

    # Проверяем доступ к бизнес-режиму (если задан whitelist)
    if new_mode == "business" and BUSINESS_MODE_USERS and user_id not in BUSINESS_MODE_USERS:
        await message.answer("Бизнес-режим недоступен для вашего аккаунта.")
        return

    await set_user_mode(user_id, new_mode)
    icon = "🏢" if new_mode == "business" else "👤"
    label = "Бизнес" if new_mode == "business" else "Личный"
    await message.answer(f"{icon} Режим переключён: {label}")


@router.message(Command("voice_on"))
async def voice_on_handler(message: Message):
    """Включает голосовые ответы."""
    # Используем глобальный config — изменяем на лету
    import config
    config.VOICE_REPLY_MODE = "always"
    await message.answer("🔊 Отвечаю голосом.")


@router.message(Command("voice_off"))
async def voice_off_handler(message: Message):
    """Отключает голосовые ответы."""
    import config
    config.VOICE_REPLY_MODE = "never"
    await message.answer("🔇 Отвечаю текстом.")


@router.message(Command("web"))
async def web_handler(message: Message):
    """Команда /web — генерирует magic-link для доступа к miniapp из браузера.
    Создаёт JWT токен (5 мин), отправляет кнопку со ссылкой.
    """
    import os
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from api.deps import create_jwt

    user_id = message.from_user.id
    miniapp_url = os.environ.get("MINIAPP_URL", "https://77-238-235-171.sslip.io")

    # Создаём magic-токен (живёт 5 минут, одноразовый по назначению)
    magic_token = create_jwt(telegram_id=user_id, expires_in=300, purpose="magic")
    link = f"{miniapp_url}/auth?token={magic_token}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Открыть в браузере", url=link)]
    ])

    await message.answer(
        "🔗 Ссылка для доступа к приложению из браузера.\n"
        "Действует **5 минут**, после чего сессия будет работать 24 часа.\n\n"
        "⚠️ Не передавай эту ссылку другим людям.",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )

@router.message(Command("research"))
async def research_handler(message: Message):
    """Команда /research - magic-link для Research Platform (research.thalors.ai)."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from api.deps import create_jwt

    user_id = message.from_user.id
    research_url = "https://research.thalors.ai"

    # Magic-токен (5 мин)
    magic_token = create_jwt(telegram_id=user_id, expires_in=300, purpose="magic")
    link = f"{research_url}/auth?token={magic_token}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔬 Открыть Research Platform", url=link)]
    ])

    await message.answer(
        "🔬 **Research Platform**\n\n"
        "Ссылка для входа в панель управления сбором данных.\n"
        "Действует **5 минут**.\n\n"
        "Там вы сможете:\n"
        "• Просматривать задачи и результаты\n"
        "• Создавать новые задачи сбора\n"
        "• Экспортировать данные в CSV\n\n"
        "⚠️ Не передавайте ссылку другим людям.",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )

