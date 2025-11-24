"""
Automation Service - Manages automations and execution
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.services.firestore_client import db
from app.models.automations import (
    Automation, AutomationTrigger, AutomationAction,
    AutomationStatus, ExecutionStatus, ExecutionRecord
)

logger = logging.getLogger(__name__)


def create_automation(
    user_id: str,
    name: str,
    trigger: AutomationTrigger,
    actions: List[AutomationAction],
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Create a new automation."""
    try:
        automation_ref = db.collection("automations").document()
        automation_id = automation_ref.id
        
        now = datetime.now().isoformat()
        automation_data = {
            "user_id": user_id,
            "name": name,
            "description": description or "",
            "trigger": trigger.value,
            "actions": [action.value for action in actions],
            "status": AutomationStatus.INACTIVE.value,
            "created_at": now,
            "updated_at": now,
            "execution_count": 0,
            "last_executed_at": None,
            "metadata": metadata or {},
        }
        
        automation_ref.set(automation_data)
        logger.info(f"Created automation {automation_id} for user {user_id}")
        return automation_id
        
    except Exception as e:
        logger.error(f"Error creating automation: {e}")
        raise


def get_automation(automation_id: str) -> Optional[Automation]:
    """Get an automation by ID."""
    try:
        automation_doc = db.collection("automations").document(automation_id).get()
        
        if not automation_doc.exists:
            return None
        
        data = automation_doc.to_dict()
        return Automation(
            id=automation_id,
            user_id=data.get("user_id", ""),
            name=data.get("name", ""),
            description=data.get("description"),
            trigger=AutomationTrigger(data.get("trigger", "new_prospect_added")),
            actions=[AutomationAction(action) for action in data.get("actions", [])],
            status=AutomationStatus(data.get("status", "inactive")),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            execution_count=data.get("execution_count", 0),
            last_executed_at=data.get("last_executed_at"),
            metadata=data.get("metadata", {}),
        )
    except Exception as e:
        logger.error(f"Error getting automation {automation_id}: {e}")
        return None


def list_automations(
    user_id: str,
    status: Optional[AutomationStatus] = None,
    limit: int = 100
) -> List[Automation]:
    """List automations for a user."""
    try:
        query = db.collection("automations").where("user_id", "==", user_id)
        
        if status:
            query = query.where("status", "==", status.value)
        
        # Try to order by updated_at
        try:
            docs = query.order_by("updated_at", direction="DESCENDING").limit(limit).stream()
        except Exception:
            docs = query.limit(limit).stream()
        
        automations = []
        for doc in docs:
            try:
                data = doc.to_dict()
                automations.append(Automation(
                    id=doc.id,
                    user_id=data.get("user_id", ""),
                    name=data.get("name", ""),
                    description=data.get("description"),
                    trigger=AutomationTrigger(data.get("trigger", "new_prospect_added")),
                    actions=[AutomationAction(action) for action in data.get("actions", [])],
                    status=AutomationStatus(data.get("status", "inactive")),
                    created_at=data.get("created_at", ""),
                    updated_at=data.get("updated_at", ""),
                    execution_count=data.get("execution_count", 0),
                    last_executed_at=data.get("last_executed_at"),
                    metadata=data.get("metadata", {}),
                ))
            except Exception as e:
                logger.warning(f"Error processing automation document {doc.id}: {e}")
                continue
        
        # Sort in Python if order_by didn't work
        if automations:
            try:
                automations.sort(key=lambda x: x.updated_at, reverse=True)
            except:
                pass
        
        return automations
    except Exception as e:
        logger.error(f"Error listing automations: {e}")
        return []


def update_automation(automation_id: str, updates: Dict[str, Any]) -> bool:
    """Update an automation."""
    try:
        automation_ref = db.collection("automations").document(automation_id)
        updates["updated_at"] = datetime.now().isoformat()
        
        # Convert enums to values if needed
        if "trigger" in updates and isinstance(updates["trigger"], AutomationTrigger):
            updates["trigger"] = updates["trigger"].value
        if "actions" in updates and updates["actions"]:
            updates["actions"] = [action.value if isinstance(action, AutomationAction) else action for action in updates["actions"]]
        if "status" in updates and isinstance(updates["status"], AutomationStatus):
            updates["status"] = updates["status"].value
        
        automation_ref.update(updates)
        return True
    except Exception as e:
        logger.error(f"Error updating automation: {e}")
        return False


def delete_automation(automation_id: str) -> bool:
    """Delete an automation."""
    try:
        db.collection("automations").document(automation_id).delete()
        return True
    except Exception as e:
        logger.error(f"Error deleting automation: {e}")
        return False


def record_execution(
    automation_id: str,
    user_id: str,
    triggered_by: str,
    status: ExecutionStatus,
    error: Optional[str] = None,
    results: Optional[Dict[str, Any]] = None
) -> str:
    """Record an automation execution."""
    try:
        execution_ref = db.collection("automation_executions").document()
        execution_id = execution_ref.id
        
        now = datetime.now().isoformat()
        execution_data = {
            "automation_id": automation_id,
            "user_id": user_id,
            "status": status.value,
            "triggered_by": triggered_by,
            "started_at": now,
            "completed_at": now if status in [ExecutionStatus.SUCCESS, ExecutionStatus.FAILED] else None,
            "error": error,
            "results": results or {},
        }
        
        execution_ref.set(execution_data)
        
        # Update automation execution count
        automation = get_automation(automation_id)
        if automation:
            update_automation(automation_id, {
                "execution_count": automation.execution_count + 1,
                "last_executed_at": now,
            })
        
        return execution_id
    except Exception as e:
        logger.error(f"Error recording execution: {e}")
        raise


def list_executions(
    automation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 100
) -> List[ExecutionRecord]:
    """List automation executions."""
    try:
        query = db.collection("automation_executions")
        
        if automation_id:
            query = query.where("automation_id", "==", automation_id)
        
        if user_id:
            query = query.where("user_id", "==", user_id)
        
        # Try to order by started_at
        try:
            docs = query.order_by("started_at", direction="DESCENDING").limit(limit).stream()
        except Exception:
            docs = query.limit(limit).stream()
        
        executions = []
        for doc in docs:
            try:
                data = doc.to_dict()
                executions.append(ExecutionRecord(
                    id=doc.id,
                    automation_id=data.get("automation_id", ""),
                    user_id=data.get("user_id", ""),
                    status=ExecutionStatus(data.get("status", "pending")),
                    triggered_by=data.get("triggered_by", ""),
                    started_at=data.get("started_at", ""),
                    completed_at=data.get("completed_at"),
                    error=data.get("error"),
                    results=data.get("results", {}),
                ))
            except Exception as e:
                logger.warning(f"Error processing execution document {doc.id}: {e}")
                continue
        
        # Sort in Python if order_by didn't work
        if executions:
            try:
                executions.sort(key=lambda x: x.started_at, reverse=True)
            except:
                pass
        
        return executions
    except Exception as e:
        logger.error(f"Error listing executions: {e}")
        return []

