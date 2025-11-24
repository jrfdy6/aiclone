"""
System Log Service
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
from app.services.firestore_client import db
from app.models.system_logs import SystemLog, LogLevel, LogCategory

logger = logging.getLogger(__name__)


def create_log(
    user_id: str,
    level: LogLevel,
    category: LogCategory,
    message: str,
    details: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    related_id: Optional[str] = None,
    can_rerun: bool = False
) -> str:
    """Create a new log entry."""
    try:
        log_ref = db.collection("system_logs").document()
        log_id = log_ref.id
        
        log_data = {
            "user_id": user_id,
            "level": level.value,
            "category": category.value,
            "message": message,
            "details": details or "",
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
            "related_id": related_id,
            "can_rerun": can_rerun,
        }
        
        log_ref.set(log_data)
        logger.info(f"Created log entry {log_id}: {level.value} - {message}")
        return log_id
        
    except Exception as e:
        logger.error(f"Error creating log entry: {e}")
        raise


def get_log(log_id: str) -> Optional[SystemLog]:
    """Get a log entry by ID."""
    try:
        log_doc = db.collection("system_logs").document(log_id).get()
        
        if not log_doc.exists:
            return None
        
        data = log_doc.to_dict()
        return SystemLog(
            id=log_id,
            user_id=data.get("user_id", ""),
            level=LogLevel(data.get("level", "info")),
            category=LogCategory(data.get("category", "system")),
            message=data.get("message", ""),
            details=data.get("details"),
            timestamp=data.get("timestamp", ""),
            metadata=data.get("metadata", {}),
            related_id=data.get("related_id"),
            can_rerun=data.get("can_rerun", False),
        )
    except Exception as e:
        logger.error(f"Error getting log entry {log_id}: {e}")
        return None


def list_logs(
    user_id: str,
    level: Optional[LogLevel] = None,
    category: Optional[LogCategory] = None,
    limit: int = 100
) -> List[SystemLog]:
    """List log entries for a user."""
    try:
        query = db.collection("system_logs").where("user_id", "==", user_id)
        
        if level:
            query = query.where("level", "==", level.value)
        
        if category:
            query = query.where("category", "==", category.value)
        
        # Try to order by timestamp
        try:
            docs = query.order_by("timestamp", direction="DESCENDING").limit(limit).stream()
        except Exception:
            docs = query.limit(limit).stream()
        
        logs = []
        for doc in docs:
            try:
                data = doc.to_dict()
                logs.append(SystemLog(
                    id=doc.id,
                    user_id=data.get("user_id", ""),
                    level=LogLevel(data.get("level", "info")),
                    category=LogCategory(data.get("category", "system")),
                    message=data.get("message", ""),
                    details=data.get("details"),
                    timestamp=data.get("timestamp", ""),
                    metadata=data.get("metadata", {}),
                    related_id=data.get("related_id"),
                    can_rerun=data.get("can_rerun", False),
                ))
            except Exception as e:
                logger.warning(f"Error processing log document {doc.id}: {e}")
                continue
        
        # Sort in Python if order_by didn't work
        if logs:
            try:
                logs.sort(key=lambda x: x.timestamp, reverse=True)
            except:
                pass
        
        return logs
    except Exception as e:
        logger.error(f"Error listing logs: {e}")
        return []


def get_log_stats(user_id: str) -> Dict[str, Any]:
    """Get log statistics for a user."""
    try:
        logs = list_logs(user_id, limit=1000)
        
        stats = {
            "total_logs": len(logs),
            "by_level": defaultdict(int),
            "by_category": defaultdict(int),
            "recent_errors": 0,
        }
        
        # Count by level and category
        for log in logs:
            stats["by_level"][log.level.value] += 1
            stats["by_category"][log.category.value] += 1
            
            # Count recent errors (last 24 hours)
            try:
                log_time = datetime.fromisoformat(log.timestamp.replace("Z", "+00:00"))
                if log.level == LogLevel.ERROR and (datetime.now(log_time.tzinfo) - log_time) < timedelta(days=1):
                    stats["recent_errors"] += 1
            except:
                pass
        
        return stats
    except Exception as e:
        logger.error(f"Error getting log stats: {e}")
        return {
            "total_logs": 0,
            "by_level": {},
            "by_category": {},
            "recent_errors": 0,
        }

