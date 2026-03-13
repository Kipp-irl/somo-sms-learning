"""
engagement_monitor.py – Background task that checks for disengaged students.

Alert rules:
  - 24h no interaction → warning (no_response)
  - 48h no interaction → critical (disengaged)
  - Score < 30% on recent assignment → info (low_score)
"""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from database import engine
from models import Student, Alert, Assignment, AssessmentResult
from twilio_service import send_sms


CHECK_INTERVAL_MINUTES = 60  # how often to run the check
WARNING_HOURS = 24
CRITICAL_HOURS = 48
LOW_SCORE_THRESHOLD = 0.3


async def _run_checks():
    """Single pass: check all active students for engagement issues."""
    now = datetime.now(timezone.utc)
    warning_cutoff = now - timedelta(hours=WARNING_HOURS)
    critical_cutoff = now - timedelta(hours=CRITICAL_HOURS)

    with Session(engine) as s:
        students = s.exec(
            select(Student).where(Student.state.in_(["active", "aptitude_test"]))
        ).all()

        for student in students:
            # Ensure timezone-aware comparison
            last = student.last_interaction
            if last and not last.tzinfo:
                last = last.replace(tzinfo=timezone.utc)

            # Skip if already has an active (undismissed) alert of same type
            existing = s.exec(
                select(Alert).where(
                    Alert.student_phone == student.phone_number,
                    Alert.dismissed == False,
                )
            ).all()
            existing_types = {a.alert_type for a in existing}

            # Critical: 48h+ silence
            if last and last < critical_cutoff and "disengaged" not in existing_types:
                s.add(Alert(
                    student_phone=student.phone_number,
                    alert_type="disengaged",
                    severity="critical",
                    message=f"{student.name} hasn't responded in 48h+.",
                ))
                # Auto-update state
                student.state = "idle"
                s.add(student)
                s.commit()
                continue

            # Warning: 24h+ silence
            if last and last < warning_cutoff and "no_response" not in existing_types:
                s.add(Alert(
                    student_phone=student.phone_number,
                    alert_type="no_response",
                    severity="warning",
                    message=f"{student.name} hasn't responded in 24h.",
                ))
                s.commit()
                continue

            # Low score check: most recent graded assignment
            recent_assignment = s.exec(
                select(Assignment).where(
                    Assignment.student_phone == student.phone_number,
                    Assignment.status == "graded",
                ).order_by(Assignment.responded_at.desc())
            ).first()

            if recent_assignment and "low_score" not in existing_types:
                result = s.exec(
                    select(AssessmentResult).where(
                        AssessmentResult.assignment_id == recent_assignment.id
                    )
                ).first()
                if result and result.score < LOW_SCORE_THRESHOLD:
                    s.add(Alert(
                        student_phone=student.phone_number,
                        alert_type="low_score",
                        severity="info",
                        message=f"{student.name} scored {int(result.score*100)}% on recent question.",
                    ))
                    s.commit()


def send_nudge(phone: str, name: str):
    """Send an encouragement SMS to a student."""
    msg = f"Hi {name}! Your tutor misses you. Reply to any message to keep learning. You are doing great!"
    send_sms(to=phone, message=msg[:155])


async def engagement_loop():
    """Infinite loop that runs engagement checks on an interval."""
    while True:
        try:
            await _run_checks()
            print(f"[MONITOR] Engagement check completed.")
        except Exception as e:
            print(f"[MONITOR] Error during engagement check: {e}")
        await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)
