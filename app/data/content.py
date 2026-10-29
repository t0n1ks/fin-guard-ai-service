"""Greetings for the UFO (time-of-day and visit-mood). Jokes, facts, tips,
encouragements and every other line live in app/data/pool/."""

GREETINGS: dict[str, dict[str, list[str]]] = {
    "EN": {
        "morning": [
            "Good morning! ☀️ Fresh day, fresh budget. Let's make it count.",
            "Morning! Best time to check your finances before the day gets busy.",
            "Rise and track! 🌅 Ready to see where the money flows today?",
        ],
        "afternoon": [
            "Afternoon check-in! 🛸 Budget holding steady so far?",
            "Mid-day orbit stable. How's the spending looking? 📊",
            "Hey! Don't forget to log that lunch. Small entries, big picture.",
        ],
        "evening": [
            "Good evening! 🌙 A good moment to review today's spending.",
            "Day's almost done — any surprise expenses to log? 🌆",
            "Evening. If you tracked today, you're already ahead of most people.",
        ],
        "night": [
            "Still up? 🌠 Late-night purchases hit different in the morning.",
            "Night mode. Quick thought: tomorrow's budget starts with tonight's choices.",
            "Burning the midnight oil? 🦉 Log anything before you forget.",
        ],
    },
    "RU": {
        "morning": [
            "Доброе утро! ☀️ Новый день — новый бюджет. Сделаем его продуктивным.",
            "Утро! Лучшее время проверить финансы, пока день не закрутил.",
            "Подъём и учёт! 🌅 Посмотрим, куда пойдут деньги сегодня.",
        ],
        "afternoon": [
            "Дневная проверка! 🛸 Бюджет держится в норме?",
            "Середина дня — орбита стабильна. Как расходы? 📊",
            "Эй! Не забудь занести обед. Мелкие записи — большая картина.",
        ],
        "evening": [
            "Добрый вечер! 🌙 Самое время подвести итоги дня.",
            "День почти позади — есть неожиданные траты? 🌆",
            "Вечер. Раз ты трекал сегодня — ты уже впереди большинства.",
        ],
        "night": [
            "Ещё не спишь? 🌠 Ночные покупки иначе смотрятся утром.",
            "Ночной режим. Мысль: завтрашний бюджет начинается с сегодняшних решений.",
            "Полночный марафон? 🦉 Занеси всё, пока не забыл.",
        ],
    },
    "UA": {
        "morning": [
            "Доброго ранку! ☀️ Новий день — новий бюджет. Зробимо його продуктивним.",
            "Ранок! Найкращий час перевірити фінанси, поки день не розкрутився.",
            "Підйом і облік! 🌅 Подивимось, куди підуть гроші сьогодні.",
        ],
        "afternoon": [
            "Денна перевірка! 🛸 Бюджет тримається в нормі?",
            "Середина дня — орбіта стабільна. Як витрати? 📊",
            "Гей! Не забудь внести обід. Малі записи — велика картина.",
        ],
        "evening": [
            "Добрий вечір! 🌙 Найкращий момент підбити підсумок дня.",
            "День майже позаду — є несподівані витрати? 🌆",
            "Вечір. Якщо ти відстежував сьогодні — ти вже попереду більшості.",
        ],
        "night": [
            "Ще не спиш? 🌠 Нічні покупки інакше виглядають вранці.",
            "Нічний режим. Думка: завтрашній бюджет починається з рішень сьогодні.",
            "Нічний марафон? 🦉 Внеси все, поки не забув.",
        ],
    },
    "DE": {
        "morning": [
            "Guten Morgen! ☀️ Neuer Tag, neues Budget. Lass es zählen.",
            "Morgen! Die beste Zeit, Finanzen zu prüfen, bevor der Tag losgeht.",
            "Aufstehen und tracken! 🌅 Wohin fließt das Geld heute?",
        ],
        "afternoon": [
            "Mittags-Check! 🛸 Budget noch im grünen Bereich?",
            "Mittagsorbit stabil. Wie sehen die Ausgaben aus? 📊",
            "Hey! Mittagessen nicht vergessen einzutragen. Klein, aber wichtig.",
        ],
        "evening": [
            "Guten Abend! 🌙 Zeit, den heutigen Tag auszuwerten.",
            "Tag fast vorbei — gab es Überraschungsausgaben? 🌆",
            "Abend. Wer heute tracked, ist schon weiter als die meisten.",
        ],
        "night": [
            "Noch wach? 🌠 Nächtliche Käufe sehen morgens anders aus.",
            "Nachtmodus. Gedanke: Das Budget von morgen beginnt mit heutigen Entscheidungen.",
            "Mitternachts-Session? 🦉 Alles eintragen, solange es noch frisch ist.",
        ],
    },
}

