from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from app.models.request import TransactionItem, UserProfile, SalaryCycleInfo

_SAVINGS_THRESHOLD = 5.0  # EUR — minimum category spend before suggesting a savings tip


def _fmt(value: float) -> str:
    """Format to at most 2 decimal places, stripping trailing zeros."""
    s = f"{value:.2f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "EN": {
        "pacing_good_start": [
            "Great start! No significant expenses yet. 🌱",
            "Clean week so far — keep it up! ✨",
        ],
        "pacing_over": [
            "⚠️ {pct_over}% over budget! Cut {top_cat} now.",
            "{top_cat} blew your week by {pct_over}%. 🕳️",
        ],
        "pacing_warn": [
            "{pct_used}% used this week. Slow it down! 🐢",
            "Heads up: {pct_used}% of your weekly budget spent.",
        ],
        "pacing_great": [
            "Houston, only {pct_used}% used on {day_name}. 🚀",
            "Stellar pace — {pct_used}% burned. All clear! ✨",
        ],
        "salary_just_in": [
            "💰 Payday! Keep goal: {goal} {currency}. Spend wisely.",
            "Fresh cash in! Stick to your {goal} {currency} plan.",
        ],
        "balanced": [
            "Spending orbit stable — no leaks detected! 🛸",
            "All systems balanced. Solid week! 💪",
        ],
        "pacing_good": [
            "On track! Trim {top_cat} 15% → ~{potential_saving} {currency} saved.",
        ],
        "predicted_shortfall": [
            "Shortfall ahead: {predicted_balance} {currency}. Cut now! 🔴",
            "Trending to {predicted_balance} {currency} month-end. Danger! ⚠️",
        ],
        "no_income_logged": [
            "No income logged. Add salary in Settings! 📊",
            "Set expected salary in Settings to unlock insights.",
        ],
        "on_track": [
            "Trajectory: {predicted_balance} {currency} at month's end. 🌙",
            "Orbit stable — {predicted_balance} {currency} projected. ✅",
        ],
    },
    "RU": {
        "pacing_good_start": [
            "Отличное начало! Расходов почти нет. 🌱",
            "Чистая неделя! Продолжай в том же духе! ✨",
        ],
        "pacing_over": [
            "⚠️ Перерасход {pct_over}%! Урежьте {top_cat}.",
            "{top_cat} сжёг бюджет на {pct_over}% сверх нормы. 🕳️",
        ],
        "pacing_warn": [
            "{pct_used}% бюджета потрачено. Тише! 🐢",
            "Внимание: {pct_used}% недели потрачено.",
        ],
        "pacing_great": [
            "Хьюстон, только {pct_used}% бюджета. 🚀",
            "Отличный темп — {pct_used}% истрачено. Так держать! ✨",
        ],
        "salary_just_in": [
            "💰 Зарплата! Цель: {goal} {currency}. Тратьте мудро.",
            "Деньги пришли! Держите план: {goal} {currency}.",
        ],
        "balanced": [
            "Орбита трат стабильна — утечек нет! 🛸",
            "Все категории сбалансированы. Отличная неделя! 💪",
        ],
        "pacing_good": [
            "На курсе! Сократи {top_cat} 15% → ~{potential_saving} {currency}.",
        ],
        "predicted_shortfall": [
            "Дефицит! Конец месяца: {predicted_balance} {currency}. 🔴",
            "Тренд → {predicted_balance} {currency}. Опасность! ⚠️",
        ],
        "no_income_logged": [
            "Дохода нет. Добавьте зарплату в настройках! 📊",
            "Укажите ожидаемый доход в настройках.",
        ],
        "on_track": [
            "Траектория: {predicted_balance} {currency} в конце месяца. 🌙",
            "Орбита стабильна — {predicted_balance} {currency} прогноз. ✅",
        ],
    },
    "UA": {
        "pacing_good_start": [
            "Чудовий старт! Витрат майже немає. 🌱",
            "Чистий тиждень — так тримати! ✨",
        ],
        "pacing_over": [
            "⚠️ Перевитрат {pct_over}%! Скоротіть {top_cat}.",
            "{top_cat} спалив бюджет на {pct_over}% понад норму. 🕳️",
        ],
        "pacing_warn": [
            "{pct_used}% бюджету витрачено. Стоп! 🐢",
            "Увага: {pct_used}% тижня витрачено.",
        ],
        "pacing_great": [
            "Хьюстон, лише {pct_used}% бюджету. 🚀",
            "Чудовий темп — {pct_used}% витрачено. Так тримати! ✨",
        ],
        "salary_just_in": [
            "💰 Зарплата! Ціль: {goal} {currency}. Витрачайте мудро.",
            "Гроші прийшли! Тримайте план: {goal} {currency}.",
        ],
        "balanced": [
            "Орбіта витрат стабільна — витоків немає! 🛸",
            "Усі категорії збалансовані. Чудовий тиждень! 💪",
        ],
        "pacing_good": [
            "На курсі! Скороти {top_cat} 15% → ~{potential_saving} {currency}.",
        ],
        "predicted_shortfall": [
            "Дефіцит! Кінець місяця: {predicted_balance} {currency}. 🔴",
            "Тренд → {predicted_balance} {currency}. Небезпека! ⚠️",
        ],
        "no_income_logged": [
            "Доходу немає. Додайте зарплату в налаштуваннях! 📊",
            "Вкажіть очікуваний дохід у налаштуваннях.",
        ],
        "on_track": [
            "Траєкторія: {predicted_balance} {currency} наприкінці місяця. 🌙",
            "Орбіта стабільна — {predicted_balance} {currency} прогноз. ✅",
        ],
    },
    "DE": {
        "pacing_good_start": [
            "Guter Start! Kaum Ausgaben bisher. 🌱",
            "Saubere Woche — weiter so! ✨",
        ],
        "pacing_over": [
            "⚠️ {pct_over}% über Budget! Kürze {top_cat}.",
            "{top_cat} fraß Budget um {pct_over}%. 🕳️",
        ],
        "pacing_warn": [
            "{pct_used}% verbraucht. Bremse! 🐢",
            "Achtung: {pct_used}% der Woche verbraucht.",
        ],
        "pacing_great": [
            "Houston, nur {pct_used}% am {day_name}. 🚀",
            "Toller Kurs — {pct_used}% verbraucht. Weiter so! ✨",
        ],
        "salary_just_in": [
            "💰 Gehalt! Ziel: {goal} {currency}. Weise ausgeben.",
            "Geld da! Halte Plan: {goal} {currency}.",
        ],
        "balanced": [
            "Ausgaben-Orbit stabil — keine Lecks! 🛸",
            "Alle Kategorien ausgewogen. Starke Woche! 💪",
        ],
        "pacing_good": [
            "Auf Kurs! {top_cat} 15% kürzen → ~{potential_saving} {currency}.",
        ],
        "predicted_shortfall": [
            "Defizit! Monatsende: {predicted_balance} {currency}. 🔴",
            "Trend → {predicted_balance} {currency}. Gefahr! ⚠️",
        ],
        "no_income_logged": [
            "Kein Einkommen. Gehalt in Einstellungen eintragen! 📊",
            "Erwartetes Gehalt in Einstellungen eingeben.",
        ],
        "on_track": [
            "Kurs: {predicted_balance} {currency} zum Monatsende. 🌙",
            "Orbit stabil — {predicted_balance} {currency} Prognose. ✅",
        ],
    },
}

