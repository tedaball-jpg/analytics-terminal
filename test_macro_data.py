from datetime import date

import pytest

from macro_data import (
    DataUnavailable,
    bank_rate_changes,
    fetch_fred_series,
    fetch_json_series,
    fetch_us_cpi_readings,
    fetch_yield_curve,
    parse_month,
    parse_quarter,
)


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


# --- fetch_fred_series: FRED's plain CSV, used for US ECO data and the GC widening -------------


class FakeCsvResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def test_fetch_fred_series_parses_a_normal_response(monkeypatch):
    csv_text = "observation_date,DGS2\n2026-01-02,4.50\n2026-01-03,4.55\n"
    monkeypatch.setattr("macro_data.requests.get", lambda *a, **k: FakeCsvResponse(csv_text))
    result = fetch_fred_series("DGS2", "US 2-year Treasury")
    assert result == [(date(2026, 1, 2), 4.50), (date(2026, 1, 3), 4.55)]


def test_fetch_fred_series_skips_missing_observations_marked_empty(monkeypatch):
    # FRED's actual convention for most series: a missing observation (e.g. a holiday,
    # or a reading not yet published) is an empty string, not a placeholder character.
    csv_text = "observation_date,DGS2\n2026-01-02,4.50\n2026-01-03,\n2026-01-04,4.60\n"
    monkeypatch.setattr("macro_data.requests.get", lambda *a, **k: FakeCsvResponse(csv_text))
    result = fetch_fred_series("DGS2", "US 2-year Treasury")
    assert result == [(date(2026, 1, 2), 4.50), (date(2026, 1, 4), 4.60)]


def test_fetch_fred_series_skips_missing_observations_marked_with_a_dot(monkeypatch):
    # FRED's documented convention (seen less often in practice than an empty string,
    # but still used by some series), so both are treated as missing.
    csv_text = "observation_date,DGS2\n2026-01-02,4.50\n2026-01-03,.\n2026-01-04,4.60\n"
    monkeypatch.setattr("macro_data.requests.get", lambda *a, **k: FakeCsvResponse(csv_text))
    result = fetch_fred_series("DGS2", "US 2-year Treasury")
    assert result == [(date(2026, 1, 2), 4.50), (date(2026, 1, 4), 4.60)]


def test_fetch_fred_series_raises_data_unavailable_on_a_network_error(monkeypatch):
    import requests

    def broken_get(*a, **k):
        raise requests.exceptions.ConnectionError("no route to host")

    monkeypatch.setattr("macro_data.requests.get", broken_get)
    with pytest.raises(DataUnavailable, match="could not fetch"):
        fetch_fred_series("DGS2", "US 2-year Treasury")


def test_fetch_fred_series_raises_data_unavailable_when_every_row_is_missing(monkeypatch):
    csv_text = "observation_date,DGS2\n2026-01-02,.\n2026-01-03,.\n"
    monkeypatch.setattr("macro_data.requests.get", lambda *a, **k: FakeCsvResponse(csv_text))
    with pytest.raises(DataUnavailable, match="no .* data"):
        fetch_fred_series("DGS2", "US 2-year Treasury")


def test_fetch_fred_series_raises_data_unavailable_on_malformed_csv(monkeypatch):
    monkeypatch.setattr("macro_data.requests.get", lambda *a, **k: FakeCsvResponse("not,a,valid,fred,csv\n1,2,3,4,5\n"))
    with pytest.raises(DataUnavailable, match="unexpected"):
        fetch_fred_series("DGS2", "US 2-year Treasury")


def test_fetch_yield_curve_rejects_an_unknown_country():
    with pytest.raises(ValueError):
        fetch_yield_curve("FR")


def test_fetch_us_cpi_readings_rounds_to_one_decimal_place(monkeypatch):
    # A 13-month CPI index series engineered to give a YoY rate with more precision
    # than is meaningful (105.5 / 100 - 1 = 5.5%, but with noisy intermediate months
    # that would otherwise carry through as floating-point noise).
    rows = "\n".join(f"2025-{m:02d}-01,{100 + m * 0.0137:.6f}" for m in range(1, 13))
    csv_text = f"observation_date,CPIAUCSL\n{rows}\n2026-01-01,105.5\n"
    monkeypatch.setattr("macro_data.requests.get", lambda *a, **k: FakeCsvResponse(csv_text))
    readings = fetch_us_cpi_readings()
    assert len(readings) == 1
    assert readings[0][1] == round(readings[0][1], 1)
