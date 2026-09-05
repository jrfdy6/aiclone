from fastapi import APIRouter, Depends, HTTPException, Request
from app.models import (
    OwnerDayActionCreate,
    OwnerDayActionUpdate,
    OwnerDayBriefingUpdate,
    OwnerDaySessionUpsert,
)
from app.services.owner_day_service import OwnerDayService
from app.security.control_plane import control_plane_auth_required, request_is_authorized

router = APIRouter(tags=['Owner Day'], prefix='/api/owner-day')
service = OwnerDayService()


def _require_owner_day_read(request: Request) -> None:
    """Keep lifecycle exports behind the authenticated control plane."""
    if control_plane_auth_required() and not request_is_authorized(request):
        raise HTTPException(status_code=401, detail="Control-plane authentication required")


@router.put('/sessions', response_model=dict)
def upsert_session(payload: OwnerDaySessionUpsert):
    return service.upsert_session(owner_calendar_date=payload.owner_calendar_date, overview=payload.overview)


@router.get('/sessions/{owner_calendar_date}', response_model=dict)
def read_session(owner_calendar_date: str):
    session = service.get_session(owner_calendar_date)
    if not session:
        raise HTTPException(status_code=404, detail='Owner-day session not found')
    return {**session, 'actions': service.list_actions(session['session_id'])}


@router.get('/events', response_model=list[dict], dependencies=[Depends(_require_owner_day_read)])
def read_events(limit: int = 500):
    """Bounded append-only feed consumed by the existing local Dream runner."""
    return service.list_events(limit=limit)


@router.post('/actions', response_model=dict)
def create_action(payload: OwnerDayActionCreate):
    try:
        return service.add_action(**payload.model_dump())
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put('/actions/{action_id}/briefing', response_model=dict)
def update_action_briefing(action_id: str, payload: OwnerDayBriefingUpdate):
    try:
        return service.update_briefing(action_id, payload.briefing.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch('/actions/{action_id}', response_model=dict)
def update_action(action_id: str, payload: OwnerDayActionUpdate):
    try:
        return service.update_action(action_id, **payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
