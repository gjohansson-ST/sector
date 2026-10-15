from custom_components.sector.client import RequestMetrics


def test_request_metrics_counts_total_and_each_endpoint(monkeypatch) -> None:
    current_time = 100.0
    monkeypatch.setattr(
        "custom_components.sector.client.time.monotonic",
        lambda: current_time,
    )
    metrics = RequestMetrics()

    metrics.record("Logs")
    metrics.record("Logs")
    metrics.record("get_panel_list")
    metrics.record()

    result = metrics.get()

    assert result == {
        "requests_per_minute_total": 4,
        "requests_per_minute_by_endpoint": {
            "Logs": 2,
            "get_panel_list": 1,
        },
        "requests_per_hour_total": 4,
        "requests_per_hour_by_endpoint": {
            "Logs": 2,
            "get_panel_list": 1,
        },
    }


def test_request_metrics_keeps_minute_and_hourly_counts_after_one_second(
    monkeypatch,
) -> None:
    current_time = 100.0
    monkeypatch.setattr(
        "custom_components.sector.client.time.monotonic",
        lambda: current_time,
    )
    metrics = RequestMetrics()
    metrics.record("Logs")
    metrics.record("get_panel_info")

    current_time = 101.0

    assert metrics.get() == {
        "requests_per_minute_total": 2,
        "requests_per_minute_by_endpoint": {
            "Logs": 1,
            "get_panel_info": 1,
        },
        "requests_per_hour_total": 2,
        "requests_per_hour_by_endpoint": {
            "Logs": 1,
            "get_panel_info": 1,
        },
    }


def test_request_metrics_removes_requests_older_than_one_minute(
    monkeypatch,
) -> None:
    current_time = 100.0
    monkeypatch.setattr(
        "custom_components.sector.client.time.monotonic",
        lambda: current_time,
    )
    metrics = RequestMetrics()
    metrics.record("Logs")

    current_time = 160.0

    assert metrics.get() == {
        "requests_per_minute_total": 0,
        "requests_per_minute_by_endpoint": {},
        "requests_per_hour_total": 1,
        "requests_per_hour_by_endpoint": {"Logs": 1},
    }


def test_request_metrics_removes_requests_older_than_one_hour(monkeypatch) -> None:
    current_time = 100.0
    monkeypatch.setattr(
        "custom_components.sector.client.time.monotonic",
        lambda: current_time,
    )
    metrics = RequestMetrics()
    metrics.record("Logs")

    current_time = 3700.0

    assert metrics.get() == {
        "requests_per_minute_total": 0,
        "requests_per_minute_by_endpoint": {},
        "requests_per_hour_total": 0,
        "requests_per_hour_by_endpoint": {},
    }
