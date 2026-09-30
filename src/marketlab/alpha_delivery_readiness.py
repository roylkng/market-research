from __future__ import annotations

from typing import Any

from marketlab.alpha import AlphaContractError

REQUIRED_PRIOR_DELIVERY_SESSIONS = 20


def delivery_source_warmup_readiness(
    prior_delivery_sessions: list[dict[str, Any]],
    *,
    required_prior_sessions: int = REQUIRED_PRIOR_DELIVERY_SESSIONS,
) -> dict[str, Any]:
    """Classify source-level readiness for prospective delivery features.

    This is a preflight only. READY means the source-level 20-session history is
    structurally capable of producing 21-session delivery features once the
    current session is added. Stock-level identity/missingness filters still run
    later under the frozen feature contract.
    """

    if (
        isinstance(required_prior_sessions, bool)
        or not isinstance(required_prior_sessions, int)
        or required_prior_sessions < 1
    ):
        raise AlphaContractError(
            "delivery warmup required_prior_sessions must be a positive integer"
        )
    if len(prior_delivery_sessions) != required_prior_sessions:
        raise AlphaContractError(
            "delivery warmup preflight requires the exact frozen prior-session window"
        )

    dates = [str(row.get("session_date") or "") for row in prior_delivery_sessions]
    if any(not value for value in dates):
        raise AlphaContractError("delivery warmup session_date is required")
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise AlphaContractError(
            "delivery warmup sessions must be unique and chronological"
        )

    blocking = []
    statuses = []
    for row in prior_delivery_sessions:
        quality = row.get("source_quality")
        status = (
            str(quality.get("status") or "")
            if isinstance(quality, dict)
            else "MISSING_SOURCE_QUALITY"
        )
        statuses.append(status)
        if status != "READY":
            blocking.append(
                {
                    "session_date": str(row["session_date"]),
                    "status": status,
                    "raw_sha256": row.get("raw_sha256"),
                }
            )

    consecutive_clean = 0
    for status in reversed(statuses):
        if status != "READY":
            break
        consecutive_clean += 1

    additional_needed = max(
        0,
        required_prior_sessions - consecutive_clean,
    )
    state = (
        "READY"
        if not blocking and consecutive_clean == required_prior_sessions
        else "WARMUP_BLOCKED"
    )

    return {
        "state": state,
        "required_prior_sessions": required_prior_sessions,
        "prior_session_count": len(prior_delivery_sessions),
        "blocking_session_count": len(blocking),
        "blocking_sessions": blocking,
        "consecutive_clean_prior_sessions": consecutive_clean,
        "additional_clean_prior_sessions_needed": additional_needed,
        "first_prior_session": dates[0],
        "last_prior_session": dates[-1],
        "feature_eligibility_changed": False,
        "live_capital_allowed": False,
    }
