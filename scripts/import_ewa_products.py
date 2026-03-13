"""
Импорт EWA Product (здоровое питание) в food_items.
Парсит КБЖУ из HTML-таблиц разных форматов, приводит к 100г.
Описания/преимущества сохраняет в JSON для бота.
"""
import asyncio, json, re, sys, os
import httpx
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class RowParser(HTMLParser):
    """Парсит HTML-таблицу в список строк [[cell, cell, ...], ...]."""
    def __init__(self):
        super().__init__()
        self._in_cell = False
        self._rows = []
        self._current_row = []
        self._current_cell = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self._current_row = []
        elif tag in ('td', 'th'):
            self._in_cell = True
            self._current_cell = ''

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self._in_cell:
            self._in_cell = False
            self._current_row.append(self._current_cell.strip())
        elif tag == 'tr':
            if self._current_row:
                self._rows.append(self._current_row)
                self._current_row = []

    def handle_data(self, data):
        if self._in_cell:
            self._current_cell += data


def _num(text: str) -> float:
    """Первое число из текста."""
    m = re.search(r'(\d+[,.]?\d*)', text)
    return float(m.group(1).replace(',', '.')) if m else 0


def _kcal(text: str) -> float:
    """Калории из '430 кДж / 100 ккал' или '98/410'."""
    m = re.search(r'(\d+)\s*ккал', text.lower())
    if m: return float(m.group(1))
    m2 = re.search(r'(\d+)\s*/\s*(\d+)', text)
    if m2:
        a, b = float(m2.group(1)), float(m2.group(2))
        return min(a, b)
    return _num(text)


def parse_nutrition_100g(structure_html: str) -> dict:
    """Извлекает КБЖУ на 100г из HTML-таблицы состава."""
    r = {'protein_g': 0, 'fat_g': 0, 'carbs_g': 0, 'calories': 0}
    if not structure_html:
        return r

    # Парсим все таблицы в строки
    parser = RowParser()
    parser.feed(structure_html)
    rows = parser._rows

    # Стратегия 1: ищем столбец "на 100 г" / "в 100 г"
    col_100g = -1
    for row in rows:
        for ci, cell in enumerate(row):
            if re.search(r'(?:в|на|содержание.*)100\s*г', cell, re.I):
                col_100g = ci
                break
        if col_100g >= 0:
            break

    if col_100g >= 0:
        # Используем значения из столбца "на 100 г"
        for row in rows:
            if len(row) <= col_100g:
                continue
            label = row[0].lower()
            val = _num(row[col_100g])
            if re.match(r'белки', label) and val:
                r['protein_g'] = val
            elif label.startswith('жиры') and val:
                r['fat_g'] = val
            elif re.match(r'углеводы', label) and val:
                r['carbs_g'] = val
            elif 'энергетическ' in label:
                r['calories'] = _kcal(row[col_100g])
        # Если калории не найдены — ищем отдельно строку "энергетическая ценность на 100 г"
        if not r['calories']:
            for row in rows:
                if len(row) >= 2 and 'энергетическ' in row[0].lower() and '100' in row[0]:
                    r['calories'] = _kcal(row[1])
                    break
        return r

    # Стратегия 2: ищем строку "Энергетическая ценность на 100 г" (отдельная строка в таблице)
    cal_100g = 0
    for row in rows:
        if len(row) >= 2 and 'энергетическ' in row[0].lower() and '100' in row[0].lower():
            cal_100g = _kcal(row[1])
            break

    # Стратегия 3: одна колонка "Содержание" (per serving) — извлекаем + пересчитываем
    serving_g = 0
    sm = re.search(r'(?:порци\w*|саше[- ]?пакет\w*)\s*[–—(,-]?\s*(\d+[,.]?\d*)\s*г', structure_html, re.I)
    if not sm:
        sm = re.search(r'на\s+порцию\s+(\d+[,.]?\d*)\s*г', structure_html, re.I)
    if not sm:
        sm = re.search(r'(\d+[,.]?\d*)\s*г\s*\(1\s*(?:шт|порц)', structure_html, re.I)
    if sm:
        serving_g = float(sm.group(1).replace(',', '.'))

    # Значения из первых совпадений в таблице
    for row in rows:
        if len(row) < 2:
            continue
        label = row[0].lower()
        # Ищем значение во втором столбце
        val_text = row[1]
        val = _num(val_text)

        if re.match(r'белки', label) and val and not r['protein_g']:
            r['protein_g'] = val
        elif label.startswith('жиры') and val and not r['fat_g']:
            r['fat_g'] = val
        elif re.match(r'углеводы', label) and val and not r['carbs_g']:
            r['carbs_g'] = val
        elif 'энергетическ' in label and '100' not in label and not r['calories']:
            r['calories'] = _kcal(val_text)

    # Если есть cal_100g из отдельной строки — используем его (он точнее)
    if cal_100g:
        r['calories'] = cal_100g
    elif serving_g > 0 and r['calories']:
        # Пересчёт порция → 100г
        ratio = 100 / serving_g
        r['calories'] = round(r['calories'] * ratio, 1)
        r['protein_g'] = round(r['protein_g'] * ratio, 1)
        r['fat_g'] = round(r['fat_g'] * ratio, 1)
        r['carbs_g'] = round(r['carbs_g'] * ratio, 1)

    # Если калорий нет, рассчитаем по формуле 4*Б + 9*Ж + 4*У
    if not r['calories'] and (r['protein_g'] or r['fat_g'] or r['carbs_g']):
        r['calories'] = round(4 * r['protein_g'] + 9 * r['fat_g'] + 4 * r['carbs_g'], 1)

    return r


