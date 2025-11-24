"""
System Logs Routes
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from app.models.system_logs import (
    LogCreate, LogResponse, LogListResponse, LogStatsResponse,
    LogLevel, LogCategory
)
from app.services.system_log_service import create_log, get_log, list_logs, get_log_stats

logger = logging.getLogger(__name__)
router = APIRouter()


async def rerun_task(related_id: str, task_type: str):
    """Background task to re-run a failed task."""
    try:
        logger.info(f"Re-running {task_type} task: {related_id}")
        
        # This would trigger the appropriate task execution
        # For now, just log that it was attempted
        if task_type == "research_task":
            # Would call research task execution
            pass
        elif task_type == "automation":
            # Would call automation execution
            pass
        # etc.
        
    except Exception as e:
        logger.error(f"Error re-running task: {e}")


@router.post("", response_model=LogResponse)
async def create_log_endpoint(request: LogCreate) -> Dict[str, Any]:
    """Create a new log entry."""
    try:
        log_id = create_log(
            user_id=request.user_id,
            level=request.level,
            category=request.category,
            message=request.message,
            details=request.details,
            metadata=request.metadata,
            related_id=request.related_id,
            can_rerun=request.can_rerun,
        )
        
        log_entry = get_log(log_id)
        if not log_entry:
            raise HTTPException(status_code=500, detail="Failed to retrieve created log")
        
        return LogResponse(success=True, log=log_entry)
    except Exception as e:
        logger.exception(f"Error creating log: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create log: {str(e)}")


@router.get("", response_model=LogListResponse)
async def list_logs_endpoint(
    user_id: str = Query(..., description="User identifier"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    """List log entries for a user."""
    try:
        log_level = LogLevel(level) if level else None
        log_category = LogCategory(category) if category else None
        
        logs = list_logs(
            user_id=user_id,
            level=log_level,
            category=log_category,
            limit=limit
        )
        return LogListResponse(
            success=True,
            logs=logs,
            total=len(logs)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid filter value: {str(e)}")
    except Exception as e:
        logger.exception(f"Error listing logs: {e}")
        return LogListResponse(success=True, logs=[], total=0)


@router.get("/{log_id}", response_model=LogResponse)
async def get_log_endpoint(log_id: str) -> Dict[str, Any]:
    """Get a log entry by ID."""
    log_entry = get_log(log_id)
    if not log_entry:
        raise HTTPException(status_code=404, detail="Log entry not found")
    return LogResponse(success=True, log=log_entry)


@router.post("/{log_id}/rerun")
async def rerun_log_task(
    log_id: str,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Re-run a failed task associated with a log entry."""
    log_entry = get_log(log_id)
    if not log_entry:
        raise HTTPException(status_code=404, detail="Log entry not found")
    
    if not log_entry.can_rerun:
        raise HTTPException(status_code=400, detail="This log entry cannot be re-run")
    
    if not log_entry.related_id:
        raise HTTPException(status_code=400, detail="Log entry has no related task to re-run")
    
    # Determine task type from category
    task_type = log_entry.category.value  # Use category as task type hint
    
    # Start background re-run
    background_tasks.add_task(rerun_task, log_entry.related_id, task_type)
    
    return {
        "success": True,
        "message": f"Re-run initiated for {task_type} task",
        "related_id": log_entry.related_id
    }


@router.get("/stats/summary", response_model=LogStatsResponse)
async def get_log_stats_endpoint(
    user_id: str = Query(..., description="User identifier")
) -> Dict[str, Any]:
    """Get log statistics for a user."""
    try:
        stats = get_log_stats(user_id)
        return LogStatsResponse(
            success=True,
            total_logs=stats.get("total_logs", 0),
            by_level=dict(stats.get("by_level", {})),
            by_category=dict(stats.get("by_category", {})),
            recent_errors=stats.get("recent_errors", 0),
        )
    except Exception as e:
        logger.exception(f"Error getting log stats: {e}")
        return LogStatsResponse(
            success=True,
            total_logs=0,
            by_level={},
            by_category={},
            recent_errors=0,
        )

