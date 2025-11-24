"""
Webhook Routes
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query
from app.models.webhooks import (
    Webhook, WebhookCreate, WebhookUpdate, WebhookResponse,
    WebhookListResponse
)
from app.services.webhook_service import (
    create_webhook, get_webhook, list_webhooks,
    update_webhook, delete_webhook
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=WebhookResponse)
async def create_new_webhook(request: WebhookCreate) -> Dict[str, Any]:
    """Create a new webhook"""
    try:
        webhook = create_webhook(request.user_id, request)
        return WebhookResponse(success=True, webhook=webhook)
    except Exception as e:
        logger.exception(f"Error creating webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create webhook: {str(e)}")


@router.get("", response_model=WebhookListResponse)
async def list_all_webhooks(user_id: str = Query(..., description="User identifier")) -> Dict[str, Any]:
    """List all webhooks for a user"""
    try:
        webhooks = list_webhooks(user_id)
        return WebhookListResponse(success=True, webhooks=webhooks, total=len(webhooks))
    except Exception as e:
        logger.exception(f"Error listing webhooks: {e}")
        return WebhookListResponse(success=True, webhooks=[], total=0)


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook_details(
    webhook_id: str,
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, Any]:
    """Get a webhook by ID"""
    webhook = get_webhook(user_id, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return WebhookResponse(success=True, webhook=webhook)


@router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_existing_webhook(
    webhook_id: str,
    request: WebhookUpdate,
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, Any]:
    """Update a webhook"""
    webhook = update_webhook(user_id, webhook_id, request)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return WebhookResponse(success=True, webhook=webhook)


@router.delete("/{webhook_id}", response_model=Dict[str, bool])
async def delete_existing_webhook(
    webhook_id: str,
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, bool]:
    """Delete a webhook"""
    success = delete_webhook(user_id, webhook_id)
    if not success:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"success": True}

