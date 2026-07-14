from datetime import UTC, datetime
from ipaddress import IPv4Address
from uuid import UUID, uuid4

from fastapi import FastAPI, status
from pydantic import BaseModel, Field

from database import SessionLocal
from models import Event

from sqlalchemy import select

from datetime import UTC, datetime, timedelta
from sqlalchemy import func, select
from models import Alert, Event

app = FastAPI(
    title="Mini SIEM",
    description="Учебный сервис для приёма и анализа событий безопасности.",
    version="0.1.0",
)


class SecurityEventIn(BaseModel):
    source_ip: IPv4Address
    event_type: str = Field(examples=["login_failed"])
    message: str = Field(examples=["Неудачная попытка входа"])


class SecurityEventOut(SecurityEventIn):
    id: UUID
    received_at: datetime


class AlertOut(BaseModel):
    id: UUID
    source_ip: IPv4Address
    rule_name: str
    severity: str
    message: str
    created_at: datetime

@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/events", response_model=SecurityEventOut, status_code=status.HTTP_201_CREATED)
def receive_event(event: SecurityEventIn) -> SecurityEventOut:
    db_event = Event(
        source_ip = str(event.source_ip),
        event_type = event.event_type,
        message = event.message,
    )  
    with SessionLocal() as session:
        session.add(db_event)
        session.commit()
        session.refresh(db_event)

        if db_event.event_type == 'login_failed':
            window_start = datetime.now(UTC) - timedelta(minutes=5)
            failed_login_count = session.scalar(
                select(func.count(Event.id)).where(
                    Event.source_ip == db_event.source_ip,
                    Event.event_type == 'login_failed',
                    Event.received_at >= window_start,
                )
            )
        existing_alert = session.scalar(
            select(Alert).where(
                Alert.source_ip == db_event.source_ip,
                Alert.rule_name == "possible_brute_force",
                Alert.created_at >= window_start
            )
        )
        if failed_login_count >= 5 and existing_alert is None:
            alert = Alert(
            source_ip=db_event.source_ip,
            rule_name="possible_brute_force",
            severity="high",
            message=(
                f"За 5 минут получено {failed_login_count} "
                "неудачных попыток входа."
            ),
        )
            
            session.add(alert)
            session.commit()

        return SecurityEventOut(
            id=db_event.id,
            source_ip=db_event.source_ip,
            event_type=db_event.event_type,
            message=db_event.message,
            received_at=db_event.received_at
        )
    

@app.get("/events", response_model=list[SecurityEventOut])
def get_events(
    source_ip: IPv4Address | None = None,
    event_type: str | None = None,
):
    statement = select(Event).order_by(Event.received_at.desc())

    if source_ip is not None:
        statement = statement.where(Event.source_ip == str(source_ip))

    if event_type is not None:
        statement = statement.where(Event.event_type == event_type)

    with SessionLocal() as session:
        events = session.scalars(statement).all()

        return [
            SecurityEventOut(
                id=event.id,
                source_ip=event.source_ip,
                event_type=event.event_type,
                message=event.message,
                received_at=event.received_at,
            )
            for event in events
        ]
    
@app.get("/alerts", response_model=list[AlertOut])
def get_alerts():
    with SessionLocal() as session:
        alerts = session.scalars(
            select(Alert).order_by(Alert.created_at.desc())

        ).all()

        return [
            AlertOut(
                id=alert.id,
                source_ip=alert.source_ip,
                rule_name=alert.rule_name,
                severity=alert.severity,
                message=alert.message,
                created_at=alert.created_at,
            )
            for alert in alerts
        ]