from datetime import date

import pytest

from macro_data import DataUnavailable, bank_rate_changes, fetch_json_series, parse_month, parse_quarter


def test_parse_month_by_hand():
    assert parse_month("2026 AUG") == date(2026, 8, 1)


def test_parse_month_is_case_insensitive():
    assert parse_month("2026 aug") == date(2026, 8, 1)


def test_parse_quarter_by_hand():
    # Q1 starts in January, Q2 in April, Q3 in July, Q4 in October.
    assert parse_quarter("2026 Q1") == date(2026, 1, 1)
    assert parse_quarter("2026 Q2") == date(2026, 4, 1)
    assert parse_quarter("2026 Q3") == date(2026, 7, 1)
    assert parse_quarter("2026 Q4") == date(2026, 10, 1)


def test_bank_rate_changes_collapses_a_flat_run():
    # The rate is flat between MPC decisions, so only the days it actually changed should remain.
    series = [
        (date(2026, 1, 1), 4.5),
        (date(2026, 1, 2), 4.5),
        (date(2026, 1, 3), 4.5),
        (date(2026, 2, 1), 4.25),
        (date(2026, 2, 2), 4.25),
        (date(2026, 3, 1), 4.0),
    ]
    changes = bank_rate_changes(series)
    assert changes == [(date(2026, 1, 1), 4.5), (date(2026, 2, 1), 4.25), (date(2026, 3, 1), 4.0)]


def test_bank_rate_changes_keeps_every_row_when_the_rate_never_repeats():
    series = [(date(2026, 1, 1), 4.5), (date(2026, 2, 1), 4.25)]
    assert bank_rate_changes(series) == series


def test_bank_rate_changes_of_an_empty_series_is_empty():
    assert bank_rate_changes([]) == []


def test_fetch_json_series_raises_data_unavailable_on_a_network_error(monkeypatch):
    import requests

    def broken_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError("no route to host")

    monkeypatch.setattr("macro_data.requests.get", broken_get)
    with pytest.raises(DataUnavailable, match="could not fetch"):
        fetch_json_series("http://example.invalid", "months", "CPI inflation")


def test_fetch_json_series_raises_data_unavailable_on_a_malformed_response(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"unexpected_key": []}

    monkeypatch.setattr("macro_data.requests.get", lambda *a, **k: FakeResponse())
    with pytest.raises(DataUnavailable, match="unexpected"):
        fetch_json_series("http://example.invalid", "months", "CPI inflation")
