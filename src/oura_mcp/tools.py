"""The 11 Oura MCP tools. Field names, units, and docstrings are preserved
verbatim from upstream — this is the property the whole fork exists to
protect. Only the HTTP call site changed: `_get(...)` -> `self._client.get_collection(...)`.
"""

from datetime import date, timedelta
from typing import Optional

from fastmcp import FastMCP

from oura_mcp.client import OuraClient


def _default_range(date_from: Optional[str], date_to: Optional[str]) -> tuple:
    """Default to the last 7 days if no range given."""
    if not date_to:
        date_to = date.today().isoformat()
    if not date_from:
        date_from = (date.fromisoformat(date_to) - timedelta(days=7)).isoformat()
    return date_from, date_to


class OuraTools:
    def __init__(self, client: OuraClient) -> None:
        self._client = client

    def get_daily_activity(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[dict]:
        """Get daily activity summaries: steps, active/total calories, MET minutes
        by intensity, sedentary and resting time, inactivity alerts, and Oura's
        activity score. Dates are LOCAL calendar days as Oura assigns them.

        Useful for correlating movement with insulin sensitivity: low-step,
        high-sedentary days typically show reduced insulin sensitivity.

        Args:
            date_from: Start date YYYY-MM-DD (default: 7 days before date_to)
            date_to: End date YYYY-MM-DD inclusive (default: today)
        """
        date_from, date_to = _default_range(date_from, date_to)
        days = self._client.get_collection("daily_activity", {"start_date": date_from, "end_date": date_to})
        # Strip the 5-minute MET timeseries and minute-class string: they are
        # enormous and rarely needed for day-level analysis.
        return [
            {
                "day": d.get("day"),
                "score": d.get("score"),
                "steps": d.get("steps"),
                "active_calories": d.get("active_calories"),
                "total_calories": d.get("total_calories"),
                "equivalent_walking_distance_m": d.get("equivalent_walking_distance"),
                "high_activity_met_minutes": d.get("high_activity_met_minutes"),
                "medium_activity_met_minutes": d.get("medium_activity_met_minutes"),
                "low_activity_met_minutes": d.get("low_activity_met_minutes"),
                "sedentary_met_minutes": d.get("sedentary_met_minutes"),
                "sedentary_time_s": d.get("sedentary_time"),
                "resting_time_s": d.get("resting_time"),
                "non_wear_time_s": d.get("non_wear_time"),
                "inactivity_alerts": d.get("inactivity_alerts"),
                "average_met_minutes": d.get("average_met_minutes"),
            }
            for d in days
        ]

    def get_daily_readiness(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[dict]:
        """Get daily readiness: overall score, temperature deviation from baseline,
        and contributor scores (HRV balance, resting heart rate, recovery index,
        sleep balance, activity balance).

        Temperature deviation is a useful early-illness signal, and illness is a
        major driver of temporary insulin resistance.

        Args:
            date_from: Start date YYYY-MM-DD (default: 7 days before date_to)
            date_to: End date YYYY-MM-DD inclusive (default: today)
        """
        date_from, date_to = _default_range(date_from, date_to)
        days = self._client.get_collection("daily_readiness", {"start_date": date_from, "end_date": date_to})
        return [
            {
                "day": d.get("day"),
                "score": d.get("score"),
                "temperature_deviation_c": d.get("temperature_deviation"),
                "temperature_trend_deviation_c": d.get("temperature_trend_deviation"),
                "contributors": d.get("contributors"),
            }
            for d in days
        ]

    def get_daily_sleep(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[dict]:
        """Get daily sleep scores and contributors (deep, REM, efficiency, latency,
        restfulness, timing, total sleep).

        Args:
            date_from: Start date YYYY-MM-DD (default: 7 days before date_to)
            date_to: End date YYYY-MM-DD inclusive (default: today)
        """
        date_from, date_to = _default_range(date_from, date_to)
        days = self._client.get_collection("daily_sleep", {"start_date": date_from, "end_date": date_to})
        return [
            {
                "day": d.get("day"),
                "score": d.get("score"),
                "contributors": d.get("contributors"),
            }
            for d in days
        ]

    def get_sleep_periods(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[dict]:
        """Get detailed sleep periods: bedtimes, durations by stage, efficiency,
        average heart rate, average HRV, and lowest heart rate.

        Overnight HRV and resting HR trends often track systemic stress and
        illness, both of which affect insulin needs.

        Args:
            date_from: Start date YYYY-MM-DD (default: 7 days before date_to)
            date_to: End date YYYY-MM-DD inclusive (default: today)
        """
        date_from, date_to = _default_range(date_from, date_to)
        periods = self._client.get_collection("sleep", {"start_date": date_from, "end_date": date_to})
        return [
            {
                "day": p.get("day"),
                "type": p.get("type"),
                "bedtime_start": p.get("bedtime_start"),
                "bedtime_end": p.get("bedtime_end"),
                "total_sleep_duration_s": p.get("total_sleep_duration"),
                "time_in_bed_s": p.get("time_in_bed"),
                "efficiency": p.get("efficiency"),
                "deep_sleep_duration_s": p.get("deep_sleep_duration"),
                "rem_sleep_duration_s": p.get("rem_sleep_duration"),
                "light_sleep_duration_s": p.get("light_sleep_duration"),
                "awake_time_s": p.get("awake_time"),
                "average_heart_rate": p.get("average_heart_rate"),
                "lowest_heart_rate": p.get("lowest_heart_rate"),
                "average_hrv": p.get("average_hrv"),
            }
            for p in periods
        ]

    def get_workouts(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[dict]:
        """Get logged workouts: activity type, intensity, calories, and start/end
        times. Workout timing matters for insulin sensitivity windows (increased
        sensitivity typically persists for hours after activity).

        Args:
            date_from: Start date YYYY-MM-DD (default: 7 days before date_to)
            date_to: End date YYYY-MM-DD inclusive (default: today)
        """
        date_from, date_to = _default_range(date_from, date_to)
        workouts = self._client.get_collection("workout", {"start_date": date_from, "end_date": date_to})
        return [
            {
                "day": w.get("day"),
                "activity": w.get("activity"),
                "intensity": w.get("intensity"),
                "calories": w.get("calories"),
                "start_datetime": w.get("start_datetime"),
                "end_datetime": w.get("end_datetime"),
                "source": w.get("source"),
            }
            for w in workouts
        ]

    def get_activity_summary(self, days: int = 14) -> dict:
        """Compact multi-day activity summary for correlation with glucose data:
        per-day steps, sedentary hours, MET minutes, and activity score, plus
        period averages. Prefer this over get_daily_activity for longer ranges.

        Args:
            days: Number of days to summarize, ending today (default 14)
        """
        date_to = date.today().isoformat()
        date_from = (date.today() - timedelta(days=days)).isoformat()
        daily = self._client.get_collection("daily_activity", {"start_date": date_from, "end_date": date_to})
        if not daily:
            return {"error": "No activity data found", "from": date_from, "to": date_to}

        rows = {
            d["day"]: {
                "steps": d.get("steps"),
                "score": d.get("score"),
                "sedentary_hours": round((d.get("sedentary_time") or 0) / 3600, 1),
                "active_met_minutes": round(
                    (d.get("high_activity_met_minutes") or 0)
                    + (d.get("medium_activity_met_minutes") or 0)
                    + (d.get("low_activity_met_minutes") or 0),
                    0,
                ),
            }
            for d in daily
        }
        steps = [r["steps"] for r in rows.values() if r["steps"] is not None]
        return {
            "from": date_from,
            "to": date_to,
            "days": rows,
            "averages": {
                "steps": round(sum(steps) / len(steps)) if steps else None,
                "sedentary_hours": round(
                    sum(r["sedentary_hours"] for r in rows.values()) / len(rows), 1
                ),
            },
        }

    def get_heart_rate(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[dict]:
        """Get per-day heart rate summaries built from the intraday HR
        timeseries: min/avg/max bpm, reading count, and average bpm by source
        (awake, rest, sleep, session, workout). The raw timeseries is
        summarized per day because it is far too large to return directly.

        Args:
            date_from: Start date YYYY-MM-DD (default: 7 days before date_to)
            date_to: End date YYYY-MM-DD inclusive (default: today)
        """
        date_from, date_to = _default_range(date_from, date_to)
        points = self._client.get_collection(
            "heartrate",
            {
                "start_datetime": f"{date_from}T00:00:00",
                "end_datetime": f"{date_to}T23:59:59",
            },
        )
        days: dict = {}
        for p in points:
            bpm = p.get("bpm")
            ts = p.get("timestamp") or ""
            if bpm is None or len(ts) < 10:
                continue
            d = days.setdefault(ts[:10], {"bpms": [], "sources": {}})
            d["bpms"].append(bpm)
            d["sources"].setdefault(p.get("source") or "unknown", []).append(bpm)
        return [
            {
                "day": day,
                "readings": len(d["bpms"]),
                "bpm_min": min(d["bpms"]),
                "bpm_avg": round(sum(d["bpms"]) / len(d["bpms"]), 1),
                "bpm_max": max(d["bpms"]),
                "avg_by_source": {
                    s: round(sum(v) / len(v), 1)
                    for s, v in sorted(d["sources"].items())
                },
            }
            for day, d in sorted(days.items())
        ]

    def get_daily_stress(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[dict]:
        """Get daily stress summaries: seconds spent in high-stress and
        high-recovery zones plus Oura's day classification (restored /
        normal / stressful). Sustained stress raises cortisol, which tends
        to increase insulin needs.

        Args:
            date_from: Start date YYYY-MM-DD (default: 7 days before date_to)
            date_to: End date YYYY-MM-DD inclusive (default: today)
        """
        date_from, date_to = _default_range(date_from, date_to)
        days = self._client.get_collection("daily_stress", {"start_date": date_from, "end_date": date_to})
        return [
            {
                "day": d.get("day"),
                "stress_high_s": d.get("stress_high"),
                "recovery_high_s": d.get("recovery_high"),
                "day_summary": d.get("day_summary"),
            }
            for d in days
        ]

    def get_daily_spo2(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[dict]:
        """Get nightly blood oxygen: average SpO2 percentage and breathing
        disturbance index (higher = more disturbed breathing during sleep).

        Args:
            date_from: Start date YYYY-MM-DD (default: 7 days before date_to)
            date_to: End date YYYY-MM-DD inclusive (default: today)
        """
        date_from, date_to = _default_range(date_from, date_to)
        days = self._client.get_collection("daily_spo2", {"start_date": date_from, "end_date": date_to})
        return [
            {
                "day": d.get("day"),
                "spo2_avg_percent": (d.get("spo2_percentage") or {}).get("average"),
                "breathing_disturbance_index": d.get("breathing_disturbance_index"),
            }
            for d in days
        ]

    def get_sessions(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[dict]:
        """Get logged sessions (meditation, breathing, nap, relaxation,
        rest): type, mood, and start/end times. Heart rate and HRV
        timeseries are omitted to keep responses small.

        Args:
            date_from: Start date YYYY-MM-DD (default: 7 days before date_to)
            date_to: End date YYYY-MM-DD inclusive (default: today)
        """
        date_from, date_to = _default_range(date_from, date_to)
        sessions = self._client.get_collection("session", {"start_date": date_from, "end_date": date_to})
        return [
            {
                "day": s.get("day"),
                "type": s.get("type"),
                "mood": s.get("mood"),
                "start_datetime": s.get("start_datetime"),
                "end_datetime": s.get("end_datetime"),
            }
            for s in sessions
        ]

    def get_tags(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[dict]:
        """Get user-entered tags and notes (enhanced tags): tag type, custom
        name, free-text comment, and when they apply. Tags mark events like
        illness, travel, or alcohol, so they are useful for explaining
        anomalies in other metrics.

        Args:
            date_from: Start date YYYY-MM-DD (default: 7 days before date_to)
            date_to: End date YYYY-MM-DD inclusive (default: today)
        """
        date_from, date_to = _default_range(date_from, date_to)
        tags = self._client.get_collection("enhanced_tag", {"start_date": date_from, "end_date": date_to})
        return [
            {
                "start_day": t.get("start_day"),
                "end_day": t.get("end_day"),
                "tag_type_code": t.get("tag_type_code"),
                "custom_name": t.get("custom_name"),
                "comment": t.get("comment"),
                "start_time": t.get("start_time"),
                "end_time": t.get("end_time"),
            }
            for t in tags
        ]


TOOL_NAMES = (
    "get_daily_activity",
    "get_daily_readiness",
    "get_daily_sleep",
    "get_sleep_periods",
    "get_workouts",
    "get_activity_summary",
    "get_heart_rate",
    "get_daily_stress",
    "get_daily_spo2",
    "get_sessions",
    "get_tags",
)


def register_tools(mcp: FastMCP, tools: OuraTools) -> None:
    for name in TOOL_NAMES:
        mcp.tool()(getattr(tools, name))
