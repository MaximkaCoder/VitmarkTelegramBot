import pandas as pd
from io import BytesIO


# Функция для подключения к MS SQL и получения данных
def get_data_from_db(conn):
    query = """
    SELECT 
        ttn, 
        ttn_date, 
        car,
        car_number,
        trailer_number,
        start_time, 
        end_time, 
        departure_time, 
        field, 
        hybrid, 
        quantity,
        owner,
        processed
    FROM Data
    """

    # Получаем данные в виде DataFrame
    df = pd.read_sql_query(query, conn)

    return df


# Функция для создания Excel файла
def create_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')

    # Переименование столбцов в соответствии с вашими требованиями
    df.columns = [
        'ТТН', 'Дата ТТН', 'Марка автомобиля', 'Номер автомобиля', 'Номер прицепа', 'Дата начала погрузки',
        'Дата конца погрузки', 'Дата отправки',
        'Поле', 'Гибрид', 'Количество(кг)', 'Исполнитель', 'Обработано'
    ]

    df.to_excel(writer, index=False, startrow=1, header=False)

    workbook = writer.book
    worksheet = writer.sheets['Sheet1']

    # Форматирование заголовков
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#00B050',  # Цвет фона для заголовков
        'font_color': '#FFFFFF',  # Цвет текста заголовков (белый)
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })

    # Запись заголовков в Excel
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, header_format)

    # Автонастройка ширины колонок
    for idx, col in enumerate(df.columns):
        series = df[col]
        max_len = max(
            series.astype(str).map(len).max(),  # Максимальная длина данных в колонке
            len(str(series.name))  # Длина названия колонки
        ) + 2  # Добавляем немного пространства
        worksheet.set_column(idx, idx, max_len)

    writer.close()
    output.seek(0)

    return output