_SAVINGS_MILESTONE: dict[str, list[str]] = {
    "EN": [
        "🚀 You've stacked {savings} {currency}! Ever thought about investing? 📈",
        "💰 {savings} {currency} saved! An emergency fund is a great first step.",
        "✨ {savings} {currency} banked — treat yourself to that trip! 🌍",
    ],
    "RU": [
        "🚀 Накоплено {savings} {currency}! Может, пора инвестировать? 📈",
        "💰 {savings} {currency} в копилке! Отличный резервный фонд.",
        "✨ {savings} {currency} отложено — может, в путешествие? 🌍",
    ],
    "UA": [
        "🚀 Накопичено {savings} {currency}! Час інвестувати? 📈",
        "💰 {savings} {currency} у скарбничці! Чудовий резервний фонд.",
        "✨ {savings} {currency} відкладено — може, в подорож? 🌍",
    ],
    "DE": [
        "🚀 {savings} {currency} angespart! Zeit zu investieren? 📈",
        "💰 {savings} {currency} zurückgelegt! Ein Notgroschen lohnt sich.",
        "✨ {savings} {currency} gespart — wie wäre es mit einer Reise? 🌍",
    ],
}

_SAVINGS_DIP: dict[str, list[str]] = {
    "EN": [
        "⚠️ Last cycle you dipped into savings. Let's protect them this time! 🛡️",
        "Savings took a hit last cycle. Fixed expenses may be too high — review them! 📋",
        "Last month was costly. Time to guard those savings more fiercely. 💰",
    ],
    "RU": [
        "⚠️ В прошлом цикле задели накопления. Сейчас берегите их! 🛡️",
        "Накопления пострадали. Может, пересмотрим фиксированные расходы? 📋",
        "Предыдущий месяц был затратным. Задумаемся о сокращении подписок? 💰",
    ],
    "UA": [
        "⚠️ Минулий цикл торкнувся заощаджень. Цього разу захистімо їх! 🛡️",
        "Заощадження постраждали. Може, переглянемо фіксовані витрати? 📋",
        "Попередній місяць був витратним. Можливо, скоротимо підписки? 💰",
    ],
    "DE": [
        "⚠️ Letzter Zyklus griff Ersparnisse an. Diesmal schützen wir sie! 🛡️",
        "Ersparnisse litten. Fixkosten könnten zu hoch sein — überprüfe sie! 📋",
        "Letzter Monat war teuer. Zeit, die Ersparnisse besser zu schützen. 💰",
    ],
}

