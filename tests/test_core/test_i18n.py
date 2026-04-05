"""Unit tests for the i18n module."""
from __future__ import annotations

import pytest

from src.core.i18n import _REGISTRY, register, t
from src.core.i18n.shared import category_label, period_label  # noqa: F401 — triggers register()


@pytest.fixture(autouse=True)
def _clean_registry():
    """Snapshot and restore _REGISTRY around each test."""
    snapshot = dict(_REGISTRY)
    yield
    _REGISTRY.clear()
    _REGISTRY.update(snapshot)


class TestRegisterAndTranslate:
    def test_register_and_lookup(self):
        register("test", {"hello": {"zh": "你好", "en": "Hello", "ja": "こんにちは"}})
        assert t("test.hello", "zh") == "你好"
        assert t("test.hello", "en") == "Hello"
        assert t("test.hello", "ja") == "こんにちは"

    def test_fallback_to_zh(self):
        register("test", {"msg": {"zh": "中文"}})
        assert t("test.msg", "en") == "中文"
        assert t("test.msg", "ja") == "中文"

    def test_fallback_to_key(self):
        assert t("nonexistent.key", "en") == "nonexistent.key"

    def test_format_kwargs(self):
        register("test", {"greet": {"en": "Hello {name}!", "zh": "你好 {name}!"}})
        assert t("test.greet", "en", name="Alice") == "Hello Alice!"
        assert t("test.greet", "zh", name="小明") == "你好 小明!"

    def test_format_no_kwargs(self):
        register("test", {"plain": {"en": "No args here"}})
        assert t("test.plain", "en") == "No args here"

    def test_register_is_additive(self):
        register("ns1", {"a": {"zh": "A"}})
        register("ns2", {"b": {"zh": "B"}})
        assert t("ns1.a", "zh") == "A"
        assert t("ns2.b", "zh") == "B"


class TestSharedLabels:
    def test_category_labels(self):
        assert category_label("morning", "zh") == "晨起"
        assert category_label("morning", "en") == "Morning"
        assert category_label("morning", "ja") == "朝の振り返り"

    def test_period_labels(self):
        assert period_label("week", "zh") == "本周"
        assert period_label("week", "en") == "This week"
        assert period_label("week", "ja") == "今週"

    def test_all_categories_have_all_langs(self):
        """Every shared.cat.* key should have zh, en, ja."""
        for key, langs in _REGISTRY.items():
            if key.startswith("shared.cat."):
                for lang in ("zh", "en", "ja"):
                    assert lang in langs, f"{key} missing {lang}"

    def test_all_periods_have_all_langs(self):
        for key, langs in _REGISTRY.items():
            if key.startswith("shared.period."):
                for lang in ("zh", "en", "ja"):
                    assert lang in langs, f"{key} missing {lang}"
