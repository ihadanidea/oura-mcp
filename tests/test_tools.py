import respx
from httpx import Response

from oura_mcp.client import OuraClient
from oura_mcp.config import OURA_BASE
from oura_mcp.tools import OuraTools


def _tools() -> OuraTools:
    return OuraTools(OuraClient(token="tok", base_url=OURA_BASE))


def _mock_endpoint(endpoint: str, fixture: dict) -> respx.Route:
    return respx.get(path__regex=rf"^/v2/usercollection/{endpoint}$").mock(
        return_value=Response(200, json=fixture)
    )


def test_get_daily_activity_field_mapping(load_fixture):
    fixture = load_fixture("daily_activity")
    _mock_endpoint("daily_activity", fixture)

    result = _tools().get_daily_activity(date_from="2026-08-10", date_to="2026-08-11")

    assert result[0] == {
        "day": "2026-08-10",
        "score": 82,
        "steps": 8342,
        "active_calories": 410,
        "total_calories": 2510,
        "equivalent_walking_distance_m": 9800,
        "high_activity_met_minutes": 12,
        "medium_activity_met_minutes": 38,
        "low_activity_met_minutes": 55,
        "sedentary_met_minutes": 20,
        "sedentary_time_s": 30600,
        "resting_time_s": 21600,
        "non_wear_time_s": 0,
        "inactivity_alerts": 1,
        "average_met_minutes": 1.4,
    }
    assert isinstance(result[0]["steps"], int)
    assert isinstance(result[0]["total_calories"], int)


def test_get_daily_readiness_field_mapping(load_fixture):
    fixture = load_fixture("daily_readiness")
    _mock_endpoint("daily_readiness", fixture)

    result = _tools().get_daily_readiness(date_from="2026-08-10", date_to="2026-08-11")

    assert result[1]["day"] == "2026-08-11"
    assert result[1]["temperature_deviation_c"] == 0.6
    assert result[1]["temperature_trend_deviation_c"] == 0.3
    assert result[1]["contributors"] == fixture["data"][1]["contributors"]


def test_get_daily_sleep_field_mapping(load_fixture):
    fixture = load_fixture("daily_sleep")
    _mock_endpoint("daily_sleep", fixture)

    result = _tools().get_daily_sleep(date_from="2026-08-10", date_to="2026-08-11")

    assert result == [
        {"day": "2026-08-10", "score": 85, "contributors": fixture["data"][0]["contributors"]},
        {"day": "2026-08-11", "score": 68, "contributors": fixture["data"][1]["contributors"]},
    ]


def test_get_sleep_periods_fidelity_golden_record(load_fixture):
    """The fidelity property the fork exists to protect: raw values, explicit
    unit suffixes, no human-formatted durations or times anywhere."""
    fixture = load_fixture("sleep_page1")
    fixture = {**fixture, "next_token": None}  # single page for this test
    _mock_endpoint("sleep", fixture)

    result = _tools().get_sleep_periods(date_from="2026-08-09", date_to="2026-08-10")

    assert result == [
        {
            "day": "2026-08-10",
            "type": "long_sleep",
            "bedtime_start": "2026-08-09T23:14:02-07:00",
            "bedtime_end": "2026-08-10T07:04:02-07:00",
            "total_sleep_duration_s": 27000,
            "time_in_bed_s": 28200,
            "efficiency": 91,
            "deep_sleep_duration_s": 5400,
            "rem_sleep_duration_s": 6300,
            "light_sleep_duration_s": 15300,
            "awake_time_s": 1200,
            "average_heart_rate": 54.0,
            "lowest_heart_rate": 47,
            "average_hrv": 42,
        }
    ]
    # Must survive as a plain int of seconds, never "7h 30m".
    assert isinstance(result[0]["total_sleep_duration_s"], int)
    assert result[0]["total_sleep_duration_s"] == 27000
    # Must round-trip as an offset-aware ISO 8601 string, never "11:14 PM".
    assert result[0]["bedtime_start"] == "2026-08-09T23:14:02-07:00"


