"""Tests for process parsing and formatting helpers."""

from cleanup_orphans.process import (
    format_cpu,
    format_elapsed,
    parse_cpu_minutes,
    parse_elapsed_seconds,
)


class TestParseCpuMinutes:
    def test_minutes_seconds(self) -> None:
        assert parse_cpu_minutes("5:30.00") == 5.5

    def test_hours_minutes_seconds(self) -> None:
        result = parse_cpu_minutes("1:30:00.00")
        assert result == 90.0

    def test_zero(self) -> None:
        assert parse_cpu_minutes("0:00.00") == 0.0


class TestParseElapsedSeconds:
    def test_minutes_seconds(self) -> None:
        assert parse_elapsed_seconds("05:30") == 330

    def test_hours_minutes_seconds(self) -> None:
        assert parse_elapsed_seconds("02:30:00") == 9_000

    def test_days(self) -> None:
        assert parse_elapsed_seconds("1-00:00:00") == 86_400

    def test_seconds_only(self) -> None:
        assert parse_elapsed_seconds("45") == 45


class TestFormatElapsed:
    def test_days(self) -> None:
        assert format_elapsed("2-03:00:00") == "2d 3h ago"

    def test_hours(self) -> None:
        assert format_elapsed("03:45:00") == "3h 45m ago"

    def test_minutes(self) -> None:
        assert format_elapsed("12:30") == "12m ago"

    def test_seconds(self) -> None:
        assert format_elapsed("45") == "45s ago"


class TestFormatCpu:
    def test_minutes_seconds(self) -> None:
        assert format_cpu("5:30.00") == "5m 30s"

    def test_sub_minute(self) -> None:
        assert format_cpu("0:02.50") == "2.5s"

    def test_over_hour(self) -> None:
        assert format_cpu("120:00.00") == "2h 0m"

    def test_hours_format(self) -> None:
        assert format_cpu("1:30:00") == "1h 30m"
