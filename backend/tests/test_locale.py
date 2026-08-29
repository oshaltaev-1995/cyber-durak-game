from kiba_api.emailing import password_reset_email, verification_email
from kiba_api.locale import Locale, parse_locale


def test_supported_locale_parsing_and_fallback() -> None:
    assert parse_locale("ru") is Locale.RU
    assert parse_locale("ru-RU, en;q=0.8") is Locale.RU
    assert parse_locale("en-US") is Locale.EN
    assert parse_locale("de-DE") is Locale.RU
    assert parse_locale(None) is Locale.RU


def test_verification_and_password_reset_templates_are_complete_in_both_locales() -> None:
    link = "https://example.test/token"
    ru_verification = verification_email(Locale.RU, link)
    en_verification = verification_email(Locale.EN, link)
    ru_reset = password_reset_email(Locale.RU, link)
    en_reset = password_reset_email(Locale.EN, link)

    assert ru_verification[0] == "Подтвердите email — KIBA"
    assert en_verification[0] == "Verify your email — KIBA"
    assert ru_reset[0] == "Сброс пароля — KIBA"
    assert en_reset[0] == "Reset your password — KIBA"
    assert all(link in body for _, body in (ru_verification, en_verification, ru_reset, en_reset))