_HIGH_FIXED: dict[str, list[str]] = {
    "EN": [
        "Fixed costs eat {pct}% of income. Any subscriptions to cut? 🔍",
        "Your committed expenses are {pct}% of salary. Room to renegotiate? 💬",
        "High fixed load ({pct}%). Small cuts here compound fast! ✂️",
    ],
    "RU": [
        "Фикс. расходы съедают {pct}% дохода. Есть что сократить? 🔍",
        "Обязательные расходы — {pct}% от зарплаты. Время пересмотреть? 💬",
        "Высокая нагрузка ({pct}%). Небольшие сокращения дают результат! ✂️",
    ],
    "UA": [
        "Фікс. витрати — {pct}% доходу. Є що скоротити? 🔍",
        "Зобов'язані витрати — {pct}% зарплати. Час переглянути? 💬",
        "Висока фіксована нагрузка ({pct}%). Невеликі скорочення дають ефект! ✂️",
    ],
    "DE": [
        "Fixkosten fressen {pct}% des Einkommens. Etwas kürzen? 🔍",
        "Pflichtausgaben sind {pct}% des Gehalts. Neuverhandlung möglich? 💬",
        "Hohe Fixlast ({pct}%). Kleine Kürzungen wirken schnell! ✂️",
    ],
}

_TOP_CAT_FALLBACK: dict[str, str] = {
    "EN": "expenses",
    "RU": "расходы",
    "UA": "витрати",
    "DE": "Ausgaben",
}

_DAY_NAMES: dict[str, list[str]] = {
    "EN": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "RU": ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
    "UA": ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"],
    "DE": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
}


def _build_context(
    transactions: list[TransactionItem],
    profile: UserProfile,
    analysis_date: date,
    predicted_balance: float,
    user_categories: list[str] | None = None,
) -> dict[str, Any]:
    monday = analysis_date - timedelta(days=analysis_date.isoweekday() - 1)
    week_expenses = [tx for tx in transactions if tx.type == "expense" and tx.date >= monday]
    week_spending = sum(tx.amount for tx in week_expenses)

    month_income = sum(
        tx.amount for tx in transactions
        if tx.type == "income"
        and tx.date.year == analysis_date.year
        and tx.date.month == analysis_date.month
    )
    effective_income = month_income if month_income > 0 else profile.expected_salary

    # static baseline (drives pace / pct_used)
    weekly_limit = profile.monthly_spending_goal / 4.3 if profile.monthly_spending_goal > 0 else 0.0
    pace = week_spending / weekly_limit if weekly_limit > 0 else 0.0

    cat_map: dict[str, float] = defaultdict(float)
    for tx in week_expenses:
        cat_name = tx.category.name
        # Strict category isolation: only count categories that belong to this user.
        if user_categories and cat_name not in user_categories:
            continue
        cat_map[cat_name] += tx.amount
    _lang_key = profile.language.upper()
    _fallback = _TOP_CAT_FALLBACK.get(_lang_key, _TOP_CAT_FALLBACK["EN"])
    raw_top = max(cat_map, key=lambda k: cat_map[k]) if cat_map else _fallback
    top_cat = raw_top[:16] if len(raw_top) > 16 else raw_top

    pct_used = int(round(pace * 100))
    pct_over = max(0, pct_used - 100)
    top_cat_spend = sum(tx.amount for tx in week_expenses if tx.category.name == top_cat)
    potential_saving = round(top_cat_spend * 0.15, 2)
    saving_viable = top_cat_spend >= _SAVINGS_THRESHOLD and potential_saving > 0.0

    lang = profile.language.upper()
    day_names = _DAY_NAMES.get(lang, _DAY_NAMES["EN"])
    day_name = day_names[analysis_date.isoweekday() - 1]

    return {
        "pct_over": pct_over,
        "pct_used": pct_used,
        "top_cat": top_cat,
        "effective_income": _fmt(effective_income),
        "goal": _fmt(profile.monthly_spending_goal),
        "currency": profile.currency,
        "potential_saving": _fmt(potential_saving),
        "saving_viable": saving_viable,
        "predicted_balance": _fmt(predicted_balance),
        "day_name": day_name,
    }


