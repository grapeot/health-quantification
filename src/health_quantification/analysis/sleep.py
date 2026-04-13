from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from zoneinfo import ZoneInfo


@dataclass(slots=True)
class SleepSessionMetrics:
    session_index: int
    session_type: str
    start_local: str
    end_local: str
    duration_hours: float
    sleep_hours: float
    in_bed_hours: float
    deep_sleep_hours: float
    core_sleep_hours: float
    rem_sleep_hours: float
    awake_hours: float
    unspecified_hours: float
    sample_count: int
    is_overnight: bool
    is_daytime: bool
    functional_date: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class DaySleepMetrics:
    date: str
    timezone: str
    bedtime: str | None
    wake_time: str | None
    total_sleep_hours: float
    main_sleep_hours: float
    additional_sleep_hours: float
    total_in_bed_hours: float
    sleep_efficiency: float | None
    deep_sleep_hours: float
    core_sleep_hours: float
    rem_sleep_hours: float
    awake_hours: float
    unspecified_hours: float
    sample_count: int
    nap_hours: float = 0.0
    has_nap: bool = False
    sessions: list[SleepSessionMetrics] | None = None
    lead_in_sleep: SleepSessionMetrics | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class SleepAnalysisSummary:
    period_days: int
    total_samples: int
    days_with_data: int
    days_missing: int
    avg_sleep_hours: float
    avg_bedtime: str | None
    avg_wake_time: str | None
    avg_deep_hours: float
    avg_core_hours: float
    avg_rem_hours: float
    avg_efficiency: float | None
    avg_lead_in_sleep_hours: float
    daily: list[DaySleepMetrics]
    functional_daily: list[DaySleepMetrics]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


ASLEEP_STAGES = {"asleep_deep", "asleep_core", "asleep_rem", "asleep_unspecified"}


def _tz(tz_name: str) -> ZoneInfo:
    return ZoneInfo(tz_name)


def _to_local(dt_str: str, tz: ZoneInfo) -> datetime:
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    return dt.astimezone(tz)


def _stage_duration_hours(sample: dict[str, object]) -> float:
    start = datetime.fromisoformat(str(sample["start_at"]).replace("Z", "+00:00"))
    end_str = sample.get("end_at")
    if end_str is None:
        return 0.0
    end = datetime.fromisoformat(str(end_str).replace("Z", "+00:00"))
    delta = end - start
    return max(0.0, delta.total_seconds() / 3600)


def _split_into_sessions(
    samples: list[dict[str, object]],
    tz: ZoneInfo,
    gap_threshold_hours: float = 2.0,
) -> list[list[dict[str, object]]]:
    if not samples:
        return []

    sorted_samples = sorted(samples, key=lambda sample: _to_local(str(sample["start_at"]), tz))
    sessions: list[list[dict[str, object]]] = []
    current_session: list[dict[str, object]] = [sorted_samples[0]]
    previous_end = _to_local(str(sorted_samples[0].get("end_at") or sorted_samples[0]["start_at"]), tz)

    for sample in sorted_samples[1:]:
        start_local = _to_local(str(sample["start_at"]), tz)
        gap_hours = (start_local - previous_end).total_seconds() / 3600
        if gap_hours > gap_threshold_hours:
            sessions.append(current_session)
            current_session = [sample]
        else:
            current_session.append(sample)

        previous_end = _to_local(str(sample.get("end_at") or sample["start_at"]), tz)

    sessions.append(current_session)
    return sessions


def _session_stage_hours(samples: list[dict[str, object]]) -> dict[str, float]:
    stage_hours: dict[str, float] = {}
    for sample in samples:
        stage = str(sample["stage"])
        stage_hours[stage] = stage_hours.get(stage, 0.0) + _stage_duration_hours(sample)
    return stage_hours


def _session_asleep_hours(samples: list[dict[str, object]]) -> float:
    stage_hours = _session_stage_hours(samples)
    return sum(hours for stage, hours in stage_hours.items() if stage in ASLEEP_STAGES)


