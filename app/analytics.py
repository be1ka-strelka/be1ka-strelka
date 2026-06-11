# -*- coding: utf-8 -*-
"""
Ядро аналитики: чтение Excel-файлов по дисциплине тренеров,
расчёт метрик, динамики по месяцам, топ/антитоп и прогноза на лето.

Ожидаемая структура файла (лист "Дисциплина"):
    ID тренера | Общее кол-во уроков | Количество учеников |
    Отмены по инициативе тренера | Замены по инициативе тренера |
    Переносы по инициативе тренера | Переносы по инициативе ученика |
    Отмены по инициативе ученика
"""
import io
import re
from collections import defaultdict

import openpyxl

# Канонические имена колонок (как в исходных файлах)
COLUMNS = [
    "ID тренера",
    "Общее кол-во уроков",
    "Количество учеников",
    "Отмены по инициативе тренера",
    "Замены по инициативе тренера",
    "Переносы по инициативе тренера",
    "Переносы по инициативе ученика",
    "Отмены по инициативе ученика",
]

# Машиночитаемые ключи для каждой колонки
KEYS = [
    "teacher_id",
    "lessons_total",
    "students",
    "cancel_teacher",
    "replace_teacher",
    "reschedule_teacher",
    "reschedule_student",
    "cancel_student",
]

COL_TO_KEY = dict(zip(COLUMNS, KEYS))

# Русские названия месяцев -> порядковый номер для сортировки динамики
MONTH_ORDER = {
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4,
    "май": 5, "июнь": 6, "июль": 7, "август": 8,
    "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12,
}


def detect_month(filename):
    """Извлекает название месяца из имени файла (для оси времени)."""
    name = filename.lower()
    for ru in MONTH_ORDER:
        if ru in name:
            return ru
    # если месяц не распознан — вернём само имя без расширения
    return re.sub(r"\.xlsx?$", "", name)


class ValidationError(Exception):
    pass


def parse_workbook(file_bytes, filename):
    """
    Читает один xlsx (в виде bytes) и возвращает список строк-словарей.
    Бросает ValidationError при несовпадении структуры.
    """
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    except Exception as e:
        raise ValidationError(f"Не удалось открыть файл «{filename}»: {e}")

    ws = wb.active  # лист "Дисциплина"
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValidationError(f"Файл «{filename}» пустой.")

    header = [str(c).strip() if c is not None else "" for c in rows[0]]
    if header[: len(COLUMNS)] != COLUMNS:
        raise ValidationError(
            f"Структура файла «{filename}» не совпадает с ожидаемой.\n"
            f"Ожидалось: {COLUMNS}\nПолучено: {header}"
        )

    month = detect_month(filename)
    out = []
    for r in rows[1:]:
        if r is None or r[0] is None:
            continue  # пропускаем пустые строки
        record = {"month": month}
        for key, val in zip(KEYS, r):
            if key == "teacher_id":
                record[key] = val
            else:
                record[key] = int(val) if val is not None else 0
        out.append(record)
    return out


def aggregate(files):
    """
    files: список (filename, bytes).
    Возвращает структуру с агрегированными данными по всем месяцам.
    """
    all_rows = []
    months_loaded = []
    for filename, data in files:
        rows = parse_workbook(data, filename)
        all_rows.extend(rows)
        m = detect_month(filename)
        if m not in months_loaded:
            months_loaded.append(m)

    months_sorted = sorted(months_loaded, key=lambda m: MONTH_ORDER.get(m, 99))

    # Сводка по каждому тренеру (сумма по всем загруженным месяцам)
    by_teacher = defaultdict(lambda: {k: 0 for k in KEYS if k not in ("teacher_id",)})
    # Динамика учеников по месяцам: teacher_id -> {month: students}
    students_dynamics = defaultdict(dict)

    for row in all_rows:
        tid = row["teacher_id"]
        agg = by_teacher[tid]
        for k in KEYS:
            if k == "teacher_id":
                continue
            agg[k] += row[k]
        students_dynamics[tid][row["month"]] = row["students"]

    teachers = []
    for tid, agg in by_teacher.items():
        teachers.append({
            "teacher_id": tid,
            "lessons_total": agg["lessons_total"],
            "students_sum": agg["students"],
            "cancel_teacher": agg["cancel_teacher"],
            "replace_teacher": agg["replace_teacher"],
            "reschedule_teacher": agg["reschedule_teacher"],
            "reschedule_student": agg["reschedule_student"],
            "cancel_student": agg["cancel_student"],
            "dynamics": [students_dynamics[tid].get(m, 0) for m in months_sorted],
        })

    teachers.sort(key=lambda t: str(t["teacher_id"]))

    return {
        "months": months_sorted,
        "teachers": teachers,
        "totals": _totals(teachers),
        "tops": _tops(teachers),
        "summer_forecast": summer_forecast(teachers, months_sorted),
    }


