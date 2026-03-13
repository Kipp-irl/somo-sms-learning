"""
models.py – SQLModel ORM definitions for Somo.

Models:
  - Instructor          : manages topics, registers students, views performance
  - Student             : SMS-only learner with demographics + aptitude data
  - Cluster             : named group of students (auto from aptitude or instructor-created)
  - ClusterMembership   : junction linking students to clusters
  - Topic               : instructor-defined subject (LLM generates questions)
  - Question            : stored LLM-generated or instructor-edited questions
  - Assignment          : links a question to a student (tracks delivery + response)
  - AssessmentResult    : LLM grading output per assignment
  - StudentProgress     : per-student-per-topic aggregate tracking
  - Alert               : engagement monitoring warnings
  - ProcessedMessage    : webhook idempotency guard
"""

from datetime import date, datetime, timezone
from typing import Optional
import hashlib
import secrets

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint


# ── Passcode hashing ──────────────────────────────────────

def hash_passcode(passcode: str) -> str:
    """Hash a passcode with a random salt. Returns 'salt:hash'."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + passcode).encode()).hexdigest()
    return f"{salt}:{h}"


def verify_passcode(passcode: str, stored: str) -> bool:
    """Verify a passcode against a 'salt:hash' string.
    Also accepts unhashed legacy values for backwards compat."""
    if ":" not in stored:
        # Legacy plaintext – direct comparison
        return passcode == stored
    salt, h = stored.split(":", 1)
    return hashlib.sha256((salt + passcode).encode()).hexdigest() == h


# ── Instructor ─────────────────────────────────────────

class Instructor(SQLModel, table=True):
    __tablename__ = "instructors"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    passcode: str  # stored as "salt:sha256hash"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    topics: list["Topic"] = Relationship(back_populates="instructor")


# ── Student ────────────────────────────────────────────

class Student(SQLModel, table=True):
    __tablename__ = "students"

    phone_number: str = Field(primary_key=True, index=True)
    name: str = Field(default="Student")
    age: Optional[int] = Field(default=None)
    grade: str = Field(default="Ungraded")
    preferred_language: str = Field(default="English")

    # Aptitude & clustering
    aptitude_score: Optional[float] = Field(default=None)  # 0.0-1.0 after test
    aptitude_level: str = Field(default="untested")         # untested/beginner/intermediate/advanced
    cluster_id: Optional[str] = Field(default=None)         # e.g. "Grade 5-beginner"
    aptitude_step: int = Field(default=0)                   # current aptitude question (0-5)
    aptitude_correct: int = Field(default=0)                # correct answers during test
    aptitude_current_q: Optional[str] = Field(default=None) # last aptitude question text for grading

    # SMS state machine
    state: str = Field(default="registered")  # registered/aptitude_test/active/idle
    active_topic_id: Optional[int] = Field(default=None, foreign_key="topics.id")

    # Rate limiting
    daily_request_count: int = Field(default=0)
    last_request_date: date = Field(default_factory=lambda: date.today())

    # Timestamps
    last_interaction: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    progress: list["StudentProgress"] = Relationship(back_populates="student")
    assignments: list["Assignment"] = Relationship(back_populates="student")
    alerts: list["Alert"] = Relationship(back_populates="student")


# ── Cluster ───────────────────────────────────────────

class Cluster(SQLModel, table=True):
    """Named group of students — auto-generated from aptitude or instructor-created."""
    __tablename__ = "clusters"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)                         # e.g. "Grade 5-beginner" or "Remedial Math"
    description: str = Field(default="")
    instructor_id: Optional[int] = Field(default=None, foreign_key="instructors.id")
    is_custom: bool = Field(default=True)                 # False = auto-generated from aptitude
    grade_level: str = Field(default="")                  # e.g. "Grade 5" or "" for mixed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    memberships: list["ClusterMembership"] = Relationship(back_populates="cluster")


class ClusterMembership(SQLModel, table=True):
    """Junction table linking students to clusters."""
    __tablename__ = "cluster_memberships"
    __table_args__ = (
        UniqueConstraint("cluster_id", "student_phone", name="uq_cluster_member"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    cluster_id: int = Field(foreign_key="clusters.id", index=True)
    student_phone: str = Field(foreign_key="students.phone_number", index=True)
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    cluster: Optional["Cluster"] = Relationship(back_populates="memberships")


# ── Topic ──────────────────────────────────────────────

class Topic(SQLModel, table=True):
    """Instructor sets topic + difficulty. LLM generates all questions."""
    __tablename__ = "topics"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    subject: str = Field(default="General")
    description: str = Field(default="")
    difficulty: str = Field(default="beginner")
    instructor_id: Optional[int] = Field(default=None, foreign_key="instructors.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    instructor: Optional[Instructor] = Relationship(back_populates="topics")
    questions: list["Question"] = Relationship(back_populates="topic")
    progress: list["StudentProgress"] = Relationship(back_populates="topic")


# ── Question ───────────────────────────────────────────

class Question(SQLModel, table=True):
    """LLM-generated or instructor-edited question, stored for reuse."""
    __tablename__ = "questions"

    id: Optional[int] = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topics.id", index=True)
    text: str                                        # The question (≤150 chars for SMS)
    difficulty: str = Field(default="beginner")      # beginner/intermediate/advanced
    bloom_level: str = Field(default="remember")     # remember/understand/apply/analyze
    correct_hint: str = Field(default="")            # Brief context for LLM grading
    generated_by: str = Field(default="llm")         # "llm" or "instructor"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    topic: Optional[Topic] = Relationship(back_populates="questions")
    assignments: list["Assignment"] = Relationship(back_populates="question")


# ── Assignment ─────────────────────────────────────────

class Assignment(SQLModel, table=True):
    """Links a question to a student. Tracks delivery and response."""
    __tablename__ = "assignments"

    id: Optional[int] = Field(default=None, primary_key=True)
    question_id: Optional[int] = Field(default=None, foreign_key="questions.id", index=True)
    student_phone: str = Field(foreign_key="students.phone_number", index=True)

    sent_at: Optional[datetime] = Field(default=None)
    delivered: bool = Field(default=False)
    response_text: Optional[str] = Field(default=None)
    responded_at: Optional[datetime] = Field(default=None)
    status: str = Field(default="pending")  # pending/sent/answered/graded/expired

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    question: Optional[Question] = Relationship(back_populates="assignments")
    student: Optional[Student] = Relationship(back_populates="assignments")
    result: Optional["AssessmentResult"] = Relationship(back_populates="assignment")


# ── AssessmentResult ───────────────────────────────────

class AssessmentResult(SQLModel, table=True):
    """LLM grading output for a single assignment."""
    __tablename__ = "assessment_results"

    id: Optional[int] = Field(default=None, primary_key=True)
    assignment_id: int = Field(foreign_key="assignments.id", unique=True, index=True)

    score: float = Field(default=0.0)          # 0.0 to 1.0
    correct: bool = Field(default=False)
    feedback: str = Field(default="")          # LLM-generated feedback (≤100 chars)
    improvement_areas: str = Field(default="") # JSON list of weak areas
    bloom_level_achieved: str = Field(default="remember")
    graded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    assignment: Optional[Assignment] = Relationship(back_populates="result")


# ── StudentProgress ────────────────────────────────────

class StudentProgress(SQLModel, table=True):
    """Per-student-per-topic aggregate tracking."""
    __tablename__ = "student_progress"

    id: Optional[int] = Field(default=None, primary_key=True)
    student_phone: str = Field(foreign_key="students.phone_number", index=True)
    topic_id: int = Field(foreign_key="topics.id", index=True)

    questions_attempted: int = Field(default=0)
    questions_correct: int = Field(default=0)
    current_difficulty: str = Field(default="beginner")
    history_summary: Optional[str] = Field(default=None)   # rolling LLM context
    last_active: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    student: Optional[Student] = Relationship(back_populates="progress")
    topic: Optional[Topic] = Relationship(back_populates="progress")


# ── Alert ──────────────────────────────────────────────

class Alert(SQLModel, table=True):
    """Engagement monitoring warnings."""
    __tablename__ = "alerts"

    id: Optional[int] = Field(default=None, primary_key=True)
    student_phone: str = Field(foreign_key="students.phone_number", index=True)
    alert_type: str       # no_response / disengaged / low_score / delivery_failure
    severity: str         # info / warning / critical
    message: str
    dismissed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    student: Optional[Student] = Relationship(back_populates="alerts")


# ── ProcessedMessage ───────────────────────────────────

class ProcessedMessage(SQLModel, table=True):
    """Webhook idempotency guard."""
    __tablename__ = "processed_messages"

    message_id: str = Field(primary_key=True)
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
