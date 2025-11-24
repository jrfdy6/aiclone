"""
Research Task Service - Manages research task execution and status
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from app.services.firestore_client import db
from app.models.research_tasks import (
    ResearchTask, ResearchTaskStatus, ResearchEngine, SourceType, TaskPriority
)

logger = logging.getLogger(__name__)


def create_research_task(
    user_id: str,
    title: str,
    input_source: str,
    source_type: SourceType,
    research_engine: ResearchEngine,
    priority: TaskPriority = TaskPriority.MEDIUM
) -> str:
    """
    Create a new research task in Firestore.
    
    Returns the task ID.
    """
    try:
        task_ref = db.collection("research_tasks").document()
        task_id = task_ref.id
        
        task_data = {
            "user_id": user_id,
            "title": title,
            "input_source": input_source,
            "source_type": source_type.value,
            "research_engine": research_engine.value,
            "status": ResearchTaskStatus.QUEUED.value,
            "priority": priority.value,
            "created_at": datetime.now().isoformat(),
            "outputs_available": False,
        }
        
        task_ref.set(task_data)
        logger.info(f"Created research task {task_id} for user {user_id}")
        return task_id
        
    except Exception as e:
        logger.error(f"Error creating research task: {e}")
        raise


def get_research_task(task_id: str) -> Optional[ResearchTask]:
    """Get a research task by ID."""
    try:
        task_doc = db.collection("research_tasks").document(task_id).get()
        
        if not task_doc.exists:
            return None
        
        data = task_doc.to_dict()
        return ResearchTask(
            id=task_id,
            user_id=data.get("user_id", ""),
            title=data.get("title", ""),
            input_source=data.get("input_source", ""),
            source_type=SourceType(data.get("source_type", "keywords")),
            research_engine=ResearchEngine(data.get("research_engine", "perplexity")),
            status=ResearchTaskStatus(data.get("status", "queued")),
            priority=TaskPriority(data.get("priority", "medium")),
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            outputs_available=data.get("outputs_available", False),
            result_id=data.get("result_id"),
        )
    except Exception as e:
        logger.error(f"Error getting research task {task_id}: {e}")
        return None


def list_research_tasks(
    user_id: str,
    status: Optional[str] = None,
    limit: int = 100
) -> List[ResearchTask]:
    """List research tasks for a user."""
    try:
        query = db.collection("research_tasks").where("user_id", "==", user_id)
        
        if status:
            query = query.where("status", "==", status)
        
        # Order by created_at descending
        docs = query.order_by("created_at", direction="DESCENDING").limit(limit).stream()
        
        tasks = []
        for doc in docs:
            try:
                data = doc.to_dict()
                tasks.append(ResearchTask(
                    id=doc.id,
                    user_id=data.get("user_id", ""),
                    title=data.get("title", ""),
                    input_source=data.get("input_source", ""),
                    source_type=SourceType(data.get("source_type", "keywords")),
                    research_engine=ResearchEngine(data.get("research_engine", "perplexity")),
                    status=ResearchTaskStatus(data.get("status", "queued")),
                    priority=TaskPriority(data.get("priority", "medium")),
                    created_at=data.get("created_at", ""),
                    started_at=data.get("started_at"),
                    completed_at=data.get("completed_at"),
                    error=data.get("error"),
                    outputs_available=data.get("outputs_available", False),
                    result_id=data.get("result_id"),
                ))
            except Exception as e:
                logger.warning(f"Error processing task document {doc.id}: {e}")
                continue
        
        return tasks
    except Exception as e:
        logger.error(f"Error listing research tasks: {e}")
        # Fallback to simpler query if ordering fails
        try:
            query = db.collection("research_tasks").where("user_id", "==", user_id)
            if status:
                query = query.where("status", "==", status)
            docs = query.limit(limit).stream()
            tasks = []
            for doc in docs:
                try:
                    data = doc.to_dict()
                    tasks.append(ResearchTask(
                        id=doc.id,
                        user_id=data.get("user_id", ""),
                        title=data.get("title", ""),
                        input_source=data.get("input_source", ""),
                        source_type=SourceType(data.get("source_type", "keywords")),
                        research_engine=ResearchEngine(data.get("research_engine", "perplexity")),
                        status=ResearchTaskStatus(data.get("status", "queued")),
                        priority=TaskPriority(data.get("priority", "medium")),
                        created_at=data.get("created_at", ""),
                        started_at=data.get("started_at"),
                        completed_at=data.get("completed_at"),
                        error=data.get("error"),
                        outputs_available=data.get("outputs_available", False),
                        result_id=data.get("result_id"),
                    ))
                except:
                    continue
            # Sort in Python
            tasks.sort(key=lambda x: x.created_at, reverse=True)
            return tasks
        except:
            return []


def update_task_status(
    task_id: str,
    status: ResearchTaskStatus,
    error: Optional[str] = None,
    result_id: Optional[str] = None
) -> bool:
    """Update task status."""
    try:
        task_ref = db.collection("research_tasks").document(task_id)
        updates: Dict[str, Any] = {
            "status": status.value,
        }
        
        if status == ResearchTaskStatus.RUNNING:
            updates["started_at"] = datetime.now().isoformat()
        elif status == ResearchTaskStatus.DONE:
            updates["completed_at"] = datetime.now().isoformat()
            updates["outputs_available"] = True
            if result_id:
                updates["result_id"] = result_id
        elif status == ResearchTaskStatus.FAILED:
            updates["completed_at"] = datetime.now().isoformat()
            if error:
                updates["error"] = error
        
        task_ref.update(updates)
        return True
    except Exception as e:
        logger.error(f"Error updating task status: {e}")
        return False