def generate_nudge(
    tier: str,
    risk_flags: list[str],
    profile: UserProfile,
    transactions: list[TransactionItem],
    analysis_date: date,
    predicted_balance: float,
    user_categories: list[str] | None = None,
    predicted_savings_balance: float = 0.0,
    salary_cycle: SalaryCycleInfo | None = None,
) -> str:
    ctx = _build_context(transactions, profile, analysis_date, predicted_balance, user_categories=user_categories)
    lang = profile.language.upper()
    lang_templates = _TEMPLATES.get(lang, _TEMPLATES["EN"])

    # ── Cycle-aware proactive nudges (highest priority) ───────────────────
    if salary_cycle is not None and "no_income" not in risk_flags:
        # Nudge: savings dipped last cycle (previous_savings proxy: predicted < savings_limit)
        savings_dipped = (
            predicted_savings_balance < salary_cycle.savings_limit * 0.9
            and salary_cycle.savings_limit > 0
            and random.random() < 0.50
        )
        if savings_dipped:
            pool = _SAVINGS_DIP.get(lang, _SAVINGS_DIP["EN"])
            result = random.choice(pool)
            return result if len(result) <= 99 else result[:99] + "…"

        # Nudge: fixed expenses are high (>60% of total income)
        total_fixed = salary_cycle.fixed_needs_total + salary_cycle.fixed_wants_total
        if salary_cycle.total_income > 0:
            fixed_pct = int(round(total_fixed / salary_cycle.total_income * 100))
            if fixed_pct >= 60 and random.random() < 0.40:
                pool = _HIGH_FIXED.get(lang, _HIGH_FIXED["EN"])
                template = random.choice(pool)
                try:
                    result = template.format(pct=fixed_pct)
                    return result if len(result) <= 99 else result[:99] + "…"
                except KeyError:
                    pass

    # ── Savings milestone: fire ~30% of the time ──────────────────────────
    savings_threshold = max(300.0, profile.monthly_spending_goal * 2)
    if (
        predicted_savings_balance >= savings_threshold
        and "no_income" not in risk_flags
        and random.random() < 0.30
    ):
        milestone_pool = _SAVINGS_MILESTONE.get(lang, _SAVINGS_MILESTONE["EN"])
        template = random.choice(milestone_pool)
        try:
            result = template.format(savings=_fmt(predicted_savings_balance), currency=profile.currency)
            return result if len(result) <= 99 else result[:99] + "…"
        except KeyError:
            pass

    if "no_income" in risk_flags and profile.expected_salary == 0:
        key = "no_income_logged"
    elif "expenses_exceed_income" in risk_flags and predicted_balance < 0:
        key = "predicted_shortfall"
    elif tier in lang_templates:
        key = tier
    else:
        key = "on_track"

    if key == "pacing_good" and not ctx.get("saving_viable", True):
        key = "pacing_good_start"

    template = random.choice(lang_templates[key])
    try:
        result = template.format(**ctx)
    except KeyError:
        result = random.choice(lang_templates["on_track"]).format(**ctx)
    return result if len(result) <= 99 else result[:99] + "…"
