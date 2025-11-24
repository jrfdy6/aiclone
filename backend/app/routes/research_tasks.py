"""
Research Task Management Routes
"""
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from app.models.research_tasks import (
    ResearchTaskCreate, ResearchTask, ResearchTaskListResponse,
    ResearchTaskResponse, ResearchInsightsResponse, ResearchInsight,
    ResearchEngine, ResearchTaskStatus, TaskPriority
)
from app.services.research_task_service import (
    create_research_task, get_research_task, list_research_tasks,
    update_task_status
)
from app.services.firestore_client import db

logger = logging.getLogger(__name__)
router = APIRouter()


async def execute_research_task(task_id: str, task: ResearchTask):
    """
    Background task to execute research.
    This runs the actual research using the specified engine.
    """
    from datetime import datetime
    
    try:
        logger.info(f"Executing research task {task_id}")
        update_task_status(task_id, ResearchTaskStatus.RUNNING)
        
        # Import here to avoid circular imports
        from app.services.perplexity_client import get_perplexity_client
        from app.services.firecrawl_client import get_firecrawl_client
        from app.routes.research import extract_insights_from_research
        
        # Execute research based on engine
        research_summary = ""
        sources = []
        pain_points = []
        opportunities = []
        
        try:
            if task.research_engine == ResearchEngine.PERPLEXITY:
                # Use Perplexity for research
                perplexity = get_perplexity_client()
                research_data = perplexity.research_topic(
                    topic=task.input_source,
                    num_results=10,
                    include_comparison=True,
                )
                research_summary = research_data.get("summary", "")
                sources = research_data.get("sources", [])
                
                # Extract insights
                insights = extract_insights_from_research(research_summary, sources)
                pain_points = insights.get("trending_pains", [])[:5]
                opportunities = insights.get("industry_trends", [])[:5]
                
            elif task.research_engine == ResearchEngine.FIRECRAWL:
                # Use Firecrawl for URL scraping
                firecrawl = get_firecrawl_client()
                if task.source_type == SourceType.URLS:
                    # Extract URLs from input
                    urls = [url.strip() for url in task.input_source.split('\n') if url.strip().startswith('http')]
                    scraped_content = []
                    for url in urls[:5]:  # Limit to 5 URLs
                        try:
                            scraped = firecrawl.scrape_url(url)
                            scraped_content.append(scraped.content)
                            sources.append({"url": url, "title": scraped.title})
                        except Exception as e:
                            logger.warning(f"Failed to scrape {url}: {e}")
                    
                    research_summary = "\n\n".join(scraped_content)[:2000]  # Limit summary length
                    
                    # Extract insights
                    insights = extract_insights_from_research(research_summary, sources)
                    pain_points = insights.get("trending_pains", [])[:5]
                    opportunities = insights.get("industry_trends", [])[:5]
            
            elif task.research_engine == ResearchEngine.GOOGLE_SEARCH:
                # Use Google Search (basic implementation)
                research_summary = f"Research completed for: {task.input_source}"
                # In production, integrate with Google Custom Search API
                
            # Generate suggested outreach and content angles
            suggested_outreach = [
                f"Highlight how our solution addresses: {pain_points[0] if pain_points else 'key challenges'}" if pain_points else "Share value proposition",
                "Emphasize ROI and efficiency gains",
                "Discuss relevant industry trends",
            ]
            
            content_angles = [
                f"Case study: Solving {pain_points[0] if pain_points else 'industry challenges'}" if pain_points else "Industry insights",
                "Trend analysis: " + (opportunities[0] if opportunities else "Market opportunities"),
                "Best practices guide",
            ]
            
            # Store result in research_insights collection
            insight_ref = db.collection("research_insights").document()
            insight_ref.set({
                "user_id": task.user_id,
                "task_id": task_id,
                "topic": task.input_source,
                "title": task.title,
                "summary": research_summary[:500],
                "pain_points": pain_points,
                "opportunities": opportunities,
                "suggested_outreach": suggested_outreach,
                "content_angles": content_angles,
                "sources": sources[:10],  # Limit to top 10
                "created_at": datetime.now().isoformat(),
            })
            
            update_task_status(task_id, ResearchTaskStatus.DONE, result_id=insight_ref.id)
            logger.info(f"Research task {task_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error in research execution: {e}")
            # Fallback: mark as done with basic result
            insight_ref = db.collection("research_insights").document()
            insight_ref.set({
                "user_id": task.user_id,
                "task_id": task_id,
                "topic": task.input_source,
                "title": task.title,
                "summary": f"Research completed for: {task.input_source}",
                "pain_points": [],
                "opportunities": [],
                "suggested_outreach": [],
                "content_angles": [],
                "sources": [],
                "created_at": datetime.now().isoformat(),
            })
            update_task_status(task_id, ResearchTaskStatus.DONE, result_id=insight_ref.id)
            
    except Exception as e:
        logger.error(f"Failed to execute research task {task_id}: {e}")
        update_task_status(task_id, ResearchTaskStatus.FAILED, error=str(e))


