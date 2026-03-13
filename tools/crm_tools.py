"""
LangChain @tool для CRM (контакты, сделки).
Привязываются к user_id через make_crm_tools().
"""
from __future__ import annotations

from langchain.tools import tool
from db import storage


def make_crm_tools(user_id: int) -> list:
    """Создаёт CRM tools, привязанные к конкретному user_id."""

    @tool
    async def crm_add_contact(
        name: str,
        phone: str = "",
        email: str = "",
        company: str = "",
        notes: str = "",
    ) -> str:
        """
        Добавляет новый контакт в CRM.
        Используй когда пользователь говорит «добавь клиента», «запиши контакт»,
        «новый контакт».

        Args:
            name: Имя контакта (обязательно).
            phone: Телефон.
            email: Email.
            company: Компания.
            notes: Заметки.
        """
        contact_id = await storage.add_contact(
            user_id=user_id, name=name, phone=phone,
            email=email, company=company, notes=notes,
        )
        return f"✅ Контакт добавлен: [{contact_id}] {name}"

    @tool
    async def crm_find_contact(query: str) -> str:
        """
        Ищет контакт по имени, компании или email.
        Используй когда пользователь спрашивает «найди контакт», «есть ли у меня клиент X».

        Args:
            query: Строка поиска (имя, компания, email).
        """
        contacts = await storage.find_contacts(user_id=user_id, query=query)
        if not contacts:
            return f"Контакт '{query}' не найден."
        lines = [f"Найдено {len(contacts)} контактов:"]
        for c in contacts[:10]:
            info = f"[{c['id']}] {c['name']}"
            if c.get("company"):
                info += f" ({c['company']})"
            if c.get("phone"):
                info += f" | {c['phone']}"
            lines.append(info)
        return "\n".join(lines)

    @tool
    async def crm_list_contacts() -> str:
        """
        Показывает последние контакты CRM.
        Используй когда пользователь говорит «покажи контакты», «список клиентов».
        """
        contacts = await storage.list_contacts(user_id=user_id)
        if not contacts:
            return "CRM пуст — контактов нет."
        lines = [f"Контакты ({len(contacts)}):"]
        for c in contacts:
            info = f"[{c['id']}] {c['name']}"
            if c.get("company"):
                info += f" | {c['company']}"
            lines.append(info)
        return "\n".join(lines)

    @tool
    async def crm_add_deal(
        title: str,
        amount: float = 0.0,
        notes: str = "",
    ) -> str:
        """
        Создаёт новую сделку в CRM.
        Используй когда пользователь говорит «добавь сделку», «новый проект»,
        «запиши продажу».

        Args:
            title: Название сделки.
            amount: Сумма сделки (0 если не указана).
            notes: Комментарий.
        """
        deal_id = await storage.add_deal(
            user_id=user_id, title=title, amount=amount, notes=notes
        )
        amount_str = f" на {amount:.0f} руб." if amount else ""
        return f"✅ Сделка добавлена: [{deal_id}] {title}{amount_str}"

    @tool
    async def crm_list_deals(status: str = "") -> str:
        """
        Показывает сделки CRM.
        Используй когда пользователь говорит «покажи сделки», «что в работе»,
        «статус сделок».

        Args:
            status: Фильтр по статусу: new, in_progress, won, lost.
                    Пустая строка — показать все.
        """
        deals = await storage.list_deals(user_id=user_id, status=status or None)
        if not deals:
            return "Сделок нет."
        status_icons = {"new": "🆕", "in_progress": "🔄", "won": "✅", "lost": "❌"}
        lines = [f"Сделки ({len(deals)}):"]
        for d in deals:
            icon = status_icons.get(d["status"], "•")
            amount_str = f" | {d['amount']:.0f} руб." if d.get("amount") else ""
            lines.append(f"{icon} [{d['id']}] {d['title']}{amount_str}")
        return "\n".join(lines)

    @tool
    async def crm_update_deal_status(deal_id: int, status: str) -> str:
        """
        Обновляет статус сделки.
        Используй когда пользователь говорит «закрой сделку», «перевёл в работу»,
        «сделка выиграна/проиграна».

        Args:
            deal_id: ID сделки.
            status: Новый статус: new, in_progress, won, lost.
        """
        valid = {"new", "in_progress", "won", "lost"}
        if status not in valid:
            return f"Неверный статус '{status}'. Допустимые: {', '.join(valid)}"
        ok = await storage.update_deal_status(deal_id=deal_id, user_id=user_id, status=status)
        return f"✅ Статус сделки [{deal_id}] обновлён: {status}" if ok else f"Сделка [{deal_id}] не найдена."

    return [crm_add_contact, crm_find_contact, crm_list_contacts,
            crm_add_deal, crm_list_deals, crm_update_deal_status]
