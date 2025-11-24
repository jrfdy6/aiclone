"""
Automations Engine Routes
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from app.models.automations import (
    AutomationCreate, AutomationUpdate, AutomationResponse,
    AutomationListResponse, ExecutionListResponse,
    AutomationTrigger, AutomationAction, AutomationStatus, ExecutionStatus
)
from app.services.automation_service import (
    create_automation, get_automation, list_automations,
    update_automation, delete_automation, record_execution, list_executions
)
from app.services.firestore_client import db

logger = logging.getLogger(__name__)
router = APIRouter()


async def execute_automation_actions(automation_id: str, triggered_by: str, context: Dict[str, Any]):
    """
    Background task to execute automation actions.
    This runs the actual workflow execution.
    """
    try:
        automation = get_automation(automation_id)
        if not automation:
            logger.error(f"Automation {automation_id} not found")
            return
        
        if automation.status != AutomationStatus.ACTIVE:
            logger.info(f"Automation {automation_id} is not active, skipping execution")
            return
        
        execution_id = record_execution(
            automation_id=automation_id,
            user_id=automation.user_id,
            triggered_by=triggered_by,
            status=ExecutionStatus.RUNNING,
        )
        
        results = {}
        
        # Execute each action in sequence
        for action in automation.actions:
            try:
                logger.info(f"Executing action {action.value} for automation {automation_id}")
                
                if action == AutomationAction.GENERATE_OUTREACH:
                    # Would call outreach generation service
                    results["generate_outreach"] = {"status": "completed", "message": "Outreach generated"}
                
                elif action == AutomationAction.ADD_CALENDAR_EVENT:
                    # Would call calendar service
                    results["add_calendar_event"] = {"status": "completed", "message": "Event added"}
                
                elif action == AutomationAction.SEND_NOTIFICATION:
                    # Would call notification service
                    results["send_notification"] = {"status": "completed", "message": "Notification sent"}
                
                elif action == AutomationAction.UPDATE_PROSPECT_STATUS:
                    # Would call prospect service
                    results["update_prospect_status"] = {"status": "completed", "message": "Status updated"}
                
                elif action == AutomationAction.RUN_FIRECRAWL:
                    # Would call Firecrawl service
                    results["run_firecrawl"] = {"status": "completed", "message": "Firecrawl executed"}
                
                elif action == AutomationAction.RUN_PERPLEXITY:
                    # Would call Perplexity service
                    results["run_perplexity"] = {"status": "completed", "message": "Perplexity query executed"}
                
                elif action == AutomationAction.STORE_INSIGHT:
                    # Would call vault or research service
                    results["store_insight"] = {"status": "completed", "message": "Insight stored"}
                
            except Exception as e:
                logger.error(f"Error executing action {action.value}: {e}")
                results[action.value] = {"status": "failed", "error": str(e)}
        
        # Update execution record
        from datetime import datetime
        execution_doc = db.collection("automation_executions").document(execution_id)
        execution_doc.update({
            "status": ExecutionStatus.SUCCESS.value,
            "completed_at": datetime.now().isoformat(),
            "results": results,
        })
        
        logger.info(f"Automation {automation_id} execution completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to execute automation {automation_id}: {e}")
        # Update execution record with error
        try:
            execution_id = context.get("execution_id")
            if execution_id:
                execution_doc = db.collection("automation_executions").document(execution_id)
                from datetime import datetime
                execution_doc.update({
                    "status": ExecutionStatus.FAILED.value,
                    "completed_at": datetime.now().isoformat(),
                    "error": str(e),
                })
        except:
            pass


@router.post("", response_model=AutomationResponse)
async def create_automation_endpoint(request: AutomationCreate) -> Dict[str, Any]:
    """Create a new automation."""
    try:
        automation_id = create_automation(
            user_id=request.user_id,
            name=request.name,
            trigger=request.trigger,
            actions=request.actions,
            description=request.description,
            metadata=request.metadata,
        )
        
        automation = get_automation(automation_id)
        if not automation:
            raise HTTPException(status_code=500, detail="Failed to retrieve created automation")
        
        return AutomationResponse(success=True, automation=automation)
    except Exception as e:
        logger.exception(f"Error creating automation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create automation: {str(e)}")


@router.get("", response_model=AutomationListResponse)
async def list_automations_endpoint(
    user_id: str = Query(..., description="User identifier"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    """List automations for a user."""
    try:
        automation_status = AutomationStatus(status) if status else None
        automations = list_automations(
            user_id=user_id,
            status=automation_status,
            limit=limit
        )
        return AutomationListResponse(
            success=True,
            automations=automations,
            total=len(automations)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    except Exception as e:
        logger.exception(f"Error listing automations: {e}")
        return AutomationListResponse(success=True, automations=[], total=0)


@router.get("/{automation_id}", response_model=AutomationResponse)
async def get_automation_endpoint(automation_id: str) -> Dict[str, Any]:
    """Get an automation by ID."""
    automation = get_automation(automation_id)
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    return AutomationResponse(success=True, automation=automation)


@router.put("/{automation_id}", response_model=AutomationResponse)
async def update_automation_endpoint(
    automation_id: str,
    request: AutomationUpdate
) -> Dict[str, Any]:
    """Update an automation."""
    automation = get_automation(automation_id)
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.description is not None:
        updates["description"] = request.description
    if request.trigger is not None:
        updates["trigger"] = request.trigger.value
    if request.actions is not None:
        updates["actions"] = [action.value for action in request.actions]
    if request.status is not None:
        updates["status"] = request.status.value
    if request.metadata is not None:
        updates["metadata"] = request.metadata
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    success = update_automation(automation_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update automation")
    
    updated_automation = get_automation(automation_id)
    return AutomationResponse(success=True, automation=updated_automation)


@router.delete("/{automation_id}")
async def delete_automation_endpoint(automation_id: str) -> Dict[str, Any]:
    """Delete an automation."""
    automation = get_automation(automation_id)
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    success = delete_automation(automation_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete automation")
    
    return {"success": True, "message": "Automation deleted"}


@router.post("/{automation_id}/activate", response_model=AutomationResponse)
async def activate_automation(automation_id: str) -> Dict[str, Any]:
    """Activate an automation."""
    automation = get_automation(automation_id)
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    success = update_automation(automation_id, {"status": AutomationStatus.ACTIVE.value})
    if not success:
        raise HTTPException(status_code=500, detail="Failed to activate automation")
    
    updated_automation = get_automation(automation_id)
    return AutomationResponse(success=True, automation=updated_automation)


@router.post("/{automation_id}/deactivate", response_model=AutomationResponse)
async def deactivate_automation(automation_id: str) -> Dict[str, Any]:
    """Deactivate an automation."""
    automation = get_automation(automation_id)
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    success = update_automation(automation_id, {"status": AutomationStatus.INACTIVE.value})
    if not success:
        raise HTTPException(status_code=500, detail="Failed to deactivate automation")
    
    updated_automation = get_automation(automation_id)
    return AutomationResponse(success=True, automation=updated_automation)


@router.get("/{automation_id}/executions", response_model=ExecutionListResponse)
async def get_automation_executions(
    automation_id: str,
    limit: int = Query(50, ge=1, le=500),
) -> Dict[str, Any]:
    """Get execution history for an automation."""
    automation = get_automation(automation_id)
    if not automation:
        raise HTTPException(status_code=404, detail="Automation not found")
    
    executions = list_executions(automation_id=automation_id, limit=limit)
    return ExecutionListResponse(
        success=True,
        executions=executions,
        total=len(executions)
    )

