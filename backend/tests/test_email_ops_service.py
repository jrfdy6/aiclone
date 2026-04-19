from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import EmailMessage, EmailThread
from app.services.email_ops_service import _classify_thread


def _sample_thread(*, subject: str, body_text: str, from_address: str, to_addresses: list[str], provider_labels: list[str] | None = None) -> EmailThread:
    now = datetime.now(timezone.utc)
    return EmailThread(
        id="thread-1",
        provider="gmail",
        provider_thread_id="thread-1",
        provider_labels=provider_labels or [],
        subject=subject,
        from_address=from_address,
        from_name=None,
        organization=None,
        to_addresses=to_addresses,
        messages=[
            EmailMessage(
                id="msg-1",
                direction="inbound",
                from_address=from_address,
                from_name=None,
                to_addresses=to_addresses,
                cc_addresses=[],
                subject=subject,
                body_text=body_text,
                received_at=now,
            )
        ],
        last_message_at=now,
        created_at=now,
        updated_at=now,
    )


class EmailOpsServiceTests(unittest.TestCase):
    def test_agc_requires_explicit_workspace_label(self) -> None:
        thread = _sample_thread(
            subject="Need help improving procurement workflow visibility",
            body_text="We want operational clarity and workflow modernization support for procurement operations.",
            from_address="operations@statecollege.edu",
            to_addresses=["neo512235@gmail.com"],
        )

        classified = _classify_thread(thread)

        self.assertEqual(classified.workspace_key, "shared_ops")
        self.assertEqual(classified.lane, "manual_review")
        self.assertIn("label_required:workspace/agc", classified.routing_reasons)

    def test_agc_routes_when_workspace_label_is_present(self) -> None:
        thread = _sample_thread(
            subject="Vendor onboarding package",
            body_text="Please review the reseller onboarding packet and next supplier steps.",
            from_address="partnerrelations@quantabio.com",
            to_addresses=["neo512235+agc-vendors@gmail.com"],
            provider_labels=["workspace/agc"],
        )

        classified = _classify_thread(thread)

        self.assertEqual(classified.workspace_key, "agc")
        self.assertEqual(classified.lane, "supplier_partner")
        self.assertIn("label:workspace/agc", classified.routing_reasons)


if __name__ == "__main__":
    unittest.main()
