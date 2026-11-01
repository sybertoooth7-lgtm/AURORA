"""Where a persisted analysis result's data actually came from.

The honesty invariant ("simulated data is always labelled") has to hold in
two places: the result payload itself and every roll-up built from it. The
helpers live here so the dashboard summary and the assistant answer the
same question with the same code instead of drifting apart.
"""

import json

from sqlalchemy import case, cast, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.logging_conf import get_logger
from app.models.analysis import Analysis, AnalysisResult

logger = get_logger(__name__)


def count_by_provenance(db: Session, user_id: int) -> dict[str, int]:
    """Count results per provenance bucket in the database.

    The dashboard polls this roll-up, and the previous shape pulled every
    result's metadata JSON into Python to count it. That is O(history) bytes
    per poll. Each supported dialect has JSON extraction plus a validity
    guard, so the same answer comes back as a grouped count; anything
    unexpected (an unsupported dialect, a JSON function missing from an old
    server) falls back to the Python walk rather than failing the dashboard.
    """
    try:
        if db.get_bind().dialect.name == "sqlite":
            valid = func.json_valid(AnalysisResult.metadata_json)
            provenance = case(
                (valid, func.json_extract(AnalysisResult.metadata_json, "$.provenance"))
            )
            simulated = case(
                (valid, func.json_type(AnalysisResult.metadata_json, "$.simulated"))
            )
        elif db.get_bind().dialect.name == "postgresql":
            # pg_input_is_valid keeps one malformed legacy row from aborting
            # the cast for every account on the instance.
            as_json = cast(AnalysisResult.metadata_json, JSONB)
            valid = func.pg_input_is_valid(AnalysisResult.metadata_json, "jsonb")
            # `->>` rather than jsonb_extract_path_text: the latter's path is
            # VARIADIC text[], which a scalar bind parameter cannot satisfy.
            provenance = case((valid, as_json["provenance"].astext))
            simulated = case((valid, as_json["simulated"].astext))
        else:
            return _count_in_python(db, user_id)

        bucket = case(
            (
                provenance.is_not(None) & (func.length(provenance) > 0),
                provenance,
            ),
            (simulated == "true", "simulated"),
            (simulated == "false", "real"),
            else_="unknown",
        )
        rows = (
            db.query(bucket.label("bucket"), func.count())
            .select_from(AnalysisResult)
            .join(Analysis, AnalysisResult.analysis_id == Analysis.id)
            .filter(Analysis.user_id == user_id)
            .group_by(bucket)
            .all()
        )
        return {str(bucket_value): int(count) for bucket_value, count in rows}
    except Exception:  # noqa: BLE001 - an optimisation must not break the roll-up
        db.rollback()
        logger.warning("provenance SQL roll-up unavailable; using Python walk", exc_info=True)
        return _count_in_python(db, user_id)


def _count_in_python(db: Session, user_id: int) -> dict[str, int]:
    """Fallback roll-up that streams the metadata column in bounded batches."""
    counts: dict[str, int] = {}
    rows = (
        db.query(AnalysisResult.metadata_json)
        .join(Analysis, AnalysisResult.analysis_id == Analysis.id)
        .filter(Analysis.user_id == user_id)
        .yield_per(1000)
    )
    for (payload,) in rows:
        key = provenance_of(payload)
        counts[key] = counts.get(key, 0) + 1
    return counts


def provenance_of(metadata_json: str | None) -> str:
    """Bucket a persisted result by where its data actually came from.

    Results written before provenance was tracked report ``unknown`` rather
    than being silently counted as real.
    """
    if not metadata_json:
        return "unknown"
    try:
        payload = json.loads(metadata_json)
    except (TypeError, ValueError):
        return "unknown"
    if not isinstance(payload, dict):
        return "unknown"
    if payload.get("provenance"):
        return str(payload["provenance"])
    if payload.get("simulated") is True:
        return "simulated"
    if payload.get("simulated") is False:
        return "real"
    return "unknown"