def test_get_sleep_periods_paginates_across_both_fixture_pages(load_fixture):
    page1 = load_fixture("sleep_page1")
    page2 = load_fixture("sleep_page2")
    route = respx.get(path__regex=r"^/v2/usercollection/sleep$")
    route.side_effect = [Response(200, json=page1), Response(200, json=page2)]

    result = _tools().get_sleep_periods(date_from="2026-08-09", date_to="2026-08-11")

    assert [r["day"] for r in result] == ["2026-08-10", "2026-08-11"]
    assert route.call_count == 2


def test_get_workouts_field_mapping(load_fixture):
    fixture = load_fixture("workout")
    _mock_endpoint("workout", fixture)

    result = _tools().get_workouts(date_from="2026-08-10", date_to="2026-08-11")

    assert result[0] == {
        "day": "2026-08-10",
        "activity": "cycling",
        "intensity": "moderate",
        "calories": 480.0,
        "start_datetime": "2026-08-10T17:02:00-07:00",
        "end_datetime": "2026-08-10T18:11:00-07:00",
        "source": "autodetected",
    }


def test_get_activity_summary_computes_averages(load_fixture):
    fixture = load_fixture("daily_activity")
    _mock_endpoint("daily_activity", fixture)

    result = _tools().get_activity_summary(days=14)

    assert set(result["days"]) == {"2026-08-10", "2026-08-11"}
    assert result["days"]["2026-08-10"]["steps"] == 8342
    assert result["days"]["2026-08-10"]["sedentary_hours"] == round(30600 / 3600, 1)
    assert result["averages"]["steps"] == round((8342 + 5210) / 2)


def test_get_activity_summary_handles_empty_range():
    respx.get(path__regex=r"^/v2/usercollection/daily_activity$").mock(
        return_value=Response(200, json={"data": [], "next_token": None})
    )

    result = _tools().get_activity_summary(days=14)

    assert result["error"] == "No activity data found"


def test_get_heart_rate_summarizes_per_day_and_source(load_fixture):
    fixture = load_fixture("heartrate")
    _mock_endpoint("heartrate", fixture)

    result = _tools().get_heart_rate(date_from="2026-08-10", date_to="2026-08-11")

    day1 = next(r for r in result if r["day"] == "2026-08-10")
    assert day1["readings"] == 5
    assert day1["bpm_min"] == 46
    assert day1["bpm_max"] == 128
    assert day1["avg_by_source"]["sleep"] == round((48 + 46) / 2, 1)
    assert day1["avg_by_source"]["workout"] == 128
    # The raw timeseries must not be returned, only the per-day summary.
    assert "bpm" not in day1 and "timestamp" not in day1


def test_get_daily_stress_field_mapping(load_fixture):
    fixture = load_fixture("daily_stress")
    _mock_endpoint("daily_stress", fixture)

    result = _tools().get_daily_stress(date_from="2026-08-10", date_to="2026-08-11")

    assert result[1] == {
        "day": "2026-08-11",
        "stress_high_s": 12600,
        "recovery_high_s": 3600,
        "day_summary": "stressful",
    }


def test_get_daily_spo2_field_mapping(load_fixture):
    fixture = load_fixture("daily_spo2")
    _mock_endpoint("daily_spo2", fixture)

    result = _tools().get_daily_spo2(date_from="2026-08-10", date_to="2026-08-11")

    assert result[0] == {
        "day": "2026-08-10",
        "spo2_avg_percent": 97.2,
        "breathing_disturbance_index": 3,
    }


def test_get_sessions_field_mapping(load_fixture):
    fixture = load_fixture("session")
    _mock_endpoint("session", fixture)

    result = _tools().get_sessions(date_from="2026-08-10", date_to="2026-08-11")

    assert result[0] == {
        "day": "2026-08-10",
        "type": "meditation",
        "mood": "good",
        "start_datetime": "2026-08-10T21:00:00-07:00",
        "end_datetime": "2026-08-10T21:15:00-07:00",
    }


def test_get_tags_field_mapping(load_fixture):
    fixture = load_fixture("enhanced_tag")
    _mock_endpoint("enhanced_tag", fixture)

    result = _tools().get_tags(date_from="2026-08-10", date_to="2026-08-11")

    assert result[0] == {
        "start_day": "2026-08-10",
        "end_day": "2026-08-11",
        "tag_type_code": "illness",
        "custom_name": None,
        "comment": "Mild cold, felt run down all day",
        "start_time": "2026-08-10T08:00:00",
        "end_time": "2026-08-11T20:00:00",
    }