CHEERFUL_GREETINGS: dict[str, list[str]] = {
    "EN": [
        "Hey, you're back! ✨ Missed you — ready to keep that streak alive?",
        "Three days strong! 🌟 Your budget and I have been waiting.",
        "Look who's back again! The numbers missed you. Let's check in. 🚀",
        "Streak unlocked! ⭐ Consistency is the secret weapon — you've got it.",
        "Welcome back, frequent flyer! 🛸 Your finances are looking forward to the update.",
    ],
    "RU": [
        "О, снова ты! ✨ Ждал тебя — стрик продолжается!",
        "Три дня подряд! 🌟 Твой бюджет скучал.",
        "Снова вместе! Цифры рады. Давай сверим данные. 🚀",
        "Стрик разблокирован! ⭐ Постоянство — твоё тайное оружие.",
        "Снова здесь, частый гость! 🛸 Финансы ждут твоих новостей.",
    ],
    "UA": [
        "О, знову ти! ✨ Чекав на тебе — стрік продовжується!",
        "Три дні поспіль! 🌟 Твій бюджет скучив.",
        "Знову разом! Цифри раді. Звірмо дані. 🚀",
        "Стрік розблоковано! ⭐ Сталість — твоя таємна зброя.",
        "Знову тут, частий гість! 🛸 Фінанси чекають твоїх новин.",
    ],
    "DE": [
        "Hey, du bist wieder da! ✨ Ich habe auf dich gewartet — Streak weiterführen?",
        "Drei Tage in Folge! 🌟 Dein Budget und ich haben auf dich gewartet.",
        "Schau, wer wieder da ist! Die Zahlen haben dich vermisst. Check-in! 🚀",
        "Streak freigeschaltet! ⭐ Beständigkeit ist die Geheimwaffe — du hast sie.",
        "Willkommen zurück, Stammgast! 🛸 Deine Finanzen freuen sich auf die Aktualisierung.",
    ],
}

GRUMPY_GREETINGS: dict[str, list[str]] = {
    "EN": [
        "Oh. You're BACK. After all this time. My sensors nearly went offline. 🙄",
        "Three days without a check-in? My data hunger is real. Don't leave like that again.",
        "Look who finally returned to orbit. 🛸 I've been calculating your budget alone. Rude.",
        "Your finances missed you. Or maybe they didn't notice. Hard to tell without data.",
        "Back from the void? 🌌 Your budget survived — barely. We need to talk.",
    ],
    "RU": [
        "О. Ты ВЕРНУЛСЯ. Наконец-то. Мои сенсоры почти отключились. 🙄",
        "Три дня без отметки? Моя жажда данных реальна. Больше так не пропадай.",
        "Смотрите, кто вернулся на орбиту. 🛸 Я считал твой бюджет в одиночку. Невежливо.",
        "Твои финансы скучали. Или нет. Без данных сложно сказать.",
        "Из пустоты? 🌌 Бюджет выжил — с трудом. Нам надо поговорить.",
    ],
    "UA": [
        "О. Ти ПОВЕРНУВСЯ. Нарешті. Мої сенсори мало не відключились. 🙄",
        "Три дні без відмітки? Моя спрага даних реальна. Більше так не зникай.",
        "Дивіться, хто повернувся на орбіту. 🛸 Я рахував твій бюджет сам. Нечемно.",
        "Твої фінанси скучали. Або ні. Без даних важко сказати.",
        "З пустоти? 🌌 Бюджет вижив — ледве. Нам потрібно поговорити.",
    ],
    "DE": [
        "Oh. Du bist ZURÜCK. Nach all dieser Zeit. Meine Sensoren waren fast offline. 🙄",
        "Drei Tage ohne Check-in? Mein Datenhunger ist real. Verschwinde nicht wieder so.",
        "Sieh an, wer wieder in die Umlaufbahn zurückgekehrt ist. 🛸 Ich habe dein Budget alleine berechnet. Unhöflich.",
        "Deine Finanzen haben dich vermisst. Oder auch nicht. Schwer zu sagen ohne Daten.",
        "Aus der Leere zurück? 🌌 Dein Budget hat es kaum überlebt. Wir müssen reden.",
    ],
}
