"""Facts — the shining star's. Append-only (see model.py).

Accurate and evergreen: no prices, rates or "this year" figures that date.
Any calculation states its assumption; a specific claim names its source in
the comment above it.
"""
from __future__ import annotations

from app.data.pool.model import Item, U

FACTS: list[Item] = [
    # Elizabeth Warren & Amelia Warren Tyagi, "All Your Worth" (2005).
    U("F001",
      "The 50/30/20 rule — needs, wants, savings — was popularised by Elizabeth Warren and her daughter in the 2005 book 'All Your Worth'.",
      "Die 50/30/20-Regel — Bedarf, Wünsche, Sparen — machte Elizabeth Warren mit ihrer Tochter 2005 im Buch „All Your Worth“ bekannt.",
      "Правило 50/30/20 — нужды, желания, сбережения — популяризовали Элизабет Уоррен и её дочь в книге «All Your Worth» (2005).",
      "Правило 50/30/20 — потреби, бажання, заощадження — популяризували Елізабет Воррен і її донька в книжці «All Your Worth» (2005)."),
    # Arithmetic approximation (72 / r).
    U("F002",
      "Rule of 72: divide 72 by the yearly return in % to see roughly how many years money takes to double. At 6%, about 12 years.",
      "72er-Regel: 72 geteilt durch die Jahresrendite in % ergibt grob die Jahre bis zur Verdopplung. Bei 6 % etwa 12 Jahre.",
      "Правило 72: раздели 72 на годовую доходность в % — получишь примерное число лет до удвоения. При 6% — около 12 лет.",
      "Правило 72: поділи 72 на річну дохідність у % — отримаєш приблизну кількість років до подвоєння. За 6% — близько 12 років."),
    # S&P Dow Jones Indices, SPIVA scorecards (published since 2002).
    U("F003",
      "S&P's long-running SPIVA reports find that most actively managed funds trail their benchmark index over 10+ year periods.",
      "Die langjährigen SPIVA-Berichte von S&P zeigen: Die meisten aktiv gemanagten Fonds liegen über 10+ Jahre hinter ihrem Index.",
      "Многолетние отчёты S&P SPIVA показывают: большинство активно управляемых фондов на горизонте 10+ лет отстают от своего индекса.",
      "Багаторічні звіти S&P SPIVA показують: більшість активно керованих фондів на горизонті 10+ років відстають від свого індексу."),
    # 100 / 1.03^10 ≈ 74.4.
    U("F004",
      "At 3% inflation a year, €100 buys only about €74 worth of today's goods after 10 years.",
      "Bei 3 % Inflation pro Jahr kaufen 100 € nach 10 Jahren nur noch Waren im heutigen Wert von etwa 74 €.",
      "При инфляции 3% в год на 100 € через 10 лет можно купить лишь около 74 € в сегодняшних ценах.",
      "За інфляції 3% на рік за 100 € через 10 років можна купити лише близько 74 € у сьогоднішніх цінах."),
    # Future value of monthly deposits at 7%/yr, compounded monthly: 480 months → ≈262k, 360 months ×2 → ≈244k.
    U("F005",
      "At a 7% yearly return, €100 a month from 25 to 65 grows to about €262,000; €200 a month from 35 reaches only about €244,000.",
      "Bei 7 % Rendite pro Jahr werden aus 100 € im Monat von 25 bis 65 rund 262.000 €; 200 € ab 35 bringen nur etwa 244.000 €.",
      "При доходности 7% в год 100 € в месяц с 25 до 65 лет дают около 262 000 €, а 200 € с 35 лет — лишь около 244 000 €.",
      "За дохідності 7% на рік 100 € на місяць із 25 до 65 років дають близько 262 000 €, а 200 € із 35 — лише близько 244 000 €."),
    U("F006",
      "Dollar-cost averaging means investing a fixed amount at regular intervals — so you automatically buy more when prices are low.",
      "Cost-Average-Effekt: Wer regelmäßig einen festen Betrag anlegt, kauft bei niedrigen Kursen automatisch mehr Anteile.",
      "Усреднение стоимости — это регулярные вложения фиксированной суммы: при низких ценах ты автоматически покупаешь больше.",
      "Усереднення вартості — це регулярні вкладення фіксованої суми: за низьких цін ти автоматично купуєш більше."),
    U("F007",
      "Diversification works because different assets rarely all fall at once: spreading money out lowers risk without picking winners.",
      "Diversifikation wirkt, weil verschiedene Anlagen selten alle zugleich fallen: Streuung senkt das Risiko ohne Gewinner-Raten.",
      "Диверсификация работает, потому что разные активы редко падают разом: распределение снижает риск без угадывания победителей.",
      "Диверсифікація працює, бо різні активи рідко падають разом: розподіл знижує ризик без вгадування переможців."),
    # (1.05 / 1.06)^30 ≈ 0.75 → about a quarter lost to the fee.
    U("F008",
      "Fees compound too: at a 6% return, a 1% yearly fee takes roughly a quarter of the final balance over 30 years.",
      "Auch Gebühren wirken mit Zinseszins: Bei 6 % Rendite kostet 1 % Jahresgebühr über 30 Jahre etwa ein Viertel des Endbetrags.",
      "Комиссии тоже работают со сложным процентом: при доходности 6% годовая комиссия 1% за 30 лет съедает около четверти итога.",
      "Комісії теж працюють зі складним відсотком: за дохідності 6% річна комісія 1% за 30 років з’їдає близько чверті підсумку."),
    # Arithmetic (72 / 3).
    U("F009",
      "The Rule of 72 works for inflation too: at 3% a year, prices roughly double in 24 years (72 ÷ 3).",
      "Die 72er-Regel gilt auch für Inflation: Bei 3 % pro Jahr verdoppeln sich die Preise in etwa 24 Jahren (72 ÷ 3).",
      "Правило 72 работает и для инфляции: при 3% в год цены удваиваются примерно за 24 года (72 ÷ 3).",
      "Правило 72 працює й для інфляції: за 3% на рік ціни подвоюються приблизно за 24 роки (72 ÷ 3)."),
    # Bitcoin protocol supply schedule; 2140 is the widely cited estimate.
    U("F010",
      "Bitcoin's code caps its supply at 21 million coins; the last tiny fractions are expected to be mined around the year 2140.",
      "Der Bitcoin-Code begrenzt die Menge auf 21 Millionen Coins; die letzten Bruchteile sollen etwa im Jahr 2140 geschürft werden.",
      "Код биткоина ограничивает эмиссию 21 миллионом монет; последние доли, по расчётам, добудут примерно к 2140 году.",
      "Код біткоїна обмежує емісію 21 мільйоном монет; останні частки, за розрахунками, видобудуть приблизно до 2140 року."),
    # Laszlo Hanyecz, BitcoinTalk forum, 22 May 2010.
    U("F011",
      "On 22 May 2010 a programmer paid 10,000 BTC for two pizzas — now celebrated every year as Bitcoin Pizza Day.",
      "Am 22. Mai 2010 zahlte ein Programmierer 10.000 BTC für zwei Pizzen — heute jedes Jahr als Bitcoin Pizza Day gefeiert.",
      "22 мая 2010 года программист заплатил 10 000 BTC за две пиццы — теперь этот день отмечают как Bitcoin Pizza Day.",
      "22 травня 2010 року програміст заплатив 10 000 BTC за дві піци — тепер цей день відзначають як Bitcoin Pizza Day."),
    # Dutch East India Company (VOC), 1602; Amsterdam exchange — e.g. Britannica.
    U("F012",
      "The Dutch East India Company, founded in 1602, is widely seen as the first company whose shares the public could trade on an exchange.",
      "Die Niederländische Ostindien-Kompanie (1602) gilt als erstes Unternehmen, dessen Aktien die Öffentlichkeit an einer Börse handelte.",
      "Голландская Ост-Индская компания (1602) считается первой компанией, чьи акции публика могла покупать и продавать на бирже.",
      "Нідерландська Ост-Індська компанія (1602) вважається першою компанією, чиї акції публіка могла купувати й продавати на біржі."),
    # Song-dynasty jiaozi, 11th century — e.g. Britannica, "paper money".
    U("F013",
      "The first government-backed paper money, the jiaozi, appeared in China under the Song dynasty in the 11th century.",
      "Das erste staatlich gedeckte Papiergeld, das Jiaozi, entstand im 11. Jahrhundert in China unter der Song-Dynastie.",
      "Первые государственные бумажные деньги — цзяоцзы — появились в Китае при династии Сун в XI веке.",
      "Перші державні паперові гроші — цзяоцзи — з’явилися в Китаї за династії Сун у XI столітті."),
    # Vanguard's First Index Investment Trust, 1976 ("Bogle's Folly").
    U("F014",
      "The first index fund for everyday investors was launched by John Bogle's Vanguard in 1976. Critics called it 'Bogle's Folly'.",
      "Den ersten Indexfonds für Privatanleger brachte John Bogles Vanguard 1976 heraus. Kritiker nannten ihn „Bogle’s Folly“.",
      "Первый индексный фонд для частных инвесторов запустил Vanguard Джона Богла в 1976 году. Критики прозвали его «авантюрой Богла».",
      "Перший індексний фонд для приватних інвесторів запустив Vanguard Джона Богла 1976 року. Критики прозвали його «авантюрою Богла»."),
    # Standard management accounting.
    U("F015",
      "Break-even point = fixed costs ÷ (price − variable cost per unit). Sell fewer and the business loses money; sell more and it profits.",
      "Break-even-Punkt = Fixkosten ÷ (Preis − variable Kosten pro Stück). Darunter macht das Geschäft Verlust, darüber Gewinn.",
      "Точка безубыточности = постоянные затраты ÷ (цена − переменные затраты на единицу). Продашь меньше — убыток, больше — прибыль.",
      "Точка беззбитковості = постійні витрати ÷ (ціна − змінні витрати на одиницю). Продаси менше — збиток, більше — прибуток."),
]
