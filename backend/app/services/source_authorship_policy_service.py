from __future__ import annotations

import json
from typing import Any, Mapping


OWNER_AUTHORSHIP_ATTESTATION_KEY = "owner_authorship_attested"
OWNER_REQUESTED_ROUTE_KEY = "owner_requested_route"
AUTHORSHIP_POLICY_VERSION = "source_authorship_policy/v1"


def metadata_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def owner_authorship_attested(metadata: Any) -> bool:
    """Return true only for an explicit boolean owner-authorship attestation."""

    return metadata_object(metadata).get(OWNER_AUTHORSHIP_ATTESTATION_KEY) is True


def validate_rights_authorship(*, rights_state: str, metadata: Any) -> None:
    """Keep route authority distinct from factual authorship.

    An owner asking the system to ingest an item establishes the route by which
    it arrived. It does not establish that the owner wrote, said, or lived the
    source material. ``owner_controlled`` is therefore closed unless the event
    carries an explicit boolean attestation.
    """

    if rights_state == "owner_controlled" and not owner_authorship_attested(metadata):
        raise ValueError(
            "owner_controlled sources require an explicit owner_authorship_attested=true"
        )


def conservative_combined_rights(
    *,
    left_state: str,
    left_metadata: Any,
    right_state: str,
    right_metadata: Any,
) -> str:
    """Combine duplicate-source rights without silently promoting authorship.

    Restrictive states remain sticky. An unattested legacy ``owner_controlled``
    value is treated as attribution-required ``permitted``. If one route calls
    a duplicate external/permitted and another calls it owner-authored, the
    conservative result remains permitted; authorship changes require a
    separately audited repair/review rather than an intake replay.
    """

    def normalized(state: str, metadata: Any) -> str:
        if state == "owner_controlled" and not owner_authorship_attested(metadata):
            return "permitted"
        return state

    states = {
        normalized(left_state, left_metadata),
        normalized(right_state, right_metadata),
    }
    if "blocked" in states:
        return "blocked"
    if "restricted" in states:
        return "restricted"
    if "permitted" in states:
        return "permitted"
    if "owner_controlled" in states:
        return "owner_controlled"
    return "unknown"
