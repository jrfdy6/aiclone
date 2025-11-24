"""
Webhook Service
"""
import logging
import httpx
import hmac
import hashlib
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.services.firestore_client import db
from app.models.webhooks import Webhook, WebhookCreate, WebhookUpdate, WebhookEventType, WebhookStatus

logger = logging.getLogger(__name__)


def create_webhook(user_id: str, webhook_data: WebhookCreate) -> Webhook:
    """Create a new webhook"""
    webhook_id = db.collection("users").document(user_id).collection("webhooks").document().id
    
    webhook = Webhook(
        id=webhook_id,
        user_id=user_id,
        url=str(webhook_data.url),
        event_types=webhook_data.event_types,
        secret=webhook_data.secret,
        status=WebhookStatus.ACTIVE,
        created_at=datetime.now(),
        failure_count=0
    )
    
    db.collection("users").document(user_id).collection("webhooks").document(webhook_id).set(
        webhook.model_dump(mode='json', exclude_none=True)
    )
    
    logger.info(f"Created webhook {webhook_id} for user {user_id}")
    return webhook


def get_webhook(user_id: str, webhook_id: str) -> Optional[Webhook]:
    """Get a webhook by ID"""
    doc = db.collection("users").document(user_id).collection("webhooks").document(webhook_id).get()
    if not doc.exists:
        return None
    
    data = doc.to_dict()
    return Webhook(**data)


def list_webhooks(user_id: str) -> List[Webhook]:
    """List all webhooks for a user"""
    docs = db.collection("users").document(user_id).collection("webhooks").stream()
    return [Webhook(**doc.to_dict()) for doc in docs]


def update_webhook(user_id: str, webhook_id: str, update_data: WebhookUpdate) -> Optional[Webhook]:
    """Update a webhook"""
    doc_ref = db.collection("users").document(user_id).collection("webhooks").document(webhook_id)
    update_dict = update_data.model_dump(exclude_unset=True)
    
    if update_dict:
        update_dict["updated_at"] = datetime.now()
        doc_ref.update(update_dict)
    
    return get_webhook(user_id, webhook_id)


def delete_webhook(user_id: str, webhook_id: str) -> bool:
    """Delete a webhook"""
    doc_ref = db.collection("users").document(user_id).collection("webhooks").document(webhook_id)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.delete()
        return True
    return False


async def trigger_webhook(webhook: Webhook, event_type: WebhookEventType, payload: Dict[str, Any]):
    """Trigger a webhook delivery"""
    if webhook.status != WebhookStatus.ACTIVE:
        return
    
    if event_type not in webhook.event_types:
        return
    
    # Prepare payload
    webhook_payload = {
        "event_type": event_type.value,
        "timestamp": datetime.now().isoformat(),
        "data": payload
    }
    
    # Generate signature if secret is provided
    headers = {"Content-Type": "application/json"}
    if webhook.secret:
        signature = hmac.new(
            webhook.secret.encode(),
            json.dumps(webhook_payload).encode(),
            hashlib.sha256
        ).hexdigest()
        headers["X-Webhook-Signature"] = signature
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook.url, json=webhook_payload, headers=headers)
            
            # Update webhook stats
            doc_ref = db.collection("users").document(webhook.user_id).collection("webhooks").document(webhook.id)
            doc_ref.update({
                "last_triggered": datetime.now(),
                "failure_count": 0 if response.status_code < 400 else webhook.failure_count + 1
            })
            
            if response.status_code >= 400:
                logger.warning(f"Webhook {webhook.id} delivery failed: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Error triggering webhook {webhook.id}: {e}")
        # Increment failure count
        doc_ref = db.collection("users").document(webhook.user_id).collection("webhooks").document(webhook.id)
        current_failures = webhook.failure_count + 1
        doc_ref.update({"failure_count": current_failures})
        
        # Deactivate if too many failures
        if current_failures >= 5:
            doc_ref.update({"status": WebhookStatus.FAILED.value})


async def trigger_webhooks_for_event(user_id: str, event_type: WebhookEventType, payload: Dict[str, Any]):
    """Trigger all active webhooks for an event"""
    webhooks = list_webhooks(user_id)
    for webhook in webhooks:
        if webhook.status == WebhookStatus.ACTIVE:
            await trigger_webhook(webhook, event_type, payload)