def clean_html(h):
    if not h: return ''
    t = re.sub(r'<br\s*/?>', '\n', h)
    t = re.sub(r'</div>', '\n', t)
    t = re.sub(r'<[^>]+>', '', t)
    return re.sub(r'\n{3,}', '\n\n', t).strip()


async def main():
    print("🔄 Загружаю продукты с ewaproduct.com...")
    async with httpx.AsyncClient(timeout=30) as c:
        data = (await c.post('https://ewaproduct.com/api/products/list?country_id=1', json={})).json()

    hp = [p for p in data if 'здоровое питание' in p.get('categories', [])]
    print(f"📦 {len(hp)} продуктов")

    parsed = []
    descriptions = {}  # Для бота — имя → описание + преимущества

    for p in hp:
        name = f"EWA {p['name']}"
        n = parse_nutrition_100g(p.get('structure', ''))

        # Описание для бота
        subtitle = p.get('attributes', {}).get('subtitle', '')
        packaging = p.get('attributes', {}).get('packaging', '')
        benefits = clean_html(p.get('key_features', ''))
        desc = '\n'.join(filter(None, [subtitle, f"Упаковка: {packaging}" if packaging else '', benefits]))
        descriptions[name] = desc

        parsed.append({'name': name, **n})

    print("\n" + "=" * 60)
    issues = 0
    for i, it in enumerate(parsed, 1):
        flag = "⚠️" if it['calories'] < 10 else "✅"
        if it['calories'] < 10: issues += 1
        print(f"{flag} {i:2d}. {it['name']}")
        print(f"      {it['calories']} ккал | Б:{it['protein_g']} Ж:{it['fat_g']} У:{it['carbs_g']}")

    if issues:
        print(f"\n⚠️ {issues} продуктов с подозрительными калориями — будут рассчитаны по формуле 4Б+9Ж+4У")

    # Сохраняем описания в JSON для бота
    desc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'ewa_products.json')
    os.makedirs(os.path.dirname(desc_path), exist_ok=True)
    with open(desc_path, 'w', encoding='utf-8') as f:
        json.dump(descriptions, f, ensure_ascii=False, indent=2)
    print(f"\n📝 Описания сохранены в {desc_path}")

    # Запись в БД
    print("\n🔄 Записываю в базу данных...")
    database_url = "postgresql+asyncpg://aiuser:changeme@localhost:5432/aiassistant"

    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    added = skipped = 0
    async with async_session() as session:
        for it in parsed:
            existing = await session.execute(
                text("SELECT id FROM food_items WHERE name = :name"), {'name': it['name']}
            )
            if existing.scalar_one_or_none():
                print(f"  ⏭ {it['name']} — уже есть")
                skipped += 1
                continue

            await session.execute(
                text("INSERT INTO food_items (name, calories, protein_g, fat_g, carbs_g) VALUES (:n, :c, :p, :f, :u)"),
                {'n': it['name'], 'c': it['calories'], 'p': it['protein_g'], 'f': it['fat_g'], 'u': it['carbs_g']}
            )
            added += 1
            print(f"  ✅ {it['name']} — {it['calories']} ккал/100г")

        await session.commit()
    await engine.dispose()
    print(f"\n✅ Добавлено: {added}, пропущено: {skipped}")


if __name__ == '__main__':
    asyncio.run(main())