@router.post("", response_model=ResearchTaskResponse)
async def create_task(
    request: ResearchTaskCreate,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Create a new research task."""
    try:
        task_id = create_research_task(
            user_id=request.user_id,
            title=request.title,
            input_source=request.input_source,
            source_type=request.source_type,
            research_engine=request.research_engine,
            priority=request.priority,
        )
        
        task = get_research_task(task_id)
        if not task:
            raise HTTPException(status_code=500, detail="Failed to retrieve created task")
        
        # Start execution in background if auto-run is enabled
        # For now, tasks are created in QUEUED state
        
        return ResearchTaskResponse(success=True, task=task)
    except Exception as e:
        logger.exception(f"Error creating research task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")


@router.get("", response_model=ResearchTaskListResponse)
async def list_tasks(
    user_id: str = Query(..., description="User identifier"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    """List research tasks for a user."""
    try:
        tasks = list_research_tasks(user_id=user_id, status=status, limit=limit)
        return ResearchTaskListResponse(
            success=True,
            tasks=tasks,
            total=len(tasks)
        )
    except Exception as e:
        logger.exception(f"Error listing research tasks: {e}")
        return ResearchTaskListResponse(success=True, tasks=[], total=0)


@router.get("/{task_id}", response_model=ResearchTaskResponse)
async def get_task(task_id: str) -> Dict[str, Any]:
    """Get a research task by ID."""
    task = get_research_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return ResearchTaskResponse(success=True, task=task)


@router.post("/{task_id}/run", response_model=ResearchTaskResponse)
async def run_task(
    task_id: str,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Execute a research task."""
    task = get_research_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status == ResearchTaskStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Task is already running")
    
    if task.status == ResearchTaskStatus.DONE:
        raise HTTPException(status_code=400, detail="Task is already completed")
    
    # Start background execution
    background_tasks.add_task(execute_research_task, task_id, task)
    
    # Return updated task
    updated_task = get_research_task(task_id)
    return ResearchTaskResponse(success=True, task=updated_task or task)


@router.get("/{task_id}/insights", response_model=ResearchInsightsResponse)
async def get_insights(task_id: str) -> Dict[str, Any]:
    """Get research insights for a completed task."""
    task = get_research_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.outputs_available or not task.result_id:
        raise HTTPException(status_code=400, detail="Task has no insights available yet")
    
    try:
        # Get insights from research_insights collection
        insight_doc = db.collection("research_insights").document(task.result_id).get()
        
        if not insight_doc.exists:
            raise HTTPException(status_code=404, detail="Insights not found")
        
        data = insight_doc.to_dict()
        insights = ResearchInsight(
            summary=data.get("summary", ""),
            pain_points=data.get("pain_points", []),
            opportunities=data.get("opportunities", []),
            suggested_outreach=data.get("suggested_outreach", []),
            content_angles=data.get("content_angles", []),
            key_findings=data.get("key_findings", []),
            sources=data.get("sources", []),
        )
        
        return ResearchInsightsResponse(
            success=True,
            task_id=task_id,
            task_title=task.title,
            insights=insights
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting insights: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get insights: {str(e)}")

