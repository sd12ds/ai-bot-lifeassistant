"""
Хендлеры действий над задачами (callback-кнопки).
- task_done:<id>               — кнопка «✅ Выполнено» из уведомления
- task_done_list:single:<id>   — кнопка «✅ Выполнено» из списка задач
- postpone:single:<id>:choose  — первый клик «⏱ Перенести»
- postpone:single:<id>:<min>   — второй клик с выбором интервала
- edit:single:<id>             — запрос редактирования (FSM)
- edit_cancel:<id>             — отмена редактирования (FSM)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from bot.states import EditTaskStates
from db import storage
from db import reminders as rdb
from bot.keyboards.postpone_kb import postpone_kb
from bot.keyboards.tasks_kb import tasks_menu_kb

router = Router()


@router.callback_query(F.data.startswith("task_done"))
async def on_task_done(cb: CallbackQuery) -> None:
    """Обрабатывает нажатие «✅ Выполнено».
    Форматы callback_data:
      task_done:<task_id>              — из уведомления
      task_done_list:single:<task_id>  — из списка задач
    """
    data = cb.data or ""
    if data.startswith("task_done_list:"):
        parts = data.split(":", 2)
        raw_id = parts[2] if len(parts) > 2 else ""
    else:
        raw_id = data.split(":", 1)[-1]

    try:
        task_id = int(raw_id)
    except Exception:
        await cb.answer("Некорректный идентификатор", show_alert=True)
        return

    # Помечаем задачу выполненной
    await storage.complete_task(task_id=task_id, user_id=cb.from_user.id)

    # Убираем клавиатуру у этого сообщения
    await cb.answer("Готово — задача выполнена!")
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.callback_query(F.data.startswith("postpone:"))
async def on_postpone(cb: CallbackQuery) -> None:
    """Обрабатывает нажатие «⏱ Перенести».
    Форматы callback_data:
      postpone:single:<task_id>:choose   — показать меню выбора интервала
      postpone:single:<task_id>:<min>    — применить перенос на <min> минут
      postpone:single:<task_id>:cancel   — отменить
    """
    parts = (cb.data or "").split(":", 3)
    if len(parts) < 4:
        await cb.answer("Ошибка параметров", show_alert=True)
        return

    _, scope, raw_id, action = parts
    try:
        task_id = int(raw_id)
    except ValueError:
        await cb.answer("Некорректный ID", show_alert=True)
        return

    if action == "cancel":
        # Восстанавливаем исходный вид задачи
        us = await rdb.get_user_settings(cb.from_user.id)
        tz = ZoneInfo(us.get("timezone", "Europe/Moscow"))
        task = await storage.get_task(task_id, cb.from_user.id)
        if task:
            from bot.handlers.task_menu import _format_task_line, _task_kb
            try:
                await cb.message.edit_text(
                    _format_task_line(task, tz),
                    reply_markup=_task_kb(task_id),
                )
            except Exception:
                pass
        await cb.answer("Отменено")
        return

    if action == "choose":
        # Первый клик — показать варианты переноса в этом же сообщении
        us = await rdb.get_user_settings(cb.from_user.id)
        tz = ZoneInfo(us.get("timezone", "Europe/Moscow"))
        task = await storage.get_task(task_id, cb.from_user.id)
        if task:
            from bot.handlers.task_menu import _format_task_line
            line = _format_task_line(task, tz)
        else:
            line = f"Задача [{task_id}]"
        try:
            await cb.message.edit_text(
                line + "\n\n⏱ На сколько перенести?",
                reply_markup=postpone_kb(scope, task_id),
            )
        except Exception:
            pass
        await cb.answer()
        return

    if action.isdigit():
        # Второй клик — применяем перенос
        minutes = int(action)
        us = await rdb.get_user_settings(cb.from_user.id)
        tz = ZoneInfo(us.get("timezone", "Europe/Moscow"))
        task = await storage.get_task(task_id, cb.from_user.id)

        if task and task.get("due_datetime"):
            cur = datetime.fromisoformat(task["due_datetime"])
            if cur.tzinfo is None:
                cur = cur.replace(tzinfo=tz)
            new_due = cur + timedelta(minutes=minutes)
        else:
            # Если срока нет — отсчитываем от текущего момента
            new_due = datetime.now(tz) + timedelta(minutes=minutes)

        # Обновляем срок и напоминание
        await storage.update_task_due(task_id, cb.from_user.id, new_due.isoformat())
        await rdb.cancel_pending_reminders_for_task(cb.from_user.id, task_id)
        await rdb.schedule_reminder_for_task(cb.from_user.id, task_id, new_due.isoformat())

        # Обновляем текст сообщения
        updated = await storage.get_task(task_id, cb.from_user.id)
        if updated:
            from bot.handlers.task_menu import _format_task_line, _task_kb
            try:
                await cb.message.edit_text(
                    _format_task_line(updated, tz),
                    reply_markup=_task_kb(task_id),
                )
            except Exception:
                pass
        await cb.answer("Перенесено!")
        return

    # Неизвестный action
    await cb.answer("Неизвестное действие", show_alert=True)


# ──────────────────────────────────────────────
# Редактирование задачи через FSM
# ──────────────────────────────────────────────

def _edit_cancel_kb(task_id: int) -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой ❌ Отмена для режима редактирования."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"edit_cancel:{task_id}",
        )
    ]])


@router.callback_query(F.data.startswith("edit:"))
async def on_edit_request(cb: CallbackQuery, state: FSMContext) -> None:
    """Переводит задачу в режим редактирования через FSM.
    Формат callback_data: edit:single:<task_id>
    """
    parts = (cb.data or "").split(":", 2)
    if len(parts) < 3:
        await cb.answer("Ошибка параметров", show_alert=True)
        return
    _, scope, raw_id = parts
    try:
        task_id = int(raw_id)
    except ValueError:
        await cb.answer("Некорректный ID", show_alert=True)
        return

    # Сохраняем context в FSM: task_id и message_id задачи для последующего
    # восстановления клавиатуры (на случай отмены или успешного редактирования)
    await state.set_state(EditTaskStates.waiting_for_text)
    await state.update_data(task_id=task_id, orig_msg_id=cb.message.message_id)

    # Переключаем сообщение задачи в «режим редактирования»: убираем кнопки
    # действий и показываем только кнопку Отмена — пользователь видит чёткий
    # индикатор того, что идёт ввод, и может выйти из режима в любой момент.
    try:
        await cb.message.edit_reply_markup(reply_markup=_edit_cancel_kb(task_id))
    except Exception:
        pass

    # Просим пользователя ввести новый текст; клавиатура задач сохраняется
    await cb.message.answer(
        f"✏️ Редактирование задачи [{task_id}]\n"
        "Введите новый текст:\n"
        "• просто заголовок\n"
        "• или «Заголовок: описание»",
        reply_markup=tasks_menu_kb(),  # восстанавливаем нижнее меню
    )
    await cb.answer()


@router.callback_query(F.data.startswith("edit_cancel:"))
async def on_edit_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    """Отменяет редактирование: восстанавливает полную клавиатуру задачи."""
    parts = (cb.data or "").split(":", 1)
    raw_id = parts[1] if len(parts) > 1 else ""
    try:
        task_id = int(raw_id)
    except ValueError:
        await cb.answer("Ошибка", show_alert=True)
        return

    # Сбрасываем FSM-состояние
    await state.clear()

    # Восстанавливаем полную клавиатуру задачи (кнопки действий)
    us = await rdb.get_user_settings(cb.from_user.id)
    tz = ZoneInfo(us.get("timezone", "Europe/Moscow"))
    task = await storage.get_task(task_id, cb.from_user.id)
    if task:
        from bot.handlers.task_menu import _format_task_line, _task_kb
        try:
            await cb.message.edit_text(
                _format_task_line(task, tz),
                reply_markup=_task_kb(task_id),
            )
        except Exception:
            pass

    await cb.answer("Редактирование отменено")


@router.message(StateFilter(EditTaskStates.waiting_for_text), F.text)
async def on_edit_apply(message: Message, state: FSMContext) -> None:
    """Принимает новый текст задачи из FSM-состояния и применяет изменения."""
    # Получаем task_id и message_id из FSM
    data = await state.get_data()
    task_id: int | None = data.get("task_id")
    orig_msg_id: int | None = data.get("orig_msg_id")

    if task_id is None:
        await state.clear()
        return

    # Разбираем новый текст: «Заголовок[: описание]»
    raw = (message.text or "").strip()
    if not raw:
        await message.reply("Пустой текст. Введите заголовок или «Заголовок: описание».")
        return
    if ":" in raw:
        title, desc = raw.split(":", 1)
        title, desc = title.strip(), desc.strip()
    else:
        title, desc = raw, ""
    if not title:
        await message.reply("Заголовок не должен быть пустым.")
        return

    # Применяем изменения в БД
    ok = await storage.update_task_text(
        task_id=task_id,
        user_id=message.from_user.id,
        title=title,
        description=desc,
    )
    if not ok:
        await state.clear()
        await message.reply("Задача не найдена или не принадлежит вам.")
        return

    # Сбрасываем FSM-состояние
    await state.clear()

    # Обновляем исходное сообщение с задачей (восстанавливаем полный вид)
    if orig_msg_id:
        try:
            us = await rdb.get_user_settings(message.from_user.id)
            tz = ZoneInfo(us.get("timezone", "Europe/Moscow"))
            updated = await storage.get_task(task_id, message.from_user.id)
            if updated:
                from bot.handlers.task_menu import _format_task_line, _task_kb
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=orig_msg_id,
                    text=_format_task_line(updated, tz),
                    reply_markup=_task_kb(task_id),
                )
        except Exception:
            # Не падаем, если не удалось обновить сообщение
            pass

    # Подтверждение + восстанавливаем нижнее меню задач
    await message.answer("✅ Задача обновлена.", reply_markup=tasks_menu_kb())
