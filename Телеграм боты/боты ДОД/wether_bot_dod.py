import telebot
import requests

BOT_TOKEN = ""
WETHER_TOKEN = "9e078a39584f9fc316c08246435c8457"

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я подскажу тебе погоду в любом городе! Введи любой город ⛅️")

@bot.message_handler(func=lambda message: True)
def get_weather(message):
    city = message.text.strip()
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"

    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        temp = data['main']['temp']

        reply = (f"Погода в городе: {city}\n"
                 f"Температура: {temp} C")
    else:
        reply = "Такого города нет"

    bot.reply_to(message, reply)        
bot.polling()