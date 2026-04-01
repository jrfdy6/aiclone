from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.lab_experiment_service import (
    get_lab_experiment,
    list_lab_experiments,
    run_content_fallback_experiment,
    run_lab_experiment,
    run_social_response_matrix_experiment,
)

router = APIRouter(tags=["Lab"], prefix="/api/lab")


@router.get("/experiments")
async def list_experiments():
    return {"experiments": list_lab_experiments()}


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str):
    experiment = get_lab_experiment(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Lab experiment not found")
    return experiment


@router.post("/experiments/content-fallback-observatory/run")
async def run_content_fallback():
    return await run_content_fallback_experiment()


@router.post("/experiments/article-response-matrix/run")
async def run_article_response_matrix():
    return await run_social_response_matrix_experiment()


@router.post("/experiments/{experiment_id}/run")
async def run_experiment(experiment_id: str):
    try:
        return await run_lab_experiment(experiment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Lab experiment not found") from exc
