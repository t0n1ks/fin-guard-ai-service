"""Daily-quota lines — what the cow / star say once today's two jokes / two
facts have been served (the cap that makes the 90-day no-repeat real).
``when`` is the kind: "joke" (the cow) or "fact" (the star). Append-only.
"""
from __future__ import annotations

from app.data.pool.model import Item, U

QUOTA: list[Item] = [
    U("Q001", "That's today's two cow jokes — union rules. More tomorrow! 🐄",
      "Das waren die zwei Kuh-Witze für heute — Gewerkschaftsregel. Morgen mehr! 🐄",
      "На сегодня две шутки от коровы — профсоюзные правила. Завтра ещё! 🐄",
      "На сьогодні два жарти від корови — профспілкові правила. Завтра ще! 🐄", when="joke"),
    U("Q002", "The cow has clocked out for the day. Fresh jokes tomorrow.",
      "Die Kuh hat Feierabend. Frische Witze gibt's morgen.",
      "Корова ушла с работы. Свежие шутки — завтра.",
      "Корова пішла з роботи. Свіжі жарти — завтра.", when="joke"),
    U("Q003", "Joke quota reached! The cow is rehearsing new material for tomorrow.",
      "Witz-Kontingent erreicht! Die Kuh probt schon neues Material für morgen.",
      "Лимит шуток исчерпан! Корова уже репетирует новый материал на завтра.",
      "Ліміт жартів вичерпано! Корова вже репетирує новий матеріал на завтра.", when="joke"),
    U("Q004", "No more moo-jokes today — quality over quantity. 😄",
      "Heute keine Muh-Witze mehr — Qualität vor Quantität. 😄",
      "Больше никаких му-шуток сегодня — качество важнее количества. 😄",
      "Більше жодних му-жартів сьогодні — якість важливіша за кількість. 😄", when="joke"),
    U("Q005", "That's today's two star facts. The stars are recharging — more tomorrow! ✨",
      "Das waren die zwei Sternenfakten für heute. Die Sterne laden auf — morgen mehr! ✨",
      "На сегодня два факта от звёзд. Звёзды подзаряжаются — завтра ещё! ✨",
      "На сьогодні два факти від зірок. Зорі підзаряджаються — завтра ще! ✨", when="fact"),
    U("Q006", "Fact quota reached. Let today's two sink in. 🌟",
      "Fakten-Kontingent erreicht. Lass die zwei von heute sacken. 🌟",
      "Лимит фактов на сегодня исчерпан. Пусть сегодняшние два уложатся. 🌟",
      "Ліміт фактів на сьогодні вичерпано. Хай сьогоднішні два вкладуться. 🌟", when="fact"),
    U("Q007", "The stars are out of fresh facts for today. New ones tomorrow.",
      "Die Sterne haben für heute keine frischen Fakten mehr. Neue gibt's morgen.",
      "У звёзд на сегодня закончились свежие факты. Новые — завтра.",
      "У зірок на сьогодні закінчилися свіжі факти. Нові — завтра.", when="fact"),
    U("Q008", "Two facts a day keeps boredom away. Come back tomorrow! ✨",
      "Zwei Fakten am Tag halten die Langeweile fern. Komm morgen wieder! ✨",
      "Два факта в день — и скуке не место. Возвращайся завтра! ✨",
      "Два факти на день — і нудьзі не місце. Повертайся завтра! ✨", when="fact"),
]
