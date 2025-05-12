import telebot
import requests

TELEGRAM_TOKEN = ''
WEATHER_API_KEY = ''

bot = telebot.TeleBot(TELEGRAM_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Напиши мне название города, и я расскажу тебе, какая там сейчас погода 🌤")

@bot.message_handler(func=lambda message: True)
def get_weather(message):
    city = message.text.strip()
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
    response = requests.get(url)
    print(response.status_code)
    if response.status_code == 200:
        data = response.json()
        temp = data['main']['temp']
        feels_like = data['main']['feels_like']
        weather_desc = data['weather'][0]['main']
        humidity = data['main']['humidity']
        wind_speed = data['wind']['speed']
        pressure = data['main']['pressure']
        code_to_smile = {
            "Clear": "Ясно \U00002600",
            "Clouds": "Облачно \U00002601",
            "Rain": "Дождь \U00002614",
            "Drizzle": "Дождь \U00002614",
            "Thunderstorm": "Гроза \U000026A1",
            "Snow": "Снег \U0001F328",
            "Mist": "Туман \U0001F32B"
        }

        if weather_desc in code_to_smile:
            wd = code_to_smile[weather_desc]
        else:
            wd = "Посмотри в окно, я не понимаю, что там за погода..."

        reply = (
            f"🌍 Погода в городе {city}:\n"
            f"🌡 Температура: {temp}°C (ощущается как {feels_like}°C)\n"
            f"🌦 Состояние: {wd}\n"
            f"💧 Влажность: {humidity}%\n"
            f"💨 Ветер: {wind_speed} м/с\n"
            f"⬇ Давление: {pressure//1.333} мм/рт.ст. "
        )
    else:
        reply = "⚠️ Не удалось получить данные. Проверь название города и попробуй снова."

    bot.reply_to(message, reply)

bot.polling()