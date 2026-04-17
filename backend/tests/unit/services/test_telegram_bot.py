"""TelegramBotService — unit tests for command formatting + lifecycle."""

from __future__ import annotations

from app.services.telegram_bot_service import _STATUS_EMOJI, TelegramBotService


class TestLifecycle:
    def test_not_started_by_default(self) -> None:
        svc = TelegramBotService()
        assert not svc.is_started()

    def test_empty_token_stays_disabled(self) -> None:
        svc = TelegramBotService()
        svc.start(token="", default_chat_id="123")
        assert not svc.is_started()

    def test_stop_without_start_is_safe(self) -> None:
        svc = TelegramBotService()
        svc.stop()
        assert not svc.is_started()


class TestAuth:
    def test_empty_allowlist_allows_all(self) -> None:
        svc = TelegramBotService()
        svc._allowed_chats = set()
        assert svc._is_allowed("any_chat")

    def test_allowlist_blocks_unknown(self) -> None:
        svc = TelegramBotService()
        svc._allowed_chats = {"111", "222"}
        assert svc._is_allowed("111")
        assert not svc._is_allowed("333")


class TestStatusEmoji:
    def test_all_statuses_have_emoji(self) -> None:
        for status in ["SUCCESS", "ERROR", "RUNNING", "PENDING", "CANCELLED", "SKIPPED"]:
            assert status in _STATUS_EMOJI

    def test_success_is_checkmark(self) -> None:
        assert "✅" in _STATUS_EMOJI["SUCCESS"]

    def test_error_is_alarm(self) -> None:
        assert "🚨" in _STATUS_EMOJI["ERROR"]


class TestSubscription:
    def test_subscribe_adds_chat(self) -> None:
        svc = TelegramBotService()
        svc._subscribers.add("123")
        assert "123" in svc._subscribers

    def test_unsubscribe_removes_chat(self) -> None:
        svc = TelegramBotService()
        svc._subscribers.add("123")
        svc._subscribers.discard("123")
        assert "123" not in svc._subscribers

    def test_unsubscribe_nonexistent_is_safe(self) -> None:
        svc = TelegramBotService()
        svc._subscribers.discard("never_added")
