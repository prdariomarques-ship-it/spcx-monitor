import unittest
from unittest.mock import Mock, patch

import monitor_spcx as monitor


class TelegramTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(monitor._last_alert.clear)
        self.original_ref_price = monitor._spcx_ref_price
        monitor._spcx_ref_price = None
        self.addCleanup(setattr, monitor, "_spcx_ref_price", self.original_ref_price)

    @patch.object(monitor.requests, "post")
    def test_send_telegram_returns_true_for_accepted_message(self, post):
        response = Mock()
        response.json.return_value = {"ok": True}
        post.return_value = response

        with patch.object(monitor, "TELEGRAM_TOKEN", "bot-token"), patch.object(
            monitor, "TELEGRAM_CHAT_ID", "chat-id"
        ):
            self.assertTrue(monitor.send_telegram("teste"))

        post.assert_called_once_with(
            "https://api.telegram.org/botbot-token/sendMessage",
            json={"chat_id": "chat-id", "text": "teste"},
            timeout=10,
        )

    @patch.object(monitor.requests, "post", side_effect=monitor.requests.Timeout())
    def test_send_telegram_returns_false_when_request_fails(self, _post):
        with patch.object(monitor, "TELEGRAM_TOKEN", "bot-token"), patch.object(
            monitor, "TELEGRAM_CHAT_ID", "chat-id"
        ):
            self.assertFalse(monitor.send_telegram("teste"))

    def test_failed_telegram_delivery_does_not_start_cooldown(self):
        with patch.object(monitor, "_nyse_pregao_aberto", return_value=True), patch.object(
            monitor, "fetch_prev_close", return_value=100.0
        ), patch.object(monitor, "fetch_price", return_value=106.0), patch.object(
            monitor, "send_telegram", return_value=False
        ):
            monitor.check_spcx()

        self.assertNotIn("SPCX", monitor._last_alert)


if __name__ == "__main__":
    unittest.main()