def _session_bounds_local(samples: list[dict[str, object]], tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = min(_to_local(str(sample["start_at"]), tz) for sample in samples)
    end = max(_to_local(str(sample.get("end_at") or sample["start_at"]), tz) for sample in samples)
    return start, end


def _is_daytime_nap_session(
    *,
    start_local: datetime,
    end_local: datetime,
    asleep_hours: float,
    stage_hours: dict[str, float],
) -> bool:
    is_overnight = end_local.date() > start_local.date()
    if is_overnight:
        return False

    start_hour = start_local.hour + start_local.minute / 60
    end_hour = end_local.hour + end_local.minute / 60
    daytime_window = start_hour >= 9 and end_hour <= 18.5
    short_sleep = asleep_hours <= 3.0
    has_sleep = asleep_hours >= 0.3
    mostly_unspecified = stage_hours.get("asleep_unspecified", 0.0) >= asleep_hours * 0.5 if asleep_hours > 0 else False
    return has_sleep and daytime_window and short_sleep and (mostly_unspecified or asleep_hours <= 2.5)


def _build_session_metrics(
    *,
    sessions: list[list[dict[str, object]]],
    tz: ZoneInfo,
    main_session_index: int | None,
) -> list[SleepSessionMetrics]:
    session_metrics: list[SleepSessionMetrics] = []

    for index, session in enumerate(sessions):
        stage_hours = _session_stage_hours(session)
        asleep_hours = _session_asleep_hours(session)
        start_local, end_local = _session_bounds_local(session, tz)
        duration_hours = max(0.0, (end_local - start_local).total_seconds() / 3600)
        is_overnight = end_local.date() > start_local.date()
        is_daytime = 9 <= start_local.hour < 18 and end_local.date() == start_local.date()

        if main_session_index is not None and index == main_session_index:
            session_type = "main"
        elif _is_daytime_nap_session(
            start_local=start_local,
            end_local=end_local,
            asleep_hours=asleep_hours,
            stage_hours=stage_hours,
        ):
            session_type = "nap"
        else:
            session_type = "additional_sleep"

        functional_date: str | None = None
        if session_type != "nap":
            if is_overnight:
                functional_date = end_local.date().isoformat()
            elif start_local.hour < 12:
                functional_date = end_local.date().isoformat()

        session_metrics.append(
            SleepSessionMetrics(
                session_index=index,
                session_type=session_type,
                start_local=start_local.isoformat(),
                end_local=end_local.isoformat(),
                duration_hours=round(duration_hours, 2),
                sleep_hours=round(asleep_hours, 2),
                in_bed_hours=round(sum(_stage_duration_hours(sample) for sample in session), 2),
                deep_sleep_hours=round(stage_hours.get("asleep_deep", 0.0), 2),
                core_sleep_hours=round(stage_hours.get("asleep_core", 0.0), 2),
                rem_sleep_hours=round(stage_hours.get("asleep_rem", 0.0), 2),
                awake_hours=round(stage_hours.get("awake", 0.0), 2),
                unspecified_hours=round(stage_hours.get("asleep_unspecified", 0.0), 2),
                sample_count=len(session),
                is_overnight=is_overnight,
                is_daytime=is_daytime,
                functional_date=functional_date,
            )
        )

    return session_metrics


def _lead_in_sleep_for_date(
    *,
    session_metrics: list[SleepSessionMetrics],
    date_str: str,
) -> SleepSessionMetrics | None:
    candidates = [
        session
        for session in session_metrics
        if session.functional_date == date_str and session.session_type != "nap"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda session: session.end_local)


def compute_day_metrics(
    samples: list[dict[str, object]],
    date_str: str,
    tz_name: str,
) -> DaySleepMetrics:
    tz = _tz(tz_name)
    bedtime: datetime | None = None
    wake_time: datetime | None = None
    total_in_bed = 0.0
    sample_count = len(samples)
    sessions = _split_into_sessions(samples, tz)
    session_sleep_hours = [_session_asleep_hours(session) for session in sessions]

    main_session_index: int | None = None
    if session_sleep_hours:
        main_session_index = max(range(len(sessions)), key=lambda index: session_sleep_hours[index])

    session_metrics = _build_session_metrics(
        sessions=sessions,
        tz=tz,
        main_session_index=main_session_index,
    )

    if len(session_metrics) == 1 and session_metrics[0].session_type == "main":
        only_session = session_metrics[0]
        if only_session.is_daytime and not only_session.is_overnight and only_session.sleep_hours < 3.0:
            only_session.session_type = "nap"
            main_session_index = None

    main_session = sessions[main_session_index] if sessions and main_session_index is not None else []
    main_stage_hours = _session_stage_hours(main_session)
    main_sleep = session_sleep_hours[main_session_index] if session_sleep_hours and main_session_index is not None else 0.0
    nap_hours = round(sum(session.sleep_hours for session in session_metrics if session.session_type == "nap"), 2)
    additional_sleep_hours = round(
        sum(session.sleep_hours for session in session_metrics if session.session_type == "additional_sleep"),
        2,
    )
    total_sleep = round(main_sleep + nap_hours + additional_sleep_hours, 2)

    for session in sessions:
        for sample in session:
            total_in_bed += _stage_duration_hours(sample)

    for sample in main_session:
        start_local = _to_local(str(sample["start_at"]), tz)
        end_str = sample.get("end_at")
        end_local = _to_local(str(end_str), tz) if end_str else None

        stage = str(sample["stage"])
        if stage in ASLEEP_STAGES or stage == "in_bed":
            start_hour = start_local.hour
            if start_hour >= 16:
                if bedtime is None or start_local.time() < bedtime.time():
                    bedtime = start_local
            if start_hour <= 12:
                if end_local and (wake_time is None or end_local.time() > wake_time.time()):
                    wake_time = end_local

    if bedtime is None and main_session:
        earliest = min(
            _to_local(str(s["start_at"]), tz) for s in main_session
        )
        bedtime = earliest

    efficiency = (total_sleep / total_in_bed * 100) if total_in_bed > 0 else None

    deep = main_stage_hours.get("asleep_deep", 0.0)
    core = main_stage_hours.get("asleep_core", 0.0)
    rem = main_stage_hours.get("asleep_rem", 0.0)
    awake = main_stage_hours.get("awake", 0.0)
    unspecified = main_stage_hours.get("asleep_unspecified", 0.0)

    is_nap = any(session.session_type == "nap" for session in session_metrics)
    lead_in_sleep = _lead_in_sleep_for_date(session_metrics=session_metrics, date_str=date_str)

    return DaySleepMetrics(
        date=date_str,
        timezone=tz_name,
        bedtime=bedtime.strftime("%H:%M") if bedtime else None,
        wake_time=wake_time.strftime("%H:%M") if wake_time else None,
        total_sleep_hours=total_sleep,
        main_sleep_hours=round(main_sleep, 2),
        additional_sleep_hours=additional_sleep_hours,
        total_in_bed_hours=round(total_in_bed, 2),
        sleep_efficiency=round(efficiency, 1) if efficiency is not None else None,
        deep_sleep_hours=round(deep, 2),
        core_sleep_hours=round(core, 2),
        rem_sleep_hours=round(rem, 2),
        awake_hours=round(awake, 2),
        unspecified_hours=round(unspecified, 2),
        sample_count=sample_count,
        nap_hours=nap_hours,
        has_nap=is_nap,
        sessions=session_metrics,
        lead_in_sleep=lead_in_sleep,
    )


def assign_samples_to_days(
    samples: list[dict[str, object]],
    tz_name: str,
) -> dict[str, list[dict[str, object]]]:
    tz = _tz(tz_name)
    sessions = _split_into_sessions(samples, tz)
    days: dict[str, list[dict[str, object]]] = {}
    for session in sessions:
        earliest_start = min(
            _to_local(str(s["start_at"]), tz) for s in session
        )
        date_str = earliest_start.date().isoformat()
        days.setdefault(date_str, []).extend(session)
    return days


def compute_analysis(
    samples: list[dict[str, object]],
    days: int,
    tz_name: str,
) -> SleepAnalysisSummary:
    days_map = assign_samples_to_days(samples, tz_name)

    end_date = datetime.now(_tz(tz_name)).date()
    start_date = end_date - timedelta(days=days - 1)
    all_dates = [(start_date + timedelta(days=i)).isoformat() for i in range(days)]

    daily_metrics: list[DaySleepMetrics] = []
    functional_daily_metrics: list[DaySleepMetrics] = []
    sleep_hours_list: list[float] = []
    efficiency_list: list[float] = []
    deep_list: list[float] = []
    core_list: list[float] = []
    rem_list: list[float] = []
    lead_in_hours_list: list[float] = []

    for d in all_dates:
        day_samples = days_map.get(d, [])
        if not day_samples:
            daily_metrics.append(DaySleepMetrics(
                date=d, timezone=tz_name,
                bedtime=None, wake_time=None,
                total_sleep_hours=0.0, main_sleep_hours=0.0, additional_sleep_hours=0.0, total_in_bed_hours=0.0,
                sleep_efficiency=None,
                deep_sleep_hours=0.0, core_sleep_hours=0.0,
                rem_sleep_hours=0.0, awake_hours=0.0,
                unspecified_hours=0.0, sample_count=0, nap_hours=0.0, has_nap=False, sessions=[], lead_in_sleep=None,
            ))
            continue

        metrics = compute_day_metrics(day_samples, d, tz_name)
        daily_metrics.append(metrics)

        if metrics.main_sleep_hours >= 3.0:
            sleep_hours_list.append(metrics.main_sleep_hours)
            if metrics.sleep_efficiency is not None:
                efficiency_list.append(metrics.sleep_efficiency)
            deep_list.append(metrics.deep_sleep_hours)
            core_list.append(metrics.core_sleep_hours)
            rem_list.append(metrics.rem_sleep_hours)

    days_with_data = sum(1 for m in daily_metrics if m.sample_count > 0)
    days_missing = days - days_with_data

    avg_sleep = round(sum(sleep_hours_list) / len(sleep_hours_list), 2) if sleep_hours_list else 0.0
    avg_eff = round(sum(efficiency_list) / len(efficiency_list), 1) if efficiency_list else None
    avg_deep = round(sum(deep_list) / len(deep_list), 2) if deep_list else 0.0
    avg_core = round(sum(core_list) / len(core_list), 2) if core_list else 0.0
    avg_rem = round(sum(rem_list) / len(rem_list), 2) if rem_list else 0.0

    sessions_with_source: list[tuple[str, SleepSessionMetrics]] = []
    for metrics in daily_metrics:
        for session in metrics.sessions or []:
            sessions_with_source.append((metrics.date, session))

    for d in all_dates:
        lead_in_candidates = [
            (source_date, session)
            for source_date, session in sessions_with_source
            if session.functional_date == d and session.session_type != "nap"
        ]
        if not lead_in_candidates:
            functional_daily_metrics.append(DaySleepMetrics(
                date=d, timezone=tz_name,
                bedtime=None, wake_time=None,
                total_sleep_hours=0.0, main_sleep_hours=0.0, additional_sleep_hours=0.0, total_in_bed_hours=0.0,
                sleep_efficiency=None,
                deep_sleep_hours=0.0, core_sleep_hours=0.0,
                rem_sleep_hours=0.0, awake_hours=0.0,
                unspecified_hours=0.0, sample_count=0, nap_hours=0.0, has_nap=False, sessions=[], lead_in_sleep=None,
            ))
            continue

        source_date, lead_in_session = max(lead_in_candidates, key=lambda item: item[1].end_local)
        lead_in_hours_list.append(lead_in_session.sleep_hours)
        functional_daily_metrics.append(DaySleepMetrics(
            date=d,
            timezone=tz_name,
            bedtime=lead_in_session.start_local[11:16],
            wake_time=lead_in_session.end_local[11:16],
            total_sleep_hours=lead_in_session.sleep_hours,
            main_sleep_hours=lead_in_session.sleep_hours,
            additional_sleep_hours=0.0,
            total_in_bed_hours=lead_in_session.in_bed_hours,
            sleep_efficiency=round((lead_in_session.sleep_hours / lead_in_session.in_bed_hours) * 100, 1)
            if lead_in_session.in_bed_hours > 0 else None,
            deep_sleep_hours=lead_in_session.deep_sleep_hours,
            core_sleep_hours=lead_in_session.core_sleep_hours,
            rem_sleep_hours=lead_in_session.rem_sleep_hours,
            awake_hours=lead_in_session.awake_hours,
            unspecified_hours=lead_in_session.unspecified_hours,
            sample_count=lead_in_session.sample_count,
            nap_hours=0.0,
            has_nap=False,
            sessions=[lead_in_session],
            lead_in_sleep=lead_in_session,
        ))

    avg_lead_in_sleep = round(sum(lead_in_hours_list) / len(lead_in_hours_list), 2) if lead_in_hours_list else 0.0

    bedtimes: list[str] = [
        m.bedtime for m in daily_metrics if m.bedtime and m.main_sleep_hours >= 3.0
    ]
    wake_times: list[str] = [
        m.wake_time for m in daily_metrics if m.wake_time and m.main_sleep_hours >= 3.0
    ]

    avg_bedtime = _avg_time(bedtimes) if bedtimes else None
    avg_wake = _avg_time(wake_times) if wake_times else None

    return SleepAnalysisSummary(
        period_days=days,
        total_samples=len(samples),
        days_with_data=days_with_data,
        days_missing=days_missing,
        avg_sleep_hours=avg_sleep,
        avg_bedtime=avg_bedtime,
        avg_wake_time=avg_wake,
        avg_deep_hours=avg_deep,
        avg_core_hours=avg_core,
        avg_rem_hours=avg_rem,
        avg_efficiency=avg_eff,
        avg_lead_in_sleep_hours=avg_lead_in_sleep,
        daily=daily_metrics,
        functional_daily=functional_daily_metrics,
    )


def _avg_time(times: list[str]) -> str:
    total_seconds = 0
    for t in times:
        parts = t.split(":")
        total_seconds += int(parts[0]) * 3600 + int(parts[1]) * 60
    avg_sec = total_seconds // len(times)
    h = avg_sec // 3600
    m = (avg_sec % 3600) // 60
    return f"{h:02d}:{m:02d}"
