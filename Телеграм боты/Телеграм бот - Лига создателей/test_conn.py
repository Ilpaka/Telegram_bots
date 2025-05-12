import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("Телеграм бот - Лига создателей/credentials/tonal-rune-446721-p0-f13c2765f87f.json", scope)
client = gspread.authorize(creds)

try:
    # Попытка открыть таблицу по её названию
    sheet = client.open("Liga_Sozdateley_Registrations").sheet1
    records = sheet.get_all_records()
    print("Доступ установлен, данные:", records)
except Exception as e:
    print("Ошибка при доступе к таблице:", e)