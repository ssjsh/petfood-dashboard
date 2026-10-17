"""Paw Insight demo bot. Python 3.10+, standard library only."""
import getpass
import json
import os
from pathlib import Path
import re
import string
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]

class ApiError(Exception):
    def __init__(self, code, retry_after=0):
        self.code = code
        self.retry_after = retry_after
        super().__init__(f"Telegram API status {code}")  # No token or raw response.

def load_env(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key in ("BOT_TOKEN", "DASHBOARD_URL"):
            os.environ.setdefault(key, value)

def validate_url(url):
    parsed = urlparse(url)
    if (parsed.scheme != "https" or not parsed.hostname or
            parsed.username or parsed.password or
            parsed.hostname in ("localhost", "example.com") or
            parsed.hostname.endswith(".example") or "YOUR_" in url):
        raise ValueError("Укажите настоящий HTTPS-адрес опубликованного дашборда.")
    return url

class Telegram:
    def __init__(self, token):
        self._base = "https://api.telegram.org/bot" + token + "/"

    def call(self, method, **payload):
        request = Request(self._base + method,
                          data=json.dumps(payload).encode("utf-8"),
                          headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=45) as response:
                result = json.load(response)
        except HTTPError as error:
            code, retry = error.code, 0
            try:
                data = json.loads(error.read())
                retry = data.get("parameters", {}).get("retry_after", 0)
            except (ValueError, OSError):
                pass
            raise ApiError(code, retry) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise ApiError(0) from None
        if not result.get("ok"):
            raise ApiError(result.get("error_code", 0),
                           result.get("parameters", {}).get("retry_after", 0))
        return result["result"]

def normalize(text):
    text = text.strip().casefold()
    if text.startswith("/"):
        return text.split()[0].split("@")[0]
    return text.strip(string.punctuation + " «»…")

def reply_text(text):
    text = normalize(text)
    if text in ("/start", "привет", "здравствуй", "здравствуйте", "hello"):
        return ("Привет! Я Paw Insight — демонстрационный бот аналитики продаж кормов. 🐾\n"
                "Показываю выручку, себестоимость, валовую прибыль и остатки "
                "на вымышленных данных. Нажми кнопку, чтобы открыть дашборд.")
    if text in ("/bye", "пока", "до свидания", "bye"):
        return "Пока! 🐾 Дашборд останется доступен по кнопке. Возвращайся за аналитикой!"
    if text in ("/about", "кто ты", "представься", "о боте"):
        return ("Я Paw Insight — учебный помощник для показа аналитики дистрибьютора кормов. "
                "В дашборде 24 товара, 6 менеджеров и 2 882 продажи. Все данные вымышлены. "
                "Это демонстрация, а не подключение к 1С.")
    if text in ("/dashboard", "дашборд", "аналитика", "отчеты", "отчёты"):
        return "Открой аналитику кнопкой ниже: продажи, товары, сотрудники и склад."
    if text in ("/help", "помощь"):
        return ("/start — приветствие\n/dashboard — дашборд\n/about — о проекте\n"
                "/bye — попрощаться\n/help — помощь\n"
                "Также понимаю «привет», «пока» и «кто ты».")
    return "Я демонстрационный бот. Напиши «привет», «пока», «кто ты» или открой дашборд."

def handle_update(api, update, dashboard_url):
    message = update.get("message")
    if not message or message.get("chat", {}).get("type") != "private":
        return
    if message.get("from", {}).get("is_bot"):
        return
    text = message.get("text")
    if not text:
        return
    api.call("sendMessage", chat_id=message["chat"]["id"], text=reply_text(text),
             reply_markup={"inline_keyboard": [[{
                 "text": "🐾 Открыть аналитику",
                 "web_app": {"url": dashboard_url}
             }]]})

def configure(api, url):
    api.call("setMyCommands", commands=[
        {"command": "start", "description": "Начать"},
        {"command": "dashboard", "description": "Открыть аналитику"},
        {"command": "about", "description": "О проекте"},
        {"command": "help", "description": "Помощь"},
        {"command": "bye", "description": "Попрощаться"},
    ])
    api.call("setChatMenuButton", menu_button={
        "type": "web_app", "text": "Аналитика", "web_app": {"url": url}})

def main():
    load_env(ROOT / ".env")
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token or token == "PASTE_TOKEN_LOCALLY":
        token = getpass.getpass("Токен BotFather (ввод скрыт): ").strip()
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
        raise ValueError("Некорректный формат токена. Вставьте токен локально из BotFather.")
    url = os.environ.get("DASHBOARD_URL", "").strip()
    if not url or "YOUR_" in url:
        url = input("HTTPS-адрес опубликованного дашборда: ").strip()
    url = validate_url(url)
    api = Telegram(token)
    api.call("getMe")
    webhook = api.call("getWebhookInfo")
    if webhook.get("url"):
        raise ValueError("У бота установлен webhook. Этот пример использует polling; отключите webhook перед запуском.")
    configure(api, url)
    print("Бот запущен. Напишите ему в личный чат. Остановка: Ctrl+C.")
    offset = 0
    delay = 2
    while True:
        try:
            updates = api.call("getUpdates", offset=offset, timeout=30,
                               allowed_updates=["message"])
            for update in updates:
                try:
                    handle_update(api, update, url)
                except ApiError as error:
                    if error.code not in (400, 403):
                        raise
                    print("Сообщение пропущено: чат недоступен или запрос отклонен.")
                offset = update["update_id"] + 1
            delay = 2
        except ApiError as error:
            if error.code in (401, 409):
                raise
            wait = max(delay, error.retry_after)
            print("Telegram временно недоступен; повторяем соединение.")
            time.sleep(wait)
            delay = min(delay * 2, 30)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nБот остановлен.")
    except ValueError as error:
        print(error)
        raise SystemExit(1)
    except ApiError as error:
        if error.code == 401:
            print("Telegram не принял токен. Проверьте его локально в BotFather.")
        elif error.code == 409:
            print("Конфликт получения сообщений. Остановите другой экземпляр бота или отключите webhook.")
        else:
            print("Не удалось настроить Telegram. Проверьте интернет, токен и адрес сайта.")
        raise SystemExit(1)