def _totals(teachers):
    """Итоги по школе."""
    t = {
        "teachers_count": len(teachers),
        "cancel_teacher": 0,
        "cancel_student": 0,
        "reschedule_teacher": 0,
        "reschedule_student": 0,
        "replace_teacher": 0,
        "lessons_total": 0,
    }
    for x in teachers:
        for k in ("cancel_teacher", "cancel_student", "reschedule_teacher",
                  "reschedule_student", "replace_teacher", "lessons_total"):
            t[k] += x[k]
    return t


def _tops(teachers, n=5):
    """
    Топ/антитоп. Замены и переносы тренера считаем ОТДЕЛЬНО (по пожеланию).
    Для ранжирования п.7-8 берём суммарный «инициативный» показатель тренера:
    переносы тренера + замены тренера (оба про дисциплину тренера),
    но в карточке показываем раздельно.
    """
    def score(t):
        return t["reschedule_teacher"] + t["replace_teacher"]

    ranked = sorted(teachers, key=score, reverse=True)
    most = [t for t in ranked if score(t) > 0][:n]
    # антитоп — среди тех, у кого есть уроки (активные тренеры)
    active = [t for t in teachers if t["lessons_total"] > 0]
    least = sorted(active, key=score)[:n]
    return {"most": most, "least": least}


# --- Прогноз на лето -------------------------------------------------------
# Коэффициенты основаны на открытой статистике сезонности детских
# образовательных программ (источники см. в docs/PROJECT.md):
#  - Gallup 2024: ~45% детей не вовлечены в летние программы, только 55%
#    участвуют хотя бы в одной структурированной активности летом.
#  - Конец учебного года + сезон отпусков => снижение спроса на ментальную
#    арифметику, скорочтение, подготовку к школе/экзаменам.
# Эмпирические множители спада к среднемесячному уровню весны:
SUMMER_FACTORS = {
    "июнь": 0.70,   # учебный год только закончился, часть ещё ходит
    "июль": 0.50,   # пик отпусков, минимум спроса
    "август": 0.65, # начинается подготовка к школе, частичное возвращение
}
# Множитель роста отмен/переносов по инициативе ученика летом (отпуска, отъезды)
SUMMER_STUDENT_CANCEL_UPLIFT = 1.6


def summer_forecast(teachers, months_sorted):
    """
    Прогноз летних показателей по школе на основе средних весенних значений.
    Возвращает по-месячный прогноз учеников и отмен/переносов ученика.
    """
    n_months = max(len(months_sorted), 1)
    total_students_avg = sum(t["students_sum"] for t in teachers) / n_months
    cancel_student_avg = sum(t["cancel_student"] for t in teachers) / n_months
    resched_student_avg = sum(t["reschedule_student"] for t in teachers) / n_months
    cancel_teacher_avg = sum(t["cancel_teacher"] for t in teachers) / n_months

    forecast = []
    for month, factor in SUMMER_FACTORS.items():
        forecast.append({
            "month": month,
            "students": round(total_students_avg * factor),
            "cancel_student": round(cancel_student_avg * factor * SUMMER_STUDENT_CANCEL_UPLIFT),
            "reschedule_student": round(resched_student_avg * factor * SUMMER_STUDENT_CANCEL_UPLIFT),
            # отмены тренера падают вместе с нагрузкой (меньше уроков -> меньше отмен)
            "cancel_teacher": round(cancel_teacher_avg * factor),
        })
    return {
        "spring_avg_students": round(total_students_avg),
        "factors": SUMMER_FACTORS,
        "student_cancel_uplift": SUMMER_STUDENT_CANCEL_UPLIFT,
        "forecast": forecast,
    }
