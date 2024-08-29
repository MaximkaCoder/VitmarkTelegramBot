from telebot import TeleBot, types

bot = TeleBot('6262235122:AAEzJsBDtRGRb8OHXG3IN8S6_7BecWKZt7c')

# Пример данных - номера автомобилей
vehicle_numbers = [
    "AA1111AA", "BB2222BB", "CC3333CC", "DD4444DD",
    "EE5555EE", "FF6666FF", "GG7777GG", "HH8888HH",
    "II9999II", "JJ0000JJ", "KK1111KK", "LL2222LL",
    "MM3333MM", "NN4444NN", "OO5555OO", "PP6666PP",
    "MM3333MM", "NN4444NN", "OO5555OO", "PP6666PP",
    "MM3333MM", "NN4444NN", "OO5555OO", "PP6666PP",
    "MM3333MM", "NN4444NN", "OO5555OO", "PP6666PP",
    "MM3333MM", "NN4444NN", "OO5555OO", "PP6666PP"
]

vehicles_per_page = 12  # По 9 номеров на странице (3 ряда по 3 кнопки)
total_pages = (len(vehicle_numbers) - 1) // vehicles_per_page + 1

def create_inline_keyboard(page_num):
    keyboard = types.InlineKeyboardMarkup(row_width=4)

    start_idx = (page_num - 1) * vehicles_per_page
    end_idx = start_idx + vehicles_per_page
    current_page_vehicles = vehicle_numbers[start_idx:end_idx]

    # Создаем кнопки с номерами автомобилей
    for i in range(0, len(current_page_vehicles), 3):
        row_buttons = [
            types.InlineKeyboardButton(text=current_page_vehicles[i], callback_data=f'vehicle_{current_page_vehicles[i]}'),
            types.InlineKeyboardButton(text=current_page_vehicles[i + 1], callback_data=f'vehicle_{current_page_vehicles[i + 1]}') if i + 1 < len(current_page_vehicles) else None,
            types.InlineKeyboardButton(text=current_page_vehicles[i + 2], callback_data=f'vehicle_{current_page_vehicles[i + 2]}') if i + 2 < len(current_page_vehicles) else None,
        ]
        keyboard.add(*[btn for btn in row_buttons if btn])  # Добавляем только не None кнопки

    # Добавляем кнопки для перелистывания страниц внизу
    navigation_buttons = []
    if page_num > 1:
        navigation_buttons.append(types.InlineKeyboardButton(text='⬅️', callback_data=f'prev_{page_num}'))
    if page_num < total_pages:
        navigation_buttons.append(types.InlineKeyboardButton(text='➡️', callback_data=f'next_{page_num}'))

    if navigation_buttons:
        keyboard.add(*navigation_buttons)

    return keyboard

@bot.message_handler(commands=['start'])
def send_welcome(message):
    page_num = 1  # Начинаем с первой страницы
    text = f"Страница {page_num}/{total_pages}:\nВыберите номер автомобиля:"
    keyboard = create_inline_keyboard(page_num)
    bot.send_message(message.chat.id, text, reply_markup=keyboard)
    bot.send_message(message.chat.id, str(message.chat.id), reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('vehicle_') or call.data.startswith('prev_') or call.data.startswith('next_'))
def callback_inline(call):
    if call.message:
        current_page = int(call.data.split('_')[1])

        if call.data.startswith('prev_') and current_page > 1:
            new_page = current_page - 1
        elif call.data.startswith('next_') and current_page < total_pages:
            new_page = current_page + 1
        else:
            new_page = current_page

        text = f"Страница {new_page}/{total_pages}:\nВыберите номер автомобиля:"
        keyboard = create_inline_keyboard(new_page)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=keyboard)

bot.polling()
