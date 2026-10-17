import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import io
import json
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location("petbot", Path(__file__).parents[1] / "bot" / "bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

class BotTests(unittest.TestCase):
    URL = "https://demo.github.io/petfood-dashboard/"

    def test_greetings_commands_and_punctuation(self):
        self.assertIn("Привет", bot.reply_text("Привет!"))
        self.assertIn("Привет", bot.reply_text("/start@peetfodbot interview"))
        self.assertIn("Пока", bot.reply_text("ПОКА."))
        self.assertIn("вымышлены", bot.reply_text("кто ты?"))
        self.assertIn("/dashboard", bot.reply_text("/help"))

    def test_private_message_opens_web_app(self):
        api = Mock()
        bot.handle_update(api, {"message": {"chat": {"id": 12, "type": "private"}, "text": "привет"}}, self.URL)
        args = api.call.call_args
        self.assertEqual(args.args[0], "sendMessage")
        self.assertEqual(args.kwargs["chat_id"], 12)
        self.assertEqual(args.kwargs["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"], self.URL)

    def test_ignores_group_and_nontext(self):
        api = Mock()
        for update in [{}, {"message": {"chat": {"id": 1, "type": "group"}, "text": "привет"}},
                       {"message": {"chat": {"id": 1, "type": "private"}, "photo": [{}]}}]:
            bot.handle_update(api, update, self.URL)
        api.call.assert_not_called()

    def test_menu_and_command_setup(self):
        api = Mock()
        bot.configure(api, self.URL)
        self.assertEqual(api.call.call_args.kwargs["menu_button"]["web_app"]["url"], self.URL)

    def test_invalid_urls_rejected(self):
        for value in ["file:///tmp/index.html", "http://demo.test/", "https://example.com/", "https://user:pass@test.test/"]:
            with self.assertRaises(ValueError):
                bot.validate_url(value)
        self.assertEqual(bot.validate_url(self.URL), self.URL)

    def test_rate_limit_does_not_expose_request_or_token(self):
        client = bot.Telegram("secret-test-value")
        error = HTTPError("https://api.telegram.org/botsecret-test-value/sendMessage",
                          429, "rate limited", {}, io.BytesIO(json.dumps({"parameters":{"retry_after":3}}).encode()))
        with patch.object(bot, "urlopen", side_effect=error):
            with self.assertRaises(bot.ApiError) as raised:
                client.call("sendMessage", chat_id=1, text="test")
        self.assertEqual(raised.exception.retry_after, 3)
        self.assertNotIn("secret-test-value", str(raised.exception))

if __name__ == "__main__":
    unittest.main()

