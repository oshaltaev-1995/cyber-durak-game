from pathlib import Path


def test_frontend_has_no_known_analytics_or_advertising_trackers() -> None:
    repository = Path(__file__).resolve().parents[2]
    inspected = "\n".join(
        (
            (repository / "frontend" / "src" / "index.html").read_text(),
            (repository / "frontend" / "package.json").read_text(),
            (repository / "frontend" / "angular.json").read_text(),
        )
    ).casefold()

    for marker in (
        "google-analytics",
        "googletagmanager",
        "gtag(",
        "meta pixel",
        "connect.facebook.net",
        "plausible.io",
        "matomo",
        "hotjar",
        "mixpanel",
        "segment.com",
        "amplitude",
    ):
        assert marker not in inspected
