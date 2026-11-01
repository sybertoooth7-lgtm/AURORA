"""Grounded console assistant ("FRIDAY").

There is deliberately no language model behind this endpoint. Every figure
in a reply is read from the caller's own rows -- or the shared flight store
-- during the same request, so the assistant cannot invent a finding, a
flight or a payout. A plausible-sounding hallucination is the one failure
mode an operations console must not have; free-form questions outside the
known intents get an honest "I can't read that" instead.

Routing is keyword-based and deterministic, so the same question always
gets the same answer and the whole thing is testable without a provider.
Replies carry the figures they were built from (``facts``), deep links to
the page showing the same data (``links``) and follow-up questions the
assistant can actually answer (``suggestions``).
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.logging_conf import get_logger
from app.models.alert import Alert
from app.models.analysis import Analysis, AnalysisResult
from app.models.user import User
from app.provenance import count_by_provenance
from app.quota import current_daily_quota_usage
from app.robotics.flight import flight_store
from app.schemas.assistant import AssistantFact, AssistantLink, AssistantReply

logger = get_logger(__name__)

# Short labels mirror aurora-frontend/src/lib/types.ts. Duplicated on purpose:
# the API answers without a browser, so it cannot import the frontend map.
TYPE_LABELS = {
    "vegetation_stress": "Vegetation stress",
    "land_change": "Land change",
    "climate_impact": "Climate impact",
    "infrastructure_change": "Infrastructure change",
    "water_monitoring": "Water monitoring",
    "infrastructure_monitoring": "Infrastructure monitoring",
    "environmental_monitoring": "Environmental monitoring",
    "anomaly_detection": "Anomaly detection",
    "wildfire_risk": "Wildfire risk",
    "flood_monitoring": "Flood monitoring",
    "insurance_index": "Crop index (parametric insurance)",
    "robotics_inspection": "Robotics inspection",
}

TYPE_KEYWORDS = {
    "vegetation_stress": ("vegetation", "crop", "crops", "ndvi", "agriculture"),
    "land_change": ("land change", "land cover", "landcover"),
    "climate_impact": ("climate",),
    "infrastructure_change": ("infrastructure change",),
    "water_monitoring": ("water", "lake", "river"),
    "infrastructure_monitoring": ("infrastructure", "site monitoring"),
    "environmental_monitoring": ("environment", "ecosystem"),
    "anomaly_detection": ("anomaly", "anomalies"),
    "wildfire_risk": ("wildfire", "fire", "fires", "fuel", "dryness"),
    "flood_monitoring": ("flood", "floods", "inundation"),
    "insurance_index": ("insurance", "payout", "claim", "parametric"),
    "robotics_inspection": ("inspection", "inspections", "inspect"),
}

# Areas scanned when matching a question to one of the caller's areas by name.
NAME_SEARCH_LIMIT = 500

SUGGESTIONS_GENERAL = [
    "Give me an overview",
    "Show my unread alerts",
    "How's the fleet?",
    "Is my data real or simulated?",
    "What's my quota?",
    "List my areas",
]


@dataclass
class AreaSnapshot:
    id: int
    analysis_type: str
    label: str
    status: str
    latitude: float
    longitude: float
    radius_km: float
    monitor_interval_minutes: int | None
    created_at: datetime | None
    unread_alerts: int
    latest_severity: float | None = None
    latest_confidence: float | None = None
    latest_at: datetime | None = None


@dataclass
class AlertSnapshot:
    id: int
    analysis_id: int
    area_label: str
    alert_type: str
    title: str
    created_at: datetime | None


@dataclass
class Snapshot:
    user: User
    total_areas: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    monitored: int
    last_activity: datetime | None
    areas: list[AreaSnapshot]
    unread_alerts: int
    alerts_by_type: dict[str, int]
    recent_alerts: list[AlertSnapshot]
    quota_limit: int
    quota_used: int | None
    provenance: dict[str, int]
    flights: list[dict]
    flights_error: bool = False
    named_areas: list[tuple[int, str]] = field(default_factory=list)


def _owned(db: Session, user_id: int):
    return db.query(Analysis).filter(Analysis.user_id == user_id)


def _area_snapshots(
    db: Session, analyses: list[Analysis]
) -> list[AreaSnapshot]:
    """Attach each area's latest finding and unread-alert count.

    Two bounded roll-ups (latest result id per area, unread alerts per area)
    instead of a query per row, so describing five areas costs four queries
    in total no matter how much history the account has.
    """
    if not analyses:
        return []
    # Column attributes are typed as Column[int] by mypy under the legacy
    # declarative models; at runtime they are plain ints.
    ids = [cast(int, analysis.id) for analysis in analyses]
    latest_ids = [
        row[0]
        for row in db.query(func.max(AnalysisResult.id))
        .filter(AnalysisResult.analysis_id.in_(ids))
        .group_by(AnalysisResult.analysis_id)
        .all()
    ]
    latest: dict[int, AnalysisResult] = {}
    if latest_ids:
        for result in (
            db.query(AnalysisResult)
            .filter(AnalysisResult.id.in_(latest_ids))
            .all()
        ):
            latest[cast(int, result.analysis_id)] = result
    unread = {
        analysis_id: int(count)
        for analysis_id, count in db.query(
            AnalysisResult.analysis_id, func.count(Alert.id)
        )
        .join(Alert, Alert.analysis_result_id == AnalysisResult.id)
        .filter(
            AnalysisResult.analysis_id.in_(ids),
            Alert.is_read.is_(False),
        )
        .group_by(AnalysisResult.analysis_id)
        .all()
    }

    snapshots: list[AreaSnapshot] = []
    for analysis in analyses:
        area_id = cast(int, analysis.id)
        type_key = getattr(analysis.analysis_type, "value", str(analysis.analysis_type))
        result = latest.get(area_id)
        snapshots.append(
            AreaSnapshot(
                id=area_id,
                analysis_type=type_key,
                label=analysis.description or TYPE_LABELS.get(type_key, type_key),
                status=analysis.status or "unknown",
                latitude=analysis.latitude,
                longitude=analysis.longitude,
                radius_km=analysis.radius_km,
                monitor_interval_minutes=analysis.monitor_interval_minutes,
                created_at=analysis.created_at,
                unread_alerts=unread.get(analysis.id, 0),
                latest_severity=result.severity_score if result else None,
                latest_confidence=result.confidence if result else None,
                latest_at=result.created_at if result else None,
            )
        )
    return snapshots


def build_snapshot(db: Session, user: User) -> Snapshot:
    """Everything one answer may cite, read in a bounded number of queries."""
    settings = get_settings()
    owned = _owned(db, user.id)

    by_status = {
        str(status): int(count)
        for status, count in owned.with_entities(Analysis.status, func.count())
        .group_by(Analysis.status)
        .all()
    }
    by_type = {
        str(getattr(kind, "value", kind)): int(count)
        for kind, count in owned.with_entities(
            Analysis.analysis_type, func.count()
        )
        .group_by(Analysis.analysis_type)
        .all()
    }
    recent = (
        owned.order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .limit(5)
        .all()
    )

    unread_alerts = (
        db.query(Alert).filter(Alert.user_id == user.id, Alert.is_read.is_(False)).count()
    )
    alerts_by_type = {
        str(kind): int(count)
        for kind, count in db.query(Alert.alert_type, func.count())
        .filter(Alert.user_id == user.id, Alert.is_read.is_(False))
        .group_by(Alert.alert_type)
        .all()
    }
    alert_rows = (
        db.query(Alert, Analysis.id, Analysis.description, Analysis.analysis_type)
        .join(AnalysisResult, Alert.analysis_result_id == AnalysisResult.id)
        .join(Analysis, AnalysisResult.analysis_id == Analysis.id)
        .filter(Alert.user_id == user.id, Alert.is_read.is_(False))
        .order_by(Alert.created_at.desc(), Alert.id.desc())
        .limit(5)
        .all()
    )
    recent_alerts = [
        AlertSnapshot(
            id=alert.id,
            analysis_id=analysis_id,
            area_label=description
            or TYPE_LABELS.get(str(getattr(kind, "value", kind)), str(kind)),
            alert_type=alert.alert_type,
            title=alert.title,
            created_at=alert.created_at,
        )
        for alert, analysis_id, description, kind in alert_rows
    ]

    try:
        quota_used: int | None = current_daily_quota_usage(user.id, "analyses")
    except Exception:  # noqa: BLE001 - an unreachable quota store is "unknown", not zero
        logger.warning("assistant could not read the quota store", exc_info=True)
        quota_used = None

    flights: list[dict] = []
    flights_error = False
    try:
        flights = flight_store.list_flights()
    except Exception:  # noqa: BLE001 - report the outage instead of claiming an empty fleet
        logger.warning("assistant could not read the flight store", exc_info=True)
        flights_error = True

    named_areas = [
        (analysis_id, description.strip())
        for analysis_id, description in db.query(Analysis.id, Analysis.description)
        .filter(Analysis.user_id == user.id, Analysis.description.is_not(None))
        .order_by(Analysis.created_at.desc())
        .limit(NAME_SEARCH_LIMIT)
        .all()
        if description and len(description.strip()) >= 3
    ]

    return Snapshot(
        user=user,
        total_areas=sum(by_status.values()),
        by_status=by_status,
        by_type=by_type,
        monitored=owned.filter(Analysis.monitor_interval_minutes.is_not(None)).count(),
        last_activity=recent[0].created_at if recent else None,
        areas=_area_snapshots(db, recent),
        unread_alerts=unread_alerts,
        alerts_by_type=alerts_by_type,
        recent_alerts=recent_alerts,
        quota_limit=settings.MAX_ANALYSES_PER_USER_PER_DAY,
        quota_used=quota_used,
        provenance=count_by_provenance(db, user.id),
        flights=flights,
        flights_error=flights_error,
        named_areas=named_areas,
    )


def _normalize(message: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", message.lower()).split())


def _has(text: str, words: tuple[str, ...]) -> bool:
    return any(
        re.search(rf"\b{re.escape(word)}\b", text) is not None for word in words
    )


def _quota_question(text: str) -> bool:
    if _has(text, ("quota", "budget")):
        return True
    if _has(text, ("how many", "remaining", "left")) and _has(
        text, ("analysis", "analyses", "runs", "scan", "scans")
    ):
        return True
    return _has(text, ("limit", "limits")) and _has(
        text, ("analysis", "analyses", "daily", "today")
    )


def _is_greeting(text: str) -> bool:
    words = text.split()
    return (
        len(words) <= 4
        and bool(words)
        and words[0] in {"hi", "hello", "hey", "yo", "morning", "evening", "friday"}
    )


def _match_area_id(snapshot: Snapshot, text: str) -> int | None:
    by_id = re.search(r"\barea\s*(?:number|no|#)?\s*(\d+)\b", text)
    if by_id:
        return int(by_id.group(1))
    matches = [
        (analysis_id, description)
        for analysis_id, description in snapshot.named_areas
        if description.lower() in text
    ]
    if not matches:
        return None
    # Longest description wins: "north field" beats "field" when both exist.
    return max(matches, key=lambda pair: len(pair[1]))[0]


def _type_match(text: str) -> str | None:
    for type_key, words in TYPE_KEYWORDS.items():
        if _has(text, words):
            return type_key
    return None


ACTION_WORDS = (
    "delete",
    "remove",
    "stop",
    "cancel",
    "launch",
    "start",
    "create",
    "run",
    "reset",
    "change",
    "update",
    "add",
    "make",
    "schedule",
    "disable",
    "enable",
    "trigger",
)
READ_WORDS = (
    "how",
    "what",
    "when",
    "where",
    "which",
    "who",
    "list",
    "show",
    "tell",
    "describe",
    "explain",
    "status",
    "overview",
    "summary",
    "alert",
    "quota",
    "flight",
    "provenance",
    "real",
    "simulated",
)


def _route(text: str, area_id: int | None) -> str:
    if _has(text, ("thanks", "thank you", "cheers", "appreciate")):
        return "thanks"
    # An imperative that would change state is refused before any data
    # intent: "delete my areas" must not be answered with a polite list.
    if _has(text, ACTION_WORDS) and not _has(text, READ_WORDS):
        return "fallback"
    if area_id is not None:
        return "area_detail"
    if _has(text, ("insurance", "payout", "payouts", "claim", "claims", "parametric", "underwriting")):
        return "insurance"
    if _has(text, ("alert", "alerts", "warning", "warnings", "critical", "unread", "notification", "notifications", "inbox")):
        return "alerts"
    if _has(text, ("flight", "flights", "drone", "drones", "robot", "robots", "telemetry", "fleet")):
        return "flights"
    if _has(text, ("provenance", "simulated", "synthetic", "fake", "demo data", "data source", "real data")):
        return "provenance"
    if _quota_question(text):
        return "quota"
    if _has(text, ("verify", "verified", "verification", "confirmed")):
        return "verification"
    if _has(text, ("overview", "status", "summary", "briefing", "dashboard")) or _has(
        text, ("how are things", "how is my account", "what s happening", "whats happening")
    ):
        return "overview"
    if _has(text, ("help", "commands", "capabilities")) or _has(
        text, ("what can you do", "how do i use", "how do i create", "what do you know")
    ):
        return "help"
    if _has(text, ("who are you", "what are you", "your name", "who is this")):
        return "identity"
    if _is_greeting(text):
        return "greeting"
    if _has(text, ("area", "areas", "zone", "zones", "field", "fields", "site", "sites", "monitor", "monitored")):
        return "areas"
    if _type_match(text) is not None:
        return "areas"
    return "fallback"


def _when(value: datetime | None) -> str:
    if value is None:
        return "never"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%d %b %Y %H:%M UTC")


def _spread(counts: dict[str, int]) -> str:
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{key.replace('_', ' ')} {count}" for key, count in ordered) or "nothing yet"


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or f"{singular}s")


def _provenance_sentence(counts: dict[str, int]) -> str:
    if not counts:
        return "No results have landed yet, so there is nothing to label as real or simulated."
    real = counts.get("real", 0)
    simulated = counts.get("simulated", 0)
    unknown = counts.get("unknown", 0)
    parts = []
    if real:
        parts.append(f"{real} from real satellite observations")
    if simulated:
        parts.append(f"{simulated} simulated")
    if unknown:
        parts.append(f"{unknown} saved before provenance was tracked")
    named = [
        (bucket, count)
        for bucket, count in counts.items()
        if bucket not in {"real", "simulated", "unknown"}
    ]
    parts.extend(f"{count} labelled {bucket}" for bucket, count in named)
    return "Results by data source: " + ", ".join(parts) + "."


def _quota_sentence(snapshot: Snapshot) -> str:
    if snapshot.quota_used is None:
        return "I couldn't read today's quota just now, so I won't guess at it."
    remaining = max(snapshot.quota_limit - snapshot.quota_used, 0)
    return (
        f"Analysis quota: {snapshot.quota_used} of {snapshot.quota_limit} used today, "
        f"{remaining} left (resets at midnight UTC)."
    )


def _area_line(area: AreaSnapshot) -> str:
    bits = [area.label, f"#{area.id}", area.status]
    if area.latest_severity is not None:
        bits.append(f"severity {area.latest_severity:.2f}")
    if area.unread_alerts:
        bits.append(f"{area.unread_alerts} unread {_plural(area.unread_alerts, 'alert')}")
    return "• " + ", ".join(bits)


def _facts(*pairs: tuple[str, str]) -> list[AssistantFact]:
    return [AssistantFact(label=label, value=value) for label, value in pairs]


def _links(*pairs: tuple[str, str]) -> list[AssistantLink]:
    return [AssistantLink(label=label, href=href) for label, href in pairs]


def _overview(snapshot: Snapshot):
    if snapshot.total_areas == 0:
        return (
            "You don't have any areas yet. Create one with + New area and I'll read its "
            "findings, alerts and data provenance back to you here.",
            _facts(
                ("Areas", "0"),
                ("Unread alerts", str(snapshot.unread_alerts)),
                ("Real results", "0"),
                ("Simulated results", "0"),
            ),
            ["What can you do?", "How does monitoring work?", "What's my quota?"],
            _links(("New area", "/app/areas/new"), ("Overview", "/app")),
        )

    completed = snapshot.by_status.get("completed", 0)
    waiting = snapshot.total_areas - completed
    parts = [
        f"You have {snapshot.total_areas} {_plural(snapshot.total_areas, 'area')}: "
        f"{completed} completed"
        + (f", {waiting} still pending or running" if waiting else "")
        + "."
    ]
    if snapshot.monitored:
        parts.append(
            f"{snapshot.monitored} {_plural(snapshot.monitored, 'is', 'are')} on a monitoring schedule."
        )
    if snapshot.unread_alerts:
        parts.append(
            f"{snapshot.unread_alerts} unread {_plural(snapshot.unread_alerts, 'alert')} in the inbox."
        )
    else:
        parts.append("No unread alerts.")
    parts.append(_provenance_sentence(snapshot.provenance))
    parts.append(_quota_sentence(snapshot))
    parts.append(f"Latest activity: {_when(snapshot.last_activity)}.")

    facts = [
        ("Areas", str(snapshot.total_areas)),
        ("Completed", str(completed)),
        ("Monitored", str(snapshot.monitored)),
        ("Unread alerts", str(snapshot.unread_alerts)),
        ("Real results", str(snapshot.provenance.get("real", 0))),
        ("Simulated results", str(snapshot.provenance.get("simulated", 0))),
    ]
    if snapshot.quota_used is not None:
        facts.append(
            ("Quota left today", str(max(snapshot.quota_limit - snapshot.quota_used, 0)))
        )
    return (
        " ".join(parts),
        _facts(*facts),
        SUGGESTIONS_GENERAL,
        _links(("Overview", "/app"), ("Operations", "/app/operations")),
    )


def _alerts(snapshot: Snapshot):
    if snapshot.unread_alerts == 0:
        answer = "Your inbox is clear — no unread alerts."
        suggestions = ["Give me an overview", "Show my areas", "How's the fleet?"]
    else:
        lines = [
            f"{snapshot.unread_alerts} unread {_plural(snapshot.unread_alerts, 'alert')}. "
            "Most recent first:"
        ]
        lines.extend(
            f"• {alert.title} — {alert.area_label} ({_when(alert.created_at)})"
            for alert in snapshot.recent_alerts
        )
        answer = "\n".join(lines)
        if snapshot.unread_alerts > len(snapshot.recent_alerts):
            answer += (
                f"\n…and {snapshot.unread_alerts - len(snapshot.recent_alerts)} more. "
                "Open an area to read and acknowledge its alerts."
            )
        suggestions = ["Give me an overview", "Show my areas", "What's my quota?"]

    facts = [("Unread alerts", str(snapshot.unread_alerts))]
    for kind in ("critical", "warning", "info"):
        if kind in snapshot.alerts_by_type:
            facts.append((kind.capitalize(), str(snapshot.alerts_by_type[kind])))
    links = [("Overview", "/app")]
    links.extend(
        (f"Open {alert.area_label}", f"/app/areas/{alert.analysis_id}")
        for alert in snapshot.recent_alerts[:3]
    )
    return answer, _facts(*facts), suggestions, _links(*links)


def _flights(snapshot: Snapshot):
    if snapshot.flights_error:
        return (
            "I couldn't reach the flight telemetry store just now, so I won't guess at "
            "fleet status. The Fleet page will show it again as soon as the store is back.",
            _facts(("Telemetry store", "unreachable")),
            ["Show my unread alerts", "Give me an overview"],
            _links(("Fleet", "/app/fleet")),
        )
    if not snapshot.flights:
        return (
            "No flights are reporting telemetry right now. Frames appear here as soon as "
            "a drone or ground robot posts one.",
            _facts(("Flights reporting", "0")),
            ["Give me an overview", "List my areas"],
            _links(("Fleet", "/app/fleet"), ("Operations", "/app/operations")),
        )

    attention = [
        flight
        for flight in snapshot.flights
        if flight["flight_health"]["status"] in {"caution", "critical"}
    ]
    batteries = [
        flight["flight_health"]["battery_min"]
        for flight in snapshot.flights
        if flight["flight_health"].get("battery_min") is not None
    ]
    parts = [
        f"{len(snapshot.flights)} {_plural(len(snapshot.flights), 'flight')} reporting live telemetry "
        "(platform-wide, like the Fleet page)."
    ]
    if attention:
        parts.append(
            "Needs attention: "
            + ", ".join(
                f"{flight['flight_id']} ({flight['flight_health']['status']}"
                + (
                    f", lowest battery {flight['flight_health']['battery_min']:.0f}%"
                    if flight["flight_health"].get("battery_min") is not None
                    else ""
                )
                + ")"
                for flight in attention[:4]
            )
            + "."
        )
    else:
        parts.append("All of them are healthy.")
    if batteries:
        parts.append(f"Lowest battery across the fleet: {min(batteries):.0f}%.")

    facts = [("Flights reporting", str(len(snapshot.flights)))]
    facts.append(("Needs attention", str(len(attention))))
    facts.append(
        (
            "Flights",
            ", ".join(flight["flight_id"] for flight in snapshot.flights[:5])
            + ("…" if len(snapshot.flights) > 5 else ""),
        )
    )
    if batteries:
        facts.append(("Lowest battery", f"{min(batteries):.0f}%"))
    links = [("Fleet", "/app/fleet")] + [
        (f"Flight {flight['flight_id']}", f"/app/fleet/{flight['flight_id']}")
        for flight in attention[:3]
    ]
    return " ".join(parts), _facts(*facts), SUGGESTIONS_GENERAL, _links(*links)


def _provenance(snapshot: Snapshot):
    counts = snapshot.provenance
    answer = (
        _provenance_sentence(counts)
        + " Simulated runs are labelled in every response and on the dashboard; nothing is "
        "counted as real unless the satellite provider returned real observations, and older "
        "rows that predate the tracking stay 'unknown' rather than being guessed."
    )
    facts = [
        ("Real", str(counts.get("real", 0))),
        ("Simulated", str(counts.get("simulated", 0))),
        ("Unknown", str(counts.get("unknown", 0))),
    ]
    return answer, _facts(*facts), SUGGESTIONS_GENERAL, _links(("Overview", "/app"))


def _quota(snapshot: Snapshot):
    if snapshot.quota_used is None:
        return (
            "I couldn't read today's quota just now, so I won't guess at it. The Overview "
            "page shows the same figure once the quota store is back.",
            _facts(("Quota", "unavailable")),
            ["Give me an overview", "Show my areas"],
            _links(("Overview", "/app")),
        )
    remaining = max(snapshot.quota_limit - snapshot.quota_used, 0)
    answer = (
        f"You've used {snapshot.quota_used} of {snapshot.quota_limit} analyses today; "
        f"{remaining} remain. The cap resets at midnight UTC."
    )
    if remaining == 0:
        answer += " Creating a new area now will be refused until the reset."
    facts = [
        ("Used today", str(snapshot.quota_used)),
        ("Daily limit", str(snapshot.quota_limit)),
        ("Remaining", str(remaining)),
    ]
    return answer, _facts(*facts), SUGGESTIONS_GENERAL, _links(("Overview", "/app"))


def _verification(snapshot: Snapshot):
    if snapshot.user.email_verified:
        return (
            "Yes — your email is verified, so first-of-kind jobs (new analyses, AI inference, "
            "fleet operations) are available to you.",
            _facts(("Email verified", "yes")),
            SUGGESTIONS_GENERAL,
            _links(("Settings", "/app/settings"), ("New area", "/app/areas/new")),
        )
    return (
        "Not yet. Your account can read everything, but first-of-kind jobs wait for "
        "verification. Use 'Resend email' in the banner at the top of the console.",
        _facts(("Email verified", "no")),
        SUGGESTIONS_GENERAL,
        _links(("Settings", "/app/settings")),
    )


def _insurance(snapshot: Snapshot):
    settings = get_settings()
    insured = snapshot.by_type.get("insurance_index", 0)
    answer = (
        "Parametric checks run the insurance-index pipeline over an area and apply the policy "
        "trigger. Payout figures are estimates for underwriting review — never settlements, "
        "and simulated runs are labelled as such. "
    )
    answer += (
        f"You have {insured} insurance-index {_plural(insured, 'area')}."
        if insured
        else "You don't have any insurance-index areas yet."
    )
    facts = [
        ("Insurance-index areas", str(insured)),
        ("Default trigger threshold", f"{settings.INSURANCE_DEFAULT_TRIGGER_THRESHOLD:g}"),
        ("Max sum insured", f"${settings.INSURANCE_MAX_SUM_INSURED_USD:,.0f}"),
    ]
    return (
        answer,
        _facts(*facts),
        ["Is my data real or simulated?", "What's my quota?", "List my areas"],
        _links(("New area", "/app/areas/new"), ("Overview", "/app")),
    )


def _area_detail(db: Session, snapshot: Snapshot, area_id: int):
    analysis = (
        db.query(Analysis)
        .filter(Analysis.id == area_id, Analysis.user_id == snapshot.user.id)
        .first()
    )
    if analysis is None:
        return (
            f"I couldn't find area #{area_id} in your account. I only read your own areas, "
            "so I won't describe someone else's.",
            _facts(("Area", f"#{area_id} not found")),
            ["List my areas", "Give me an overview"],
            _links(("Overview", "/app")),
        )

    area = _area_snapshots(db, [analysis])[0]
    parts = [
        f"{area.label} (#{area.id}) is {area.status}.",
        f"It covers {area.latitude:.4f}, {area.longitude:.4f} within {area.radius_km:.2f} km.",
    ]
    if area.monitor_interval_minutes:
        parts.append(f"It is re-checked every {area.monitor_interval_minutes} minutes.")
    else:
        parts.append("Continuous monitoring is off for this area.")
    if area.latest_severity is None:
        parts.append("No findings have landed yet.")
    else:
        parts.append(
            f"Latest finding: severity {area.latest_severity:.2f}"
            + (
                f", confidence {area.latest_confidence:.2f}"
                if area.latest_confidence is not None
                else ""
            )
            + f", recorded {_when(area.latest_at)}."
        )
    parts.append(
        f"{area.unread_alerts} unread {_plural(area.unread_alerts, 'alert')}."
        if area.unread_alerts
        else "No unread alerts."
    )

    facts = [
        ("Status", area.status),
        ("Type", TYPE_LABELS.get(area.analysis_type, area.analysis_type)),
        ("Centre", f"{area.latitude:.4f}, {area.longitude:.4f}"),
        ("Radius", f"{area.radius_km:.2f} km"),
        ("Monitoring", f"every {area.monitor_interval_minutes} min" if area.monitor_interval_minutes else "off"),
        ("Unread alerts", str(area.unread_alerts)),
    ]
    if area.latest_severity is not None:
        facts.append(("Latest severity", f"{area.latest_severity:.2f}"))
    return (
        " ".join(parts),
        _facts(*facts),
        ["Show my unread alerts", "Give me an overview", "Is my data real or simulated?"],
        _links((f"Open {area.label}", f"/app/areas/{area.id}"), ("Operations", "/app/operations")),
    )


def _areas(db: Session, snapshot: Snapshot, text: str):
    type_key = _type_match(text)
    if type_key:
        label = TYPE_LABELS.get(type_key, type_key)
        count = snapshot.by_type.get(type_key, 0)
        if count == 0:
            return (
                f"You don't have any {label.lower()} areas yet.",
                _facts(("Matching areas", "0")),
                ["List my areas", "What can you do?"],
                _links(("New area", "/app/areas/new"), ("Overview", "/app")),
            )
        rows = (
            db.query(Analysis)
            .filter(Analysis.user_id == snapshot.user.id, Analysis.analysis_type == type_key)
            .order_by(Analysis.created_at.desc(), Analysis.id.desc())
            .limit(5)
            .all()
        )
        areas = _area_snapshots(db, rows)
        answer = (
            f"{count} {label.lower()} {_plural(count, 'area')}. Most recent:"
            "\n" + "\n".join(_area_line(area) for area in areas)
        )
        links = [("Overview", "/app")] + [
            (f"Open {area.label}", f"/app/areas/{area.id}") for area in areas[:3]
        ]
        return (
            answer,
            _facts(("Matching areas", str(count)), ("Type", label)),
            SUGGESTIONS_GENERAL,
            _links(*links),
        )

    if snapshot.total_areas == 0:
        return (
            "You don't have any areas yet. Create one with + New area and I'll track it here.",
            _facts(("Areas", "0")),
            ["What can you do?", "What's my quota?"],
            _links(("New area", "/app/areas/new")),
        )

    answer = (
        f"{snapshot.total_areas} {_plural(snapshot.total_areas, 'area')} "
        f"({_spread(snapshot.by_status)}). Most recent:"
        "\n" + "\n".join(_area_line(area) for area in snapshot.areas)
    )
    links = [("Overview", "/app")] + [
        (f"Open {area.label}", f"/app/areas/{area.id}") for area in snapshot.areas[:3]
    ]
    facts = [
        ("Areas", str(snapshot.total_areas)),
        ("Monitored", str(snapshot.monitored)),
        ("By type", _spread(snapshot.by_type)),
    ]
    return answer, _facts(*facts), SUGGESTIONS_GENERAL, _links(*links)


def _help():
    return (
        "I read your account live and answer in plain language. I can: summarise your areas, "
        "list unread alerts, check the flight fleet, explain whether findings are real or "
        "simulated, report today's analysis quota, describe a specific area by name or number, "
        "and explain parametric insurance checks. I only read — I can't launch, change or "
        "delete anything.",
        _facts(("Mode", "read-only"), ("Data", "your account, live")),
        SUGGESTIONS_GENERAL,
        _links(("Overview", "/app"), ("Settings", "/app/settings")),
    )


def _identity():
    return (
        "I'm FRIDAY, the AURORA console assistant. I'm a deterministic assistant built into "
        "this console — there's no language model behind me. Every figure I give you is read "
        "from your own rows in the same request, which is why I can't make up a finding, a "
        "flight or a payout.",
        _facts(("Identity", "FRIDAY (AURORA console)"), ("Answers from", "your live account data")),
        SUGGESTIONS_GENERAL,
        _links(("Overview", "/app")),
    )


def _greeting_reply(snapshot: Snapshot):
    if snapshot.unread_alerts:
        state = (
            f"You have {snapshot.unread_alerts} unread "
            f"{_plural(snapshot.unread_alerts, 'alert')} waiting."
        )
    else:
        state = "No unread alerts right now."
    return (
        f"Online. I'm FRIDAY — I read your areas, alerts, flights and quota live. {state}",
        _facts(
            ("Areas", str(snapshot.total_areas)),
            ("Unread alerts", str(snapshot.unread_alerts)),
        ),
        SUGGESTIONS_GENERAL,
        _links(("Overview", "/app")),
    )


def _thanks():
    return (
        "Anytime.",
        [],
        SUGGESTIONS_GENERAL,
        _links(("Overview", "/app")),
    )


def _fallback(text: str):
    action = _has(
        text,
        (
            "start",
            "run",
            "launch",
            "create",
            "delete",
            "remove",
            "stop",
            "cancel",
            "change",
            "update",
        ),
    )
    if action:
        return (
            "I can't start, change or delete anything — I'm read-only on purpose. Use + New "
            "area for a run, or the Operations page for the job pipeline.",
            _facts(("Mode", "read-only")),
            SUGGESTIONS_GENERAL,
            _links(("New area", "/app/areas/new"), ("Operations", "/app/operations")),
        )
    return (
        "I can't read that one. I answer from your areas, alerts, flights, quota and data "
        "provenance — ask for an overview, or pick one of the suggestions below.",
        _facts(("Scope", "areas, alerts, flights, quota, provenance")),
        SUGGESTIONS_GENERAL,
        _links(("Overview", "/app")),
    )


def answer_question(db: Session, user: User, message: str) -> AssistantReply:
    """Route one question to a grounded answer. Pure read path, no writes."""
    text = _normalize(message)
    snapshot = build_snapshot(db, user)
    area_id = _match_area_id(snapshot, text)
    intent = _route(text, area_id)

    if intent == "overview":
        answer, facts, suggestions, links = _overview(snapshot)
    elif intent == "alerts":
        answer, facts, suggestions, links = _alerts(snapshot)
    elif intent == "flights":
        answer, facts, suggestions, links = _flights(snapshot)
    elif intent == "provenance":
        answer, facts, suggestions, links = _provenance(snapshot)
    elif intent == "quota":
        answer, facts, suggestions, links = _quota(snapshot)
    elif intent == "verification":
        answer, facts, suggestions, links = _verification(snapshot)
    elif intent == "insurance":
        answer, facts, suggestions, links = _insurance(snapshot)
    elif intent == "area_detail" and area_id is not None:
        answer, facts, suggestions, links = _area_detail(db, snapshot, area_id)
    elif intent == "areas":
        answer, facts, suggestions, links = _areas(db, snapshot, text)
    elif intent == "help":
        answer, facts, suggestions, links = _help()
    elif intent == "identity":
        answer, facts, suggestions, links = _identity()
    elif intent == "greeting":
        answer, facts, suggestions, links = _greeting_reply(snapshot)
    elif intent == "thanks":
        answer, facts, suggestions, links = _thanks()
    else:
        intent = "fallback"
        answer, facts, suggestions, links = _fallback(text)

    return AssistantReply(
        intent=intent,
        answer=answer,
        facts=facts,
        suggestions=suggestions,
        links=links,
        generated_at=datetime.now(UTC),
    )
