# Конфигурация Telegram и каналов

api_id = 24669542
api_hash = '98c1f90abd5beff27c296f8527a08e9a'
bot_token = '8309282218:AAEm05CWWPobe8ZfT0onXX1FGy66pP--YYg'



# ID владельца и канал для публикаций
owner_id = 6890932879
target_channel = '@bonuslab_ru'

# Каналы, которые парсим
channels_to_parse = [
    '@big_bonus_wb',
    '@Big_Bonuss',
    '@ishopper',
    '@skidki',
    # '@alikzbs_aliexpress',
    '@ozon_skidky',
    '@AleajdaTest',
    '@wowskidka1',
    '@skidki_piter_moskva',
    '@aliexpress_myskidka',
    # '@burostyle',
    # '@nedorogo_na_wb',
    # '@wbrchik',
    '@skidkarai',
    '@wb_skidkamam',
    '@vandroukiru',
]

# Фразы, которые нужно вырезать из текста
blacklist_words = [
    '💝 Скидочный бот',
    'http://t.me/Besplatno_skidki_bot',
    '🎁 @skidki',
    'Скидочный бот',
    '@Ozon_skidky',
    '💝 Скидочный бот (http://t.me/Besplatno_skidki_bot)',
    'Секретные находки➡️@TANJARUS',
    'Секретные находки',
    '@TANJARUS',
    'подписаться | откуда? с вб',
    'подписаться | откуда? с вб (https://t.me/+zBln_Toslek2N2Iy)',
    '✅ Больше находок wb с артикулами тут  (https://t.me/burostyle)',
    '✅ Больше находок wb с артикулами тут',
    'Больше находок wb с артикулами тут',
    'Недорогой WB и OZON (https://t.me/+39v8PiWvXKQxOTI6)',
    'Недорогой WB и OZON',
    'Секретные находки➡️',
    '@TANJARUS',
    'чата',
    'чат',
]



# Режимы работы
AUTO_MODE = True  # если True — посты публикуются без проверки владельцем

# Стоп-слова: если одно из них встречается в тексте поста — он автоматически отклоняется
STOP_WORDS = [
    'казино', 'ставки', '1win',
    'вулкан', 'крипта', 'ставь',
    'бесплатные деньги', 'реклама',
    'Youtube', 'TikTok', 'VK',
    'Конкурс', 'конкурс', 'ООО',
    '+79', '89', 'блог', 'БЛОГ',
    'спасибо', 'розыгрыш', 'подписаться',
    'подпишись', 'подпишитесь', 'участвую',
    'итоги', 'сертификат', 'кредит',
    'Столото', 'столото', 'выигрывай',
    'канал', 'ссылка на канал', 'ВСЕ ПРОМОКОДЫ ЗДЕСЬ',
    'Распаковка', 'автор', 'видео',
    'wowskidka', 'Закрытый клуб', 'СберПрайм',
    'бот', 'wowskidka', 'урвал', 'Сбер',
    'кредитка', 'оформ',
]

SEND_LOGS = False     # Включает/отключает уведомления владельцу о публикации и отклонении


ALERT_WORDS = [
    "кофе"
]

ALERT_TO = 398958635