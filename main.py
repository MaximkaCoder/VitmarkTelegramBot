import time
import requests
import telebot
import pyodbc
import re
import dic
import configparser
import threading
from telebot import types
from datetime import datetime
import createExcel


config = configparser.ConfigParser()
config.read('config.ini')

bot = telebot.TeleBot(config['DATABASE']['token'])

server = config['DATABASE']['server']
database = config['DATABASE']['database']
username = config['DATABASE']['username']
password = config['DATABASE']['password']

connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
conn = pyodbc.connect(connection_string)
cursor = conn.cursor()
db_lock = threading.Lock()
user_data = {}
user_steps = {}
admins = [601442777, 7178651151, 5786418791, 7244779387] # Березной, Смаль, Афонькина, Биндич
group_id = "-1001958723261"
# group_id = "-4584764861"


# Функция для создания таблицы, если она не существует
def create_table_if_not_exists():
    create_table_query = """
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_NAME = 'Data'
    )
    BEGIN
        CREATE TABLE Data (
            ttn NVARCHAR(10),
            ttn_date DATE,
            fullName NVARCHAR(70),
            typeDrive NVARCHAR(20),
            car NVARCHAR(20),
            car_number NVARCHAR(8),
            trailer_number NVARCHAR(20),
            start_time DATETIME,
            end_time DATETIME,
            departure_time DATETIME,
            field_code NVARCHAR(10),
            field NVARCHAR(30),
            hybrid_code NVARCHAR(10),
            hybrid NVARCHAR(20),
            quantity INT,
            processed BIT,
            owner NVARCHAR(50),
            PRIMARY KEY (ttn, ttn_date, field_code, hybrid_code)
        );
    END
    """
    create_table_users = """
        IF NOT EXISTS (
            SELECT * FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = 'Users'
        )
        BEGIN
            CREATE TABLE Users (
                userID BIGINT,
                PRIMARY KEY (userID)
            );
        END
    """
    cursor.execute(create_table_query)
    cursor.execute(create_table_users)
    conn.commit()

def validate_time(tm):
    pattern = r'^\d{1,2}\.\d{2}$'
    if re.match(pattern, tm):
        hours, minutes = map(int, tm.split('.'))
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return True
    return False


def check_steps(message, step):
    if step not in user_steps[message.chat.id]['step'] and step - user_steps[message.chat.id]['step'][-1] == 1:
        return True
    else:
        return False


@bot.message_handler(commands=['start'])
def start(message):
    create_table_if_not_exists()
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    user_name = message.from_user.username

    cursor.execute("SELECT * FROM Users WHERE userID = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        markup = types.InlineKeyboardMarkup()
        accept_button = types.InlineKeyboardButton("Принять", callback_data=f"accept_{user_id}")
        reject_button = types.InlineKeyboardButton("Отклонить", callback_data=f"reject_{user_id}")
        markup.add(accept_button, reject_button)

        for admin in admins:
            bot.send_message(admin, f"Новый пользователь:\nID: {user_id}\nUsername: {user_name}\nИмя: {first_name}",
                             reply_markup=markup)

        bot.send_message(message.chat.id, "Ваш запрос отправлен администратору! Ожидайте!")
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

        if user_id in dic.superAdmin_data or user_id in dic.master_data:
            add_record_button = types.KeyboardButton("ДОБАВИТЬ ЗАПИСЬ")
            markup.add(add_record_button)

        if user_id in dic.superAdmin_data or user_id not in dic.master_data:
            add_record_button = types.KeyboardButton("СГЕНЕРИРОВАТЬ ОТЧЁТ")
            markup.add(add_record_button)

        if user_id not in dic.superAdmin_data and user_id not in dic.master_data:
            bot.send_message(message.chat.id, "Нажмите 'СГЕНЕРИРОВАТЬ ОТЧЁТ', чтобы начать.", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, "Нажмите 'ДОБАВИТЬ ЗАПИСЬ', чтобы начать.", reply_markup=markup)


@bot.message_handler(commands=['get'])
def get_group_id(message):
    bot.send_message(message.chat.id, message.chat.id)


@bot.message_handler(func=lambda message: message.text == "ДОБАВИТЬ ЗАПИСЬ")
def handle_add_record(message):
    create_table_if_not_exists()
    user_data[message.chat.id] = {}
    user_steps[message.chat.id] = {}
    user_steps[message.chat.id]['step'] = []
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    add_record_button = types.KeyboardButton("ОТМЕНИТЬ ДОБАВЛЕНИЕ ЗАПИСИ")
    markup.add(add_record_button)
    bot.send_message(message.chat.id, "Введите ТТН (например 111 или 1111):", reply_markup=markup)
    bot.register_next_step_handler(message, get_ttn)


@bot.message_handler(func=lambda message: message.text == "СГЕНЕРИРОВАТЬ ОТЧЁТ")
def generate_excel(message):
    try:
        df = createExcel.get_data_from_db(conn)  # Получаем данные из базы данных
        excel_file = createExcel.create_excel(df)  # Создаем Excel файл

        bot.send_document(
            message.chat.id,
            excel_file,
            caption="Ваши данные в формате Excel",
            visible_file_name="report.xlsx"
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка: {e}")


@bot.message_handler(func=lambda message: message.text == "ОТМЕНИТЬ ДОБАВЛЕНИЕ ЗАПИСИ")
def reset(message):
    if message.chat.id in user_data:
        user_data.pop(message.chat.id)

    bot.send_message(message.chat.id, "Добавление записи отменено!")
    user_id = message.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    if user_id in dic.superAdmin_data or user_id in dic.master_data:
        add_record_button = types.KeyboardButton("ДОБАВИТЬ ЗАПИСЬ")
        markup.add(add_record_button)

    if user_id in dic.superAdmin_data or user_id not in dic.master_data:
        add_record_button = types.KeyboardButton("СГЕНЕРИРОВАТЬ ОТЧЁТ")
        markup.add(add_record_button)

    if user_id not in dic.superAdmin_data and user_id not in dic.master_data:
        bot.send_message(message.chat.id, "Нажмите 'СГЕНЕРИРОВАТЬ ОТЧЁТ', чтобы начать.", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Нажмите 'ДОБАВИТЬ ЗАПИСЬ', чтобы начать.", reply_markup=markup)


def get_ttn(message):
    if message.text != "ОТМЕНИТЬ ДОБАВЛЕНИЕ ЗАПИСИ":
        if len(message.text) in [3, 4] and message.text.isdigit():
            cursor.execute("SELECT 1 FROM Data WHERE ttn = ?", message.text)
            existing_ttn = cursor.fetchone()

            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            add_record_button = types.KeyboardButton("ДОБАВИТЬ ЗАПИСЬ")
            markup.add(add_record_button)

            if existing_ttn:
                bot.send_message(message.chat.id, "Запись с таким ТТН уже есть в базе!", reply_markup=markup)
            else:
                user_data[message.chat.id]['ТТН'] = message.text
                get_driver_name(message)
        else:
            bot.send_message(message.chat.id, "Неверный формат ТТН!")
            handle_add_record(message)
    else:
        reset(message)

def get_driver_name(message):
    if message.text != "ОТМЕНИТЬ ДОБАВЛЕНИЕ ЗАПИСИ":
        bot.send_message(message.chat.id, "Введите ФИО водителя:")
        bot.register_next_step_handler(message, get_type_drive)
    else:
        reset(message)


def get_type_drive(message):
    if message.text != "ОТМЕНИТЬ ДОБАВЛЕНИЕ ЗАПИСИ":
        user_data[message.chat.id]['ФИО'] = message.text
        bot.send_message(message.chat.id, "Выберите тип перевозки:", reply_markup=create_type_buttons())


def get_car_name(message):
    if message.text != "ОТМЕНИТЬ ДОБАВЛЕНИЕ ЗАПИСИ":
        bot.send_message(message.chat.id, "Выберите марку машины:", reply_markup=create_car_buttons())
    else:
        reset(message)


def get_another_car_name(message):
    if message.text != "ОТМЕНИТЬ ДОБАВЛЕНИЕ ЗАПИСИ":
        user_data[message.chat.id]['Авто'] = message.text.upper()
        bot.send_message(message.chat.id, f"Введите номер автомобиля {user_data[message.chat.id]['Авто']}"
                                               f" в формате ХХ1111ХХ: ")
        bot.register_next_step_handler(message, get_car_number)
    else:
        reset(message)


def get_car_number(message):
    if message.text != "ОТМЕНИТЬ ДОБАВЛЕНИЕ ЗАПИСИ":
        car_number = message.text.upper()

        if re.match(r'^[А-ЯA-Z]{2}\d{4}[А-ЯA-Z]{2}$', car_number):
            user_data[message.chat.id]['CarNumber'] = car_number
            bot.send_message(message.chat.id, "Есть ли прицеп?", reply_markup=create_car_num_buttons())
        else:
            bot.send_message(message.chat.id, "Некорректный формат номера. Формат номера: ХХ1111ХХ. \nПопробуйте снова:")
            bot.register_next_step_handler(message, get_car_number)
    else:
        reset(message)


def ask_for_date(message, first: int):
    markup = types.InlineKeyboardMarkup()
    today = datetime.now().strftime('%d.%m.%Y')
    if first == 1:
        bot.send_message(message.chat.id, "Выберете дату начала погрузки")
    elif first == 2:
        bot.send_message(message.chat.id, "Выберете дату конца погрузки")
    elif first == 3:
        bot.send_message(message.chat.id, "Выберете дату отправки")

    markup.add(types.InlineKeyboardButton(f"Да, использовать {today}", callback_data=f"date_yes_{first}"))
    markup.add(types.InlineKeyboardButton("Нет, ввести вручную", callback_data=f"date_no_{first}"))
    bot.send_message(message.chat.id, f"Использовать текущую дату ({today})?", reply_markup=markup)


def get_trailer_number(message):
    if message.text != "ОТМЕНИТЬ ДОБАВЛЕНИЕ ЗАПИСИ":
        trailer_number = message.text.upper()

        if re.match(r'^[А-ЯA-Z]{2}\d{4}[А-ЯA-Z]{2}$', trailer_number):
            user_data[message.chat.id]['TrailerNumber'] = trailer_number
            ask_for_date(message, 1)
        else:
            bot.send_message(message.chat.id, "Некорректный формат номера. Формат номера: ХХ1111ХХ. \nПопробуйте снова:")
            bot.register_next_step_handler(message, get_trailer_number)
    else:
        reset(message)



def get_date(message, first):
    if message.text != "ОТМЕНИТЬ ДОБАВЛЕНИЕ ЗАПИСИ":
        date = message.text

        if re.match(r'^\d{2}\.\d{2}\.\d{4}$', date):
            day, month, year = date.split('.')
            if 1 <= int(day) <= 31 and 1 <= int(month) <= 12:
                user_data[message.chat.id][f'Дата{first}'] = date

                if first == 1:
                    bot.send_message(message.chat.id, f"Дата начала погрузки - {date}.")
                    bot.send_message(message.chat.id, "Введите время начала погрузки (пример: 09:30):")
                    bot.register_next_step_handler(message, get_loading_start_time)
                elif first == 2:
                    bot.send_message(message.chat.id, f"Дата конца погрузки - {date}.")
                    bot.send_message(message.chat.id, "Введите время конца погрузки (пример: 09:50):")
                    bot.register_next_step_handler(message, get_loading_end_time)
                elif first == 3:
                    bot.send_message(message.chat.id, f"Дата отправки - {date}.")
                    bot.send_message(message.chat.id, "Введите время отправки (пример: 10:30):")
                    bot.register_next_step_handler(message, get_departure_time)
            else:
                bot.send_message(message.chat.id, "Некорректная дата. День должен быть от 1 до 31, а месяц от 1 до 12.")
                bot.register_next_step_handler(message, get_date, first)
        else:
            bot.send_message(message.chat.id, "Неверный формат даты!\nВведите дату (ДД.ММ.ГГГГ):")
            bot.register_next_step_handler(message, get_date, first)
    else:
        reset(message)


def get_loading_start_time(message):
    if message.text != "ОТМЕНИТЬ ДОБАВЛЕНИЕ ЗАПИСИ":
        if validate_time(message.text):
            user_data[message.chat.id]['НачалоПогрузки'] = user_data[message.chat.id]['Дата1'] + " " + message.text.replace('.', ':')
            ask_for_date(message, 2)
        else:
            bot.send_message(message.chat.id, "Неправильный формат времени. Попробуйте снова (пример: 12.00):")
            bot.register_next_step_handler(message, get_loading_start_time)
    else:
        reset(message)


def get_loading_end_time(message):
    if message.text != "ОТМЕНИТЬ ДОБАВЛЕНИЕ ЗАПИСИ":
        if validate_time(message.text):
            user_data[message.chat.id]['КонецПогрузки'] = user_data[message.chat.id]['Дата2'] + " " + message.text.replace('.', ':')
            ask_for_date(message, 3)
        else:
            bot.send_message(message.chat.id, "Неправильный формат времени. Попробуйте снова (пример: 12.00):")
            bot.register_next_step_handler(message, get_loading_end_time)
    else:
        reset(message)


def get_departure_time(message):
    if message.text != "ОТМЕНИТЬ ДОБАВЛЕНИЕ ЗАПИСИ":
        user_data[message.chat.id]['Количество'] = []
        if validate_time(message.text):
            user_data[message.chat.id]['ВремяОтправки'] = user_data[message.chat.id]['Дата3'] + " " + message.text.replace('.', ':')
            bot.send_message(message.chat.id, "Выберите номер поля:",
                             reply_markup=create_field_buttons())
        else:
            bot.send_message(message.chat.id, "Неправильный формат времени. Попробуйте снова (пример: 12.00):")
            bot.register_next_step_handler(message, get_departure_time)
    else:
        reset(message)


def ask_hybrid_quantity(call):
    hybrid = user_data[call.message.chat.id]['Гибриды'][-1]
    bot.send_message(call.message.chat.id, f"Введите количество (в килограммах) для {hybrid}:")
    bot.register_next_step_handler(call.message, save_hybrid_quantity)

def save_hybrid_quantity(message):
    if message.text != "ОТМЕНИТЬ ДОБАВЛЕНИЕ ЗАПИСИ":
        try:
            quantity = int(message.text)
            if quantity > 0:
                user_data[message.chat.id]['Количество'].append(quantity)
                print(user_data[message.chat.id]['Количество'])
                if user_data[message.chat.id]['count'] < user_data[message.chat.id]['Количество Гибридов На Поле']:
                    hybrids_quantity(message)  # Запрос следующего гибрида
                else:
                    confirm_data(message)  # Завершение ввода данных
            else:
                bot.send_message(message.chat.id, "Введите положительное целое число. Попробуйте снова:")
                bot.register_next_step_handler(message, save_hybrid_quantity)
        except ValueError:
            bot.send_message(message.chat.id, "Введите число. Попробуйте снова:")
            bot.register_next_step_handler(message, save_hybrid_quantity)
    else:
        reset(message)


def create_quantity_buttons():
    row = []
    markup = types.InlineKeyboardMarkup()

    for i in range(1, 10):
        row += [
            types.InlineKeyboardButton(str(i), callback_data=f"quantity_{i}")
        ]

        if i % 3 == 0:
            markup.row(*row)
            row = []

    return markup


def hybrids_quantity(message):
    if user_data[message.chat.id]['Количество Гибридов На Поле'] > 0:
        user_data[message.chat.id]['count'] += 1
        bot.send_message(message.chat.id, f"Выберите гибрид №{user_data[message.chat.id]['count']}:",
                         reply_markup=create_hybrid_buttons())
    else:
        bot.send_message(message.chat.id, "Выберите гибрид:", reply_markup=create_hybrid_buttons())


def create_hybrid_buttons():
    markup = types.InlineKeyboardMarkup()

    row1 = [
        types.InlineKeyboardButton("Прецинум (N6438)", callback_data=f"hybrid_Прецинум(N6438)")
    ]
    row2 = [
        types.InlineKeyboardButton("Прецинум (Н0507)", callback_data=f"hybrid_Прецинум(Н0507)")
    ]
    row3 = [
        types.InlineKeyboardButton("Хайнц (Н1015)", callback_data=f"hybrid_Хайнц(Н1015)"),
        types.InlineKeyboardButton("Хайнц (Н1301)", callback_data=f"hybrid_Хайнц(Н1301)"),
        types.InlineKeyboardButton("Хайнц (Н1648)", callback_data=f"hybrid_Хайнц(Н1648)")
    ]
    row4 = [
        types.InlineKeyboardButton("Хайнц (Н5108)", callback_data=f"hybrid_Хайнц(Н5108)"),
        types.InlineKeyboardButton("ЯГ8810F1", callback_data=f"hybrid_ЯГ8810F1")
    ]

    markup.row(*row1)
    markup.row(*row2)
    markup.row(*row3)
    markup.row(*row4)
    return markup


def create_field_buttons():
    row = []
    markup = types.InlineKeyboardMarkup()

    for i in range(1, 15):
        row += [
            types.InlineKeyboardButton(str(i), callback_data=f"field_{i}")
        ]

        if i % 3 == 0:
            markup.row(*row)
            row = []

    row = [
        types.InlineKeyboardButton(str(13), callback_data=f"field_13"),
        types.InlineKeyboardButton(str(14), callback_data=f"field_14")
    ]
    markup.row(*row)

    return markup


def create_car_buttons():
    markup = types.InlineKeyboardMarkup()

    row = [
        types.InlineKeyboardButton("MAN", callback_data=f"car_man"),
        types.InlineKeyboardButton("КАМАЗ", callback_data=f"car_kamaz"),
        types.InlineKeyboardButton("DAF", callback_data=f"car_daf")
    ]

    markup.row(*row)

    row = [
        types.InlineKeyboardButton("RENAULT", callback_data=f"car_renault"),
        types.InlineKeyboardButton("VOLVO", callback_data=f"car_volvo"),
        types.InlineKeyboardButton("SCANIA", callback_data=f"car_scania")
    ]

    markup.row(*row)

    row = [
        types.InlineKeyboardButton("MERCEDES", callback_data=f"car_mercedes"),
        types.InlineKeyboardButton("IVECO", callback_data=f"car_iveco")
    ]

    markup.row(*row)
    markup.row(types.InlineKeyboardButton("ДРУГОЙ АВТОМОБИЛЬ", callback_data=f"car_another"))
    return markup


def create_type_buttons():
    markup = types.InlineKeyboardMarkup()

    row = [
        types.InlineKeyboardButton("НАЁМНЫЙ", callback_data="type_hired"),
        types.InlineKeyboardButton("СОБСТВЕННЫЙ", callback_data="type_own")
    ]

    markup.row(*row)
    return markup


def create_car_num_buttons():
    markup = types.InlineKeyboardMarkup()

    row = [
        types.InlineKeyboardButton("ДА", callback_data=f"trailer_yes"),
        types.InlineKeyboardButton("НЕТ", callback_data=f"trailer_no")
    ]

    markup.row(*row)
    return markup


@bot.callback_query_handler(func=lambda call: call.data.startswith("accept_") or call.data.startswith("reject_"))
def handle_request(call):
    user_id = int(call.data.split("_")[1])
    cursor.execute("SELECT * FROM Users WHERE userID = ?", (user_id,))
    user = cursor.fetchone()

    if call.data.startswith("accept_"):
        if user:
            bot.send_message(call.message.chat.id, "Этот пользователь уже добавлен.")
        else:
            cursor.execute("INSERT INTO Users (userID) VALUES (?)",
                           user_id)
            conn.commit()
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            add_record_button = types.KeyboardButton("ДОБАВИТЬ ЗАПИСЬ")
            markup.add(add_record_button)

            if user_id in admins:
                add_record_button = types.KeyboardButton("СГЕНЕРИРОВАТЬ ОТЧЁТ")
                markup.add(add_record_button)

            bot.send_message(call.message.chat.id, "Пользователь добавлен.")
            bot.send_message(user_id, "Вам предоставлен доступ!", reply_markup=markup)
    elif call.data.startswith("reject_"):
        bot.send_message(call.message.chat.id, "Запрос отклонен.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("type_"))
def handle_type(call):
    if call.data == "type_hired":
        user_data[call.message.chat.id]['ТипПеревозки'] = "Наёмный"
    elif call.data == "type_own":
        user_data[call.message.chat.id]['ТипПеревозки'] = "Собственный"
    get_car_name(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith("car_"))
def handle_car(call):
    if not user_steps[call.message.chat.id]['step']:
        if call.data == "car_another":
            user_steps[call.message.chat.id]['step'].append(1)
            bot.send_message(call.message.chat.id, "Введите марку автомобиля:")
            bot.register_next_step_handler(call.message, get_another_car_name)
        else:
            user_steps[call.message.chat.id]['step'].append(1)
            car = call.data.split("_", 1)[1]
            user_data[call.message.chat.id]['Авто'] = car.upper()
            bot.send_message(call.message.chat.id, f"Введите номер автомобиля {user_data[call.message.chat.id]['Авто']}"
                                                   f" в формате ХХ1111ХХ: ")
            bot.register_next_step_handler(call.message, get_car_number)


@bot.callback_query_handler(func=lambda call: call.data.startswith("trailer_"))
def handle_trailer(call):
    if call.data == "trailer_yes" and check_steps(call.message, 2):
        user_steps[call.message.chat.id]['step'].append(2)
        bot.send_message(call.message.chat.id, "Введите номер прицепа в формате ХХ1111ХХ:")
        bot.register_next_step_handler(call.message, get_trailer_number)
    elif call.data == "trailer_no" and check_steps(call.message, 2):
        user_steps[call.message.chat.id]['step'].append(2)
        user_data[call.message.chat.id]['TrailerNumber'] = ""
        ask_for_date(call.message, 1)



@bot.callback_query_handler(func=lambda call: call.data.startswith("date_"))
def check_date_choice(call):
    if call.data == "date_yes_1" and check_steps(call.message, 3):
        user_steps[call.message.chat.id]['step'].append(3)
        user_data[call.message.chat.id]['Дата1'] = datetime.now().strftime('%d.%m.%Y')
        bot.send_message(call.message.chat.id, f"Дата начала погрузки - {user_data[call.message.chat.id]['Дата1']}.")
        bot.send_message(call.message.chat.id, "Введите время начала погрузки (пример: 9.30):")
        bot.register_next_step_handler(call.message, get_loading_start_time)
    elif call.data == "date_no_1":
        bot.send_message(call.message.chat.id, "Введите дату (ДД.ММ.ГГГГ):")
        user_steps[call.message.chat.id]['step'].append(3)
        bot.register_next_step_handler(call.message, get_date, 1)
    elif call.data == "date_yes_2" and check_steps(call.message, 4):
        user_steps[call.message.chat.id]['step'].append(4)
        user_data[call.message.chat.id]['Дата2'] = datetime.now().strftime('%d.%m.%Y')
        bot.send_message(call.message.chat.id, f"Дата конца погрузки {user_data[call.message.chat.id]['Дата2']}.")
        bot.send_message(call.message.chat.id, "Введите время конца погрузки (пример: 9.30):")
        bot.register_next_step_handler(call.message, get_loading_end_time)
    elif call.data == "date_no_2":
        bot.send_message(call.message.chat.id, "Введите дату (ДД.ММ.ГГГГ):")
        user_steps[call.message.chat.id]['step'].append(4)
        bot.register_next_step_handler(call.message, get_date, 2)
    elif call.data == "date_yes_3" and check_steps(call.message, 5):
        user_steps[call.message.chat.id]['step'].append(5)
        user_data[call.message.chat.id]['Дата3'] = datetime.now().strftime('%d.%m.%Y')
        bot.send_message(call.message.chat.id, f"Дата отгрузки - {user_data[call.message.chat.id]['Дата3']}.")
        bot.send_message(call.message.chat.id, "Введите время отправки (пример: 9.30):")
        bot.register_next_step_handler(call.message, get_departure_time)
    elif call.data == "date_no_3":
        bot.send_message(call.message.chat.id, "Введите дату (ДД.ММ.ГГГГ):")
        user_steps[call.message.chat.id]['step'].append(5)
        bot.register_next_step_handler(call.message, get_date, 3)


@bot.callback_query_handler(func=lambda call: call.data.startswith("field_"))
def handle_field(call):
    if check_steps(call.message, 6):
        user_steps[call.message.chat.id]['step'].append(6)
        field = call.data.split("_", 1)[1]
        user_data[call.message.chat.id]['Поле'] = "Поле Беляевка " + field
        bot.send_message(call.message.chat.id, f"Введите количество гибридов на {user_data[call.message.chat.id]['Поле']}",
                         reply_markup=create_quantity_buttons())


@bot.callback_query_handler(func=lambda call: call.data.startswith("quantity_"))
def handle_quantity(call):
    if check_steps(call.message, 7):
        user_steps[call.message.chat.id]['step'].append(7)
        quantity = int(call.data.split("_")[1])
        user_data[call.message.chat.id]['Количество Гибридов На Поле'] = quantity
        user_data[call.message.chat.id]['count'] = 0
        user_data[call.message.chat.id]['Гибриды'] = []
        hybrids_quantity(call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith("hybrid_"))
def handle_hybrid(call):
    if user_steps[call.message.chat.id]['step']:
        if user_steps[call.message.chat.id]['step'][-1] == 7:
            hybrid = call.data.split("_", 1)[1]
            hybrid = hybrid.replace("(", " (")
            user_data[call.message.chat.id]['Гибриды'].append(hybrid)
            ask_hybrid_quantity(call)  # Запрос количества гибрида


def confirm_data(message):
    user_data[message.chat.id]['ТТНДата'] = datetime.now().strftime('%d.%m.%Y')
    user_data[message.chat.id]['Обработано'] = 0
    try:
        user_data[message.chat.id].pop('count')
    except KeyError:
        print("key error")

    hybrid_info = "\n".join([f"{h}: {q} килограмм" for h, q in
                             zip(user_data[message.chat.id]['Гибриды'], user_data[message.chat.id]['Количество'])])
    markup = types.InlineKeyboardMarkup()
    row = [
        types.InlineKeyboardButton("Да", callback_data="confirm_yes"),
    ]
    markup.add(*row)
    markup.add(types.InlineKeyboardButton("Удалить запись", callback_data="confirm_delete"))
    bot.send_message(
        message.chat.id,
        "<b>Все ли заполнено правильно?</b>\n\n"
        f"<b>ТТН:</b> {user_data[message.chat.id]['ТТН']}"
        f"\n<b>Дата ТТН:</b> {user_data[message.chat.id]['ТТНДата']}"
        f"\n<b>Фио водителя</b>: {user_data[message.chat.id]['ФИО']}"
        f"\n<b>Тип перевозки</b>: {user_data[message.chat.id]['ТипПеревозки']}"
        f"\n<b>Марка автомобиля:</b> {user_data[message.chat.id]['Авто'].upper()}"
        f"\n<b>Номер автомобиля:</b> {user_data[message.chat.id]['CarNumber']}"
        f"\n<b>Номер прицепа:</b> {user_data[message.chat.id]['TrailerNumber']}"
        f"\n<b>Начало погрузки:</b> {user_data[message.chat.id]['НачалоПогрузки']}"
        f"\n<b>Конец погрузки:</b> {user_data[message.chat.id]['КонецПогрузки']}"
        f"\n<b>Время отправки:</b> {user_data[message.chat.id]['ВремяОтправки']}"
        f"\n<b>Поле:</b> {user_data[message.chat.id]['Поле']}"
        f"\n<b>Гибриды и количество:</b> \n{hybrid_info}",
        reply_markup=markup,
        parse_mode='HTML'
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm"))
def callback_confirm(call):
    if call.data == "confirm_yes":
        user_data[call.message.chat.id]['ТТНДата'] = datetime.now().strftime('%d.%m.%Y')
        user_steps[call.message.chat.id]['step'] = []
        save_data_to_db(user_data[call.message.chat.id], call.message)
    elif call.data == "confirm_delete":
        user_steps[call.message.chat.id]['step'] = []
        confirm_delete_markup = types.InlineKeyboardMarkup()
        confirm_delete_markup.add(types.InlineKeyboardButton("Да", callback_data="delete_confirm_yes"))
        confirm_delete_markup.add(types.InlineKeyboardButton("Нет", callback_data="delete_confirm_no"))
        bot.send_message(call.message.chat.id, "Вы уверены, что хотите удалить запись?",
                         reply_markup=confirm_delete_markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_confirm"))
def callback_delete_confirm(call):
    if call.data == "delete_confirm_yes":
        user_data.pop(call.message.chat.id, None)
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        add_record_button = types.KeyboardButton("ДОБАВИТЬ ЗАПИСЬ")
        markup.add(add_record_button)

        if call.message.chat.id in admins:
            add_record_button = types.KeyboardButton("СГЕНЕРИРОВАТЬ ОТЧЁТ")
            markup.add(add_record_button)

        bot.send_message(call.message.chat.id, "Запись удалена.", reply_markup=markup)
    elif call.data == "delete_confirm_no":
        confirm_data(call.message)


def save_data_to_db(data, message):
    if dic.users_data.get(message.chat.id) is None:
        bot.send_message(message.chat.id, "У вас нет права на внесение записей в базу!")
    else:
        ttn_date = datetime.strptime(data['ТТНДата'], '%d.%m.%Y').strftime('%Y-%m-%d')
        start_time = datetime.strptime(data['НачалоПогрузки'], '%d.%m.%Y %H:%M').strftime('%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(data['КонецПогрузки'], '%d.%m.%Y %H:%M').strftime('%Y-%m-%d %H:%M:%S')
        departure_time = datetime.strptime(data['ВремяОтправки'], '%d.%m.%Y %H:%M').strftime('%Y-%m-%d %H:%M:%S')

        # Переводим данные в строку для упрощения сравнения
        data_tuple = (
            data['ТТН'], ttn_date, start_time, end_time, departure_time,
            data['Поле'], data['Гибриды'][0], data['Количество'][0], data['Обработано']
        )

        cursor.execute(
            "SELECT 1 FROM Data WHERE ttn = ? AND ttn_date = ? AND start_time = ? AND end_time = ? AND departure_time = ? "
            "AND field = ? AND hybrid = ? AND quantity = ? AND processed = ?",
            data_tuple
        )
        existing_record = cursor.fetchone()

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        add_record_button = types.KeyboardButton("ДОБАВИТЬ ЗАПИСЬ")
        markup.add(add_record_button)

        if message.chat.id in admins:
            add_record_button = types.KeyboardButton("СГЕНЕРИРОВАТЬ ОТЧЁТ")
            markup.add(add_record_button)

        if existing_record:
            bot.send_message(message.chat.id,"Запись уже существует в базе данных.")
        else:
            try:
                with db_lock:
                    for hybrid, quantity in zip(data['Гибриды'], data['Количество']):
                        margin_found = [key for key, value in dic.margin_dict.items() if value == data['Поле']]
                        hybrid_found = [key for key, value in dic.hybrid_dict.items() if value == hybrid]

                        cursor.execute(
                            "INSERT INTO Data (ttn, ttn_date, fullName, typeDrive, car, car_number, trailer_number, start_time, end_time, "
                            "departure_time, field_code, field, hybrid_code, hybrid, quantity, processed, owner) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            data['ТТН'], ttn_date, data['ФИО'], data['ТипПеревозки'], data['Авто'], data['CarNumber'], data['TrailerNumber'], start_time,
                            end_time, departure_time,
                            margin_found[0], data['Поле'], hybrid_found[0], hybrid, quantity, data['Обработано'],
                            dic.users_data.get(message.chat.id)
                        )
                    conn.commit()

                    bot.send_message(message.chat.id, "Запись внесена в базу!", reply_markup=markup)

                    hybrid_info = "\n".join([f"{h}: {q} килограмм" for h, q in
                                             zip(user_data[message.chat.id]['Гибриды'],
                                                 user_data[message.chat.id]['Количество'])])

                    if data['TrailerNumber'] == "":
                        data['TrailerNumber'] = "нет"

                    mess = f"""
                    ТТН: {data['ТТН']}
Дата ТТН: {ttn_date}
ФИО водителя: {user_data[message.chat.id]['ФИО']}
Тип перевозки: {user_data[message.chat.id]['ТипПеревозки']}
Марка автомобиля: {data['Авто'].upper()}
Номер автомобиля: {data['CarNumber']}
Номер прицепа: {data['TrailerNumber']}
Начало погрузки: {start_time}
Конец погрузки: {end_time}
Время отправки: {departure_time}
Поле: {user_data[message.chat.id]['Поле']}
Гибриды и количество: \n{hybrid_info}

Исполнитель: {dic.users_data.get(message.chat.id)}
"""

                    bot.send_message(int(group_id), mess)
            except Exception as ex:
                bot.send_message(message.chat.id, f"Не удалось записать в базу!", reply_markup=markup)
                bot.send_message(7178651151, f"Не удалось записать в базу!\nПользователь: {message.chat.id}\nОшибка: {ex}")


if __name__ == "__main__":
    create_table_if_not_exists()
    while True:
        try:
            bot.polling(none_stop=True)
        except requests.exceptions.ReadTimeout:
            bot.send_message(7178651151, "Плохое качество связи")
            time.sleep(5)  # задержка перед перезапуском
        except Exception as ex:
            bot.send_message(7178651151, f"Бот упал с ошибкой: {ex}")
            time.sleep(5)  # задержка перед перезапуском
