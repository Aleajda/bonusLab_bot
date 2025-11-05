# Конфигурация Telegram и каналов

api_id = 23247724
api_hash = '3cc500af4e4261a9e8d4545ba6b2448e'
bot_token = '8309282218:AAEm05CWWPobe8ZfT0onXX1FGy66pP--YYg'

# ID владельца и канал для публикаций
owner_id = 398958635
target_channel = '@bonuslab_ru'

# Каналы, которые парсим
channels_to_parse = [
    '@big_bonus_wb',
    '@Big_Bonuss',
    '@dengivshapke',
    '@ishopper',
    '@skidki',
    '@alikzbs_aliexpress',
    '@ozon_skidky',
    '@AleajdaTest'
]

# Фразы, которые нужно вырезать из текста
blacklist_words = [
    '💝 Скидочный бот',
    'http://t.me/Besplatno_skidki_bot',
    '@skidki',
    '''💝 Скидочный  бот (http://t.me/Besplatno_skidki_bot)
🎁 @skidki''',
    'Скидочный бот',
    '@Ozon_skidky',
    '💝 Скидочный бот (http://t.me/Besplatno_skidki_bot)'
]

