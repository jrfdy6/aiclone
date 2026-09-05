from fastapi import APIRouter, HTTPException
from app.models import OwnerDayActionCreate, OwnerDayActionUpdate, OwnerDaySessionUpsert
from app.services.owner_day_service import OwnerDayService

router = APIRouter(tags=['Owner Day'], prefix='/api/owner-day')
service = OwnerDayService()


@router.put('/sessions', response_model=dict)
def upsert_session(payload: OwnerDaySessionUpsert):
    return service.upsert_session(owner_calendar_date=payload.owner_calendar_date, overview=payload.overview)


@router.get('/sessions/{owner_calendar_date}', response_model=dict)
def read_session(owner_calendar_date: str):
    session = service.get_session(owner_calendar_date)
    if not session:
        raise HTTPException(status_code=404, detail='Owner-day session not found')
    return {**session, 'actions': service.list_actions(session['session_id'])}


@router.post('/actions', response_model=dict)
def create_action(payload: OwnerDayActionCreate):
    try:
        return service.add_action(**payload.model_dump())
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch('/actions/{action_id}', response_model=dict)
def update_action(action_id: str, payload: OwnerDayActionUpdate):
    try:
        return service.update_action(action_id, **payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

