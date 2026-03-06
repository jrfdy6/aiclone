"""Automations Routes.

Provides visibility into all scheduled/triggered automations (cron jobs).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.models.automations import Automation
from app.services.automation_service import list_automations

router = APIRouter(tags=["Automations"])


@router.get("/", response_model=dict)
async def automations_index() -> dict:
    automations = list_automations()
    return {
        "success": True,
        "count": len(automations),
        "data": automations,
    }
