"""
main.py – FastAPI backend for Somo.

Architecture:
  - Students interact ONLY via SMS (Twilio webhook)
  - Instructors manage students, topics, questions, and monitoring via web
  - LLM generates questions, grades answers, suggests improvements
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from dotenv import load_dotenv
load_dotenv()

import os
import sys

# Fix Windows console encoding for emoji/unicode in LLM responses
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import BackgroundTasks, Depends, FastAPI, Form, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, col

from database import engine, get_session, init_db
from models import (
    Instructor, Student, Topic, Question, Assignment,
    AssessmentResult, StudentProgress, Alert, ProcessedMessage,
    Cluster, ClusterMembership,
    hash_passcode, verify_passcode,
)
from llm_service import (
    generate_aptitude_question, generate_questions, grade_answer,
    suggest_improvements, generate_sms_reply, summarize_history,
    generate_class_insights, generate_cluster_insights,
)
from twilio_service import send_sms, set_capture_mode, get_captured_messages, fetch_inbound_messages
from engagement_monitor import engagement_loop, send_nudge


async def _poll_inbound_sms():
    """Poll Twilio for inbound messages every 15 seconds (no webhook needed)."""
    print("[POLL] Inbound SMS polling started (every 15s)")
    seen_sids: set[str] = set()
    while True:
        try:
            await asyncio.sleep(15)
            loop = asyncio.get_event_loop()
            messages = await loop.run_in_executor(None, fetch_inbound_messages, 2)
            for msg in messages:
                if msg["sid"] in seen_sids:
                    continue
                seen_sids.add(msg["sid"])
                print(f"[POLL] New inbound from {msg['from_number']}: {msg['body']!r}")
                await loop.run_in_executor(
                    None, _process_sms, msg["from_number"], msg["body"], msg["sid"]
                )
            # Prevent memory growth
            if len(seen_sids) > 200:
                seen_sids.clear()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[POLL] Error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_defaults()
    _migrate_auto_clusters()
    task = asyncio.create_task(engagement_loop())
    poll_task = asyncio.create_task(_poll_inbound_sms())
    yield
    task.cancel()
    poll_task.cancel()


app = FastAPI(title="Somo", version="3.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DAILY_LIMIT = 10


# ── Instructor auth dependency ─────────────────────────
async def require_instructor(
    x_instructor_id: str = Header(..., alias="X-Instructor-Id"),
    session: Session = Depends(get_session),
) -> Instructor:
    """Validate the instructor ID header on protected API routes."""
    try:
        inst_id = int(x_instructor_id)
    except (ValueError, TypeError):
        raise_auth_error()
    inst = session.get(Instructor, inst_id)
    if not inst:
        raise_auth_error()
    return inst


def raise_auth_error():
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Invalid or missing instructor credentials.")


def _seed_defaults():
    with Session(engine) as s:
        if s.exec(select(Instructor)).first():
            return
        inst = Instructor(
            name="Default Instructor",
            passcode=hash_passcode(os.getenv("INSTRUCTOR_PASSCODE", "admin123")),
        )
        s.add(inst)
        s.commit()
        s.refresh(inst)
        s.add(Topic(
            title="Basic Math", subject="Mathematics",
            description="Addition, subtraction, multiplication and division for beginners.",
            difficulty="beginner", instructor_id=inst.id,
        ))
        s.add(Topic(
            title="English Grammar", subject="English",
            description="Parts of speech, sentence structure, tenses.",
            difficulty="beginner", instructor_id=inst.id,
        ))
        s.commit()
        # Seed demo data for dashboard demonstration
        from seed_demo import seed_demo_data
        seed_demo_data(s, instructor_id=inst.id)


def _migrate_auto_clusters():
    """Convert Student.cluster_id strings into Cluster + ClusterMembership records (idempotent)."""
    with Session(engine) as s:
        students_with_clusters = s.exec(
            select(Student).where(Student.cluster_id.isnot(None))
        ).all()
        cluster_groups: dict[str, list[Student]] = {}
        for st in students_with_clusters:
            cluster_groups.setdefault(st.cluster_id, []).append(st)

        for cid, members in cluster_groups.items():
            existing = s.exec(
                select(Cluster).where(Cluster.name == cid, Cluster.is_custom == False)
            ).first()
            if not existing:
                grade = cid.rsplit("-", 1)[0] if "-" in cid else ""
                cluster = Cluster(name=cid, is_custom=False, grade_level=grade,
                                  description=f"Auto: {cid}")
                s.add(cluster)
                s.commit()
                s.refresh(cluster)
            else:
                cluster = existing

            for st in members:
                exists = s.exec(
                    select(ClusterMembership).where(
                        ClusterMembership.cluster_id == cluster.id,
                        ClusterMembership.student_phone == st.phone_number,
                    )
                ).first()
                if not exists:
                    s.add(ClusterMembership(cluster_id=cluster.id, student_phone=st.phone_number))
            s.commit()


# ── Rate limiting ───────────────────────────────────
def _check_limit(student: Student, s: Session) -> bool:
    today = date.today()
    if student.last_request_date != today:
        student.daily_request_count = 0
        student.last_request_date = today
        s.add(student)
        s.commit()
    return student.daily_request_count < DAILY_LIMIT


def _inc_usage(student: Student, s: Session):
    student.daily_request_count += 1
    student.last_interaction = datetime.now(timezone.utc)
    s.add(student)
    s.commit()


# ═══════════════════════════════════════════════════════
# WEB PAGES — Instructor only
# ═══════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse("/instructor/login")


@app.get("/instructor/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/instructor", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    instructor_id = request.cookies.get("instructor_id")
    if not instructor_id:
        return RedirectResponse("/instructor/login")
    return templates.TemplateResponse("dashboard.html", {"request": request})


# ── Instructor auth ──────────────────────────────────
@app.post("/instructor/login")
async def login(request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    name = data.get("name", "").strip()
    passcode = data.get("passcode", "").strip()
    stmt = select(Instructor).where(Instructor.name == name)
    inst = session.exec(stmt).first()
    if not inst or not verify_passcode(passcode, inst.passcode):
        return JSONResponse({"error": "Invalid credentials."}, status_code=401)
    response = JSONResponse({"instructor_id": inst.id, "name": inst.name})
    response.set_cookie(key="instructor_id", value=str(inst.id), httponly=True)
    return response


# ═══════════════════════════════════════════════════════
# STUDENT CRUD
# ═══════════════════════════════════════════════════════

@app.post("/api/students")
async def register_student(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    d = await request.json()
    phone = d.get("phone_number", "").strip()
    if not phone:
        return JSONResponse({"error": "Phone number is required."}, status_code=400)

    existing = session.get(Student, phone)
    if existing:
        return JSONResponse({"error": "Student already registered."}, status_code=409)

    student = Student(
        phone_number=phone,
        name=d.get("name", "Student"),
        age=d.get("age"),
        grade=d.get("grade", "Ungraded"),
        preferred_language=d.get("preferred_language", "English"),
        state="registered",
    )
    session.add(student)
    session.commit()

    # Send welcome SMS + start aptitude test in background
    background_tasks.add_task(_start_aptitude, phone)

    return {"phone_number": phone, "name": student.name, "state": student.state}


@app.get("/api/students")
async def list_students(
    grade: str | None = None,
    aptitude: str | None = None,
    cluster: str | None = None,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    stmt = select(Student)
    if grade:
        stmt = stmt.where(Student.grade == grade)
    if aptitude:
        stmt = stmt.where(Student.aptitude_level == aptitude)
    if cluster:
        stmt = stmt.where(Student.cluster_id == cluster)
    students = session.exec(stmt).all()
    return [
        {
            "phone": s.phone_number, "name": s.name, "age": s.age,
            "grade": s.grade, "language": s.preferred_language,
            "aptitude_level": s.aptitude_level, "aptitude_score": s.aptitude_score,
            "cluster": s.cluster_id, "state": s.state,
            "daily_used": s.daily_request_count,
            "last_interaction": s.last_interaction.isoformat(),
            "created": s.created_at.isoformat(),
        }
        for s in students
    ]


@app.get("/api/students/{phone}")
async def get_student(phone: str, session: Session = Depends(get_session), instructor: Instructor = Depends(require_instructor)):
    student = session.get(Student, phone)
    if not student:
        return JSONResponse({"error": "Not found."}, status_code=404)

    progs = session.exec(
        select(StudentProgress).where(StudentProgress.student_phone == phone)
    ).all()
    assignments = session.exec(
        select(Assignment).where(Assignment.student_phone == phone)
    ).all()

    return {
        "phone": student.phone_number, "name": student.name, "age": student.age,
        "grade": student.grade, "language": student.preferred_language,
        "aptitude_level": student.aptitude_level, "aptitude_score": student.aptitude_score,
        "cluster": student.cluster_id, "state": student.state,
        "progress": [
            {
                "topic_id": p.topic_id,
                "topic_title": p.topic.title if p.topic else "?",
                "attempted": p.questions_attempted,
                "correct": p.questions_correct,
                "difficulty": p.current_difficulty,
                "last_active": p.last_active.isoformat(),
            }
            for p in progs
        ],
        "assignments": [
            {
                "id": a.id, "question_text": a.question.text if a.question else "",
                "status": a.status, "response": a.response_text,
                "score": a.result.score if a.result else None,
                "feedback": a.result.feedback if a.result else None,
            }
            for a in assignments
        ],
    }


# ═══════════════════════════════════════════════════════
# TOPICS CRUD
# ═══════════════════════════════════════════════════════

@app.get("/api/topics")
async def list_topics(session: Session = Depends(get_session), instructor: Instructor = Depends(require_instructor)):
    topics = session.exec(select(Topic)).all()
    return [
        {"id": t.id, "title": t.title, "subject": t.subject,
         "difficulty": t.difficulty, "description": t.description}
        for t in topics
    ]


@app.post("/api/topics")
async def create_topic(request: Request, session: Session = Depends(get_session), instructor: Instructor = Depends(require_instructor)):
    d = await request.json()
    topic = Topic(
        title=d.get("title", "Untitled"),
        subject=d.get("subject", "General"),
        description=d.get("description", ""),
        difficulty=d.get("difficulty", "beginner"),
        instructor_id=instructor.id,
    )
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return {"id": topic.id, "title": topic.title}


@app.delete("/api/topics/{topic_id}")
async def delete_topic(topic_id: int, session: Session = Depends(get_session), instructor: Instructor = Depends(require_instructor)):
    topic = session.get(Topic, topic_id)
    if not topic:
        return JSONResponse({"error": "Not found."}, status_code=404)
    session.delete(topic)
    session.commit()
    return {"deleted": topic_id}


# ═══════════════════════════════════════════════════════
# QUESTION GENERATION + MANAGEMENT
# ═══════════════════════════════════════════════════════

@app.post("/api/questions/generate")
async def generate_topic_questions(request: Request, session: Session = Depends(get_session), instructor: Instructor = Depends(require_instructor)):
    d = await request.json()
    topic_id = d.get("topic_id")
    topic = session.get(Topic, topic_id)
    if not topic:
        return JSONResponse({"error": "Topic not found."}, status_code=404)

    count = min(d.get("count", 5), 10)
    bloom = d.get("bloom_level", "understand")

    questions = generate_questions(
        topic_title=topic.title,
        topic_description=topic.description,
        difficulty=d.get("difficulty", topic.difficulty),
        bloom_level=bloom,
        count=count,
        language=d.get("language", "English"),
        grade=d.get("grade", ""),
    )

    saved = []
    for q in questions:
        obj = Question(
            topic_id=topic_id,
            text=q.get("text", "")[:150],
            difficulty=q.get("difficulty", topic.difficulty),
            bloom_level=q.get("bloom_level", bloom),
            correct_hint=q.get("correct_hint", "")[:50],
            generated_by="llm",
        )
        session.add(obj)
        session.commit()
        session.refresh(obj)
        saved.append({
            "id": obj.id, "text": obj.text, "difficulty": obj.difficulty,
            "bloom_level": obj.bloom_level, "correct_hint": obj.correct_hint,
        })

    return saved


@app.get("/api/questions")
async def list_questions(
    topic_id: int | None = None,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    stmt = select(Question)
    if topic_id:
        stmt = stmt.where(Question.topic_id == topic_id)
    questions = session.exec(stmt).all()
    return [
        {
            "id": q.id, "topic_id": q.topic_id, "text": q.text,
            "difficulty": q.difficulty, "bloom_level": q.bloom_level,
            "correct_hint": q.correct_hint, "generated_by": q.generated_by,
        }
        for q in questions
    ]


@app.put("/api/questions/{qid}")
async def edit_question(qid: int, request: Request, session: Session = Depends(get_session), instructor: Instructor = Depends(require_instructor)):
    q = session.get(Question, qid)
    if not q:
        return JSONResponse({"error": "Not found."}, status_code=404)
    d = await request.json()
    if "text" in d:
        q.text = d["text"][:150]
    if "correct_hint" in d:
        q.correct_hint = d["correct_hint"][:50]
    if "difficulty" in d:
        q.difficulty = d["difficulty"]
    q.generated_by = "instructor"
    session.add(q)
    session.commit()
    return {"id": q.id, "text": q.text}


@app.delete("/api/questions/{qid}")
async def delete_question(qid: int, session: Session = Depends(get_session), instructor: Instructor = Depends(require_instructor)):
    q = session.get(Question, qid)
    if not q:
        return JSONResponse({"error": "Not found."}, status_code=404)
    session.delete(q)
    session.commit()
    return {"deleted": qid}


# ═══════════════════════════════════════════════════════
# ASSIGNMENT DISPATCH
# ═══════════════════════════════════════════════════════

@app.post("/api/assignments/send")
async def send_assignments(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    """Send selected questions to selected students via SMS."""
    d = await request.json()
    question_ids = d.get("question_ids", [])
    student_phones = d.get("student_phones", [])

    if not question_ids or not student_phones:
        return JSONResponse({"error": "Select questions and students."}, status_code=400)

    created = []
    for qid in question_ids:
        question = session.get(Question, qid)
        if not question:
            continue
        for phone in student_phones:
            student = session.get(Student, phone)
            if not student:
                continue
            assignment = Assignment(
                question_id=qid,
                student_phone=phone,
                status="pending",
            )
            session.add(assignment)
            session.commit()
            session.refresh(assignment)
            created.append(assignment.id)
            # Dispatch SMS in background
            background_tasks.add_task(_send_assignment_sms, assignment.id)

    return {"created": len(created), "assignment_ids": created}


async def _send_assignment_sms(assignment_id: int):
    """Background: send the question SMS and update assignment status."""
    with Session(engine) as s:
        assignment = s.get(Assignment, assignment_id)
        if not assignment or not assignment.question:
            return
        question = s.get(Question, assignment.question_id)
        if not question:
            return
        response = send_sms(to=assignment.student_phone, message=question.text)

        # Check for delivery failure
        failed = False
        if "error" in response:
            failed = True
        elif response.get("status") in ("failed", "undelivered"):
            failed = True

        if failed:
            student = s.get(Student, assignment.student_phone)
            s.add(Alert(
                student_phone=assignment.student_phone,
                alert_type="delivery_failure",
                severity="warning",
                message=f"SMS delivery failed for {student.name if student else assignment.student_phone}.",
            ))

        assignment.status = "sent"
        assignment.sent_at = datetime.now(timezone.utc)
        assignment.delivered = not failed
        s.add(assignment)
        s.commit()


# ═══════════════════════════════════════════════════════
# ASSESSMENTS / METRICS
# ═══════════════════════════════════════════════════════

@app.get("/api/assessments")
async def list_assessments(
    status: str | None = None,
    topic_id: int | None = None,
    grade: str | None = None,
    student_phone: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 25,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    stmt = select(Assignment)
    if status:
        stmt = stmt.where(Assignment.status == status)
    if student_phone:
        stmt = stmt.where(Assignment.student_phone == student_phone)
    if topic_id:
        qids = [q.id for q in session.exec(select(Question).where(Question.topic_id == topic_id)).all()]
        if qids:
            stmt = stmt.where(col(Assignment.question_id).in_(qids))
        else:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
    if grade:
        phones = [s.phone_number for s in session.exec(select(Student).where(Student.grade == grade)).all()]
        if phones:
            stmt = stmt.where(col(Assignment.student_phone).in_(phones))
        else:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
    if date_from:
        try:
            stmt = stmt.where(Assignment.created_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            stmt = stmt.where(Assignment.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))
        except ValueError:
            pass

    all_results = session.exec(stmt.order_by(col(Assignment.created_at).desc())).all()
    total = len(all_results)
    offset = (page - 1) * page_size
    paginated = all_results[offset:offset + page_size]

    items = [
        {
            "id": a.id,
            "student_phone": a.student_phone,
            "student_name": a.student.name if a.student else "?",
            "student_grade": a.student.grade if a.student else "?",
            "question_text": a.question.text if a.question else "",
            "topic_title": a.question.topic.title if a.question and a.question.topic else "?",
            "status": a.status,
            "response": a.response_text,
            "sent_at": a.sent_at.isoformat() if a.sent_at else None,
            "responded_at": a.responded_at.isoformat() if a.responded_at else None,
            "created_at": a.created_at.isoformat(),
            "score": a.result.score if a.result else None,
            "feedback": a.result.feedback if a.result else None,
            "improvement": a.result.improvement_areas if a.result else None,
        }
        for a in paginated
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.get("/api/assessments/stats")
async def assessment_stats(
    topic_id: int | None = None,
    grade: str | None = None,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    assignments = session.exec(select(Assignment)).all()
    if topic_id:
        qids = {q.id for q in session.exec(select(Question).where(Question.topic_id == topic_id)).all()}
        assignments = [a for a in assignments if a.question_id in qids]
    if grade:
        phones = {s.phone_number for s in session.exec(select(Student).where(Student.grade == grade)).all()}
        assignments = [a for a in assignments if a.student_phone in phones]

    total = len(assignments)
    graded = [a for a in assignments if a.status == "graded" and a.result]
    answered = [a for a in assignments if a.status in ("answered", "graded")]
    pending = [a for a in assignments if a.status in ("pending", "sent")]
    avg_score = sum(a.result.score for a in graded) / len(graded) if graded else 0
    response_rate = len(answered) / total if total else 0
    correct_rate = sum(1 for a in graded if a.result.correct) / len(graded) if graded else 0

    buckets = {"0-20%": 0, "21-40%": 0, "41-60%": 0, "61-80%": 0, "81-100%": 0}
    for a in graded:
        pct = a.result.score * 100
        if pct <= 20: buckets["0-20%"] += 1
        elif pct <= 40: buckets["21-40%"] += 1
        elif pct <= 60: buckets["41-60%"] += 1
        elif pct <= 80: buckets["61-80%"] += 1
        else: buckets["81-100%"] += 1

    return {
        "total": total, "graded": len(graded),
        "answered": len(answered), "pending": len(pending),
        "avg_score": round(avg_score, 2),
        "response_rate": round(response_rate, 2),
        "correct_rate": round(correct_rate, 2),
        "score_distribution": buckets,
    }


@app.get("/api/assessments/student/{phone}")
async def student_assessments(phone: str, session: Session = Depends(get_session), instructor: Instructor = Depends(require_instructor)):
    assignments = session.exec(
        select(Assignment).where(Assignment.student_phone == phone)
        .order_by(col(Assignment.created_at).desc())
    ).all()
    return [
        {
            "id": a.id,
            "question_text": a.question.text if a.question else "",
            "status": a.status, "response": a.response_text,
            "score": a.result.score if a.result else None,
            "correct": a.result.correct if a.result else None,
            "feedback": a.result.feedback if a.result else None,
            "improvement": a.result.improvement_areas if a.result else None,
        }
        for a in assignments
    ]


@app.get("/api/assessments/topic/{topic_id}")
async def topic_assessments(topic_id: int, session: Session = Depends(get_session), instructor: Instructor = Depends(require_instructor)):
    questions = session.exec(
        select(Question).where(Question.topic_id == topic_id)
    ).all()
    qids = [q.id for q in questions]
    if not qids:
        return {"topic_id": topic_id, "total": 0, "graded": 0, "avg_score": 0}
    assignments = session.exec(
        select(Assignment).where(col(Assignment.question_id).in_(qids))
    ).all()
    graded = [a for a in assignments if a.result]
    avg_score = sum(a.result.score for a in graded) / len(graded) if graded else 0
    return {
        "topic_id": topic_id, "total": len(assignments),
        "graded": len(graded), "avg_score": round(avg_score, 2),
        "answered": sum(1 for a in assignments if a.status in ("answered", "graded")),
        "pending": sum(1 for a in assignments if a.status in ("pending", "sent")),
    }


# ═══════════════════════════════════════════════════════
# CLUSTERS
# ═══════════════════════════════════════════════════════

@app.get("/api/clusters")
async def list_clusters(session: Session = Depends(get_session), instructor: Instructor = Depends(require_instructor)):
    clusters = session.exec(select(Cluster)).all()
    result = []
    for c in clusters:
        memberships = session.exec(
            select(ClusterMembership).where(ClusterMembership.cluster_id == c.id)
        ).all()
        students = []
        for m in memberships:
            st = session.get(Student, m.student_phone)
            if st:
                students.append({
                    "phone": st.phone_number, "name": st.name,
                    "grade": st.grade, "aptitude_score": st.aptitude_score,
                    "aptitude_level": st.aptitude_level, "state": st.state,
                })
        result.append({
            "id": c.id, "name": c.name, "description": c.description,
            "is_custom": c.is_custom, "grade_level": c.grade_level,
            "created_at": c.created_at.isoformat(),
            "count": len(students), "students": students,
        })
    return result


@app.post("/api/clusters")
async def create_cluster(
    request: Request,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    d = await request.json()
    name = d.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "Cluster name is required."}, status_code=400)
    existing = session.exec(select(Cluster).where(Cluster.name == name)).first()
    if existing:
        return JSONResponse({"error": "A cluster with that name already exists."}, status_code=409)
    cluster = Cluster(
        name=name, description=d.get("description", ""),
        instructor_id=instructor.id, is_custom=True,
        grade_level=d.get("grade_level", ""),
    )
    session.add(cluster)
    session.commit()
    session.refresh(cluster)
    for phone in d.get("student_phones", []):
        if session.get(Student, phone):
            session.add(ClusterMembership(cluster_id=cluster.id, student_phone=phone))
    session.commit()
    return {"id": cluster.id, "name": cluster.name}


@app.put("/api/clusters/{cluster_id}")
async def update_cluster(
    cluster_id: int, request: Request,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    cluster = session.get(Cluster, cluster_id)
    if not cluster:
        return JSONResponse({"error": "Cluster not found."}, status_code=404)
    d = await request.json()
    if "name" in d:
        cluster.name = d["name"].strip()
    if "description" in d:
        cluster.description = d["description"]
    if "grade_level" in d:
        cluster.grade_level = d["grade_level"]
    session.add(cluster)
    session.commit()
    return {"id": cluster.id, "name": cluster.name}


@app.delete("/api/clusters/{cluster_id}")
async def delete_cluster(
    cluster_id: int,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    cluster = session.get(Cluster, cluster_id)
    if not cluster:
        return JSONResponse({"error": "Cluster not found."}, status_code=404)
    if not cluster.is_custom:
        return JSONResponse({"error": "Cannot delete auto-generated clusters."}, status_code=400)
    for m in session.exec(select(ClusterMembership).where(ClusterMembership.cluster_id == cluster_id)).all():
        session.delete(m)
    session.delete(cluster)
    session.commit()
    return {"deleted": cluster_id}


@app.post("/api/clusters/{cluster_id}/members")
async def add_cluster_members(
    cluster_id: int, request: Request,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    cluster = session.get(Cluster, cluster_id)
    if not cluster:
        return JSONResponse({"error": "Cluster not found."}, status_code=404)
    d = await request.json()
    added = 0
    for phone in d.get("student_phones", []):
        if not session.get(Student, phone):
            continue
        exists = session.exec(
            select(ClusterMembership).where(
                ClusterMembership.cluster_id == cluster_id,
                ClusterMembership.student_phone == phone,
            )
        ).first()
        if not exists:
            session.add(ClusterMembership(cluster_id=cluster_id, student_phone=phone))
            added += 1
    session.commit()
    return {"added": added, "cluster_id": cluster_id}


@app.delete("/api/clusters/{cluster_id}/members/{phone}")
async def remove_cluster_member(
    cluster_id: int, phone: str,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    membership = session.exec(
        select(ClusterMembership).where(
            ClusterMembership.cluster_id == cluster_id,
            ClusterMembership.student_phone == phone,
        )
    ).first()
    if not membership:
        return JSONResponse({"error": "Membership not found."}, status_code=404)
    session.delete(membership)
    session.commit()
    return {"removed": phone, "cluster_id": cluster_id}


@app.get("/api/clusters/{cluster_id}/stats")
async def cluster_stats(
    cluster_id: int,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    cluster = session.get(Cluster, cluster_id)
    if not cluster:
        return JSONResponse({"error": "Cluster not found."}, status_code=404)
    memberships = session.exec(
        select(ClusterMembership).where(ClusterMembership.cluster_id == cluster_id)
    ).all()
    phones = [m.student_phone for m in memberships]
    if not phones:
        return {"cluster_id": cluster_id, "name": cluster.name, "member_count": 0,
                "avg_score": 0, "response_rate": 0, "topic_performance": [], "score_trend": []}
    assignments = session.exec(
        select(Assignment).where(col(Assignment.student_phone).in_(phones))
    ).all()
    graded = [a for a in assignments if a.status == "graded" and a.result]
    avg_score = sum(a.result.score for a in graded) / len(graded) if graded else 0
    response_rate = sum(1 for a in assignments if a.response_text) / len(assignments) if assignments else 0

    from collections import defaultdict
    topic_scores: dict[str, list[float]] = defaultdict(list)
    for a in graded:
        if a.question and a.question.topic:
            topic_scores[a.question.topic.title].append(a.result.score)
    topic_performance = [
        {"topic": t, "avg_score": round(sum(sc) / len(sc), 2), "count": len(sc)}
        for t, sc in topic_scores.items()
    ]

    daily_scores: dict[str, list[float]] = defaultdict(list)
    for a in graded:
        if a.result.graded_at:
            gt = a.result.graded_at
            if not gt.tzinfo:
                gt = gt.replace(tzinfo=timezone.utc)
            day = gt.strftime("%Y-%m-%d")
            daily_scores[day].append(a.result.score)
    today = date.today()
    score_trend = []
    for i in range(14):
        d = (today - timedelta(days=13 - i)).isoformat()
        scores = daily_scores.get(d, [])
        score_trend.append({
            "date": d,
            "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
            "count": len(scores),
        })
    return {
        "cluster_id": cluster_id, "name": cluster.name,
        "member_count": len(phones), "avg_score": round(avg_score, 2),
        "response_rate": round(response_rate, 2),
        "topic_performance": topic_performance, "score_trend": score_trend,
    }


_cluster_insights_cache: dict[int, dict] = {}


@app.get("/api/clusters/{cluster_id}/insights")
async def cluster_insights(
    cluster_id: int,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    now = datetime.now(timezone.utc)
    cached = _cluster_insights_cache.get(cluster_id)
    if cached and cached.get("generated_at"):
        age = (now - cached["generated_at"]).total_seconds()
        if age < 1800:
            return {**cached["data"], "generated_at": cached["generated_at"].isoformat(), "cached": True}

    cluster = session.get(Cluster, cluster_id)
    if not cluster:
        return JSONResponse({"error": "Cluster not found."}, status_code=404)
    memberships = session.exec(
        select(ClusterMembership).where(ClusterMembership.cluster_id == cluster_id)
    ).all()
    phones = [m.student_phone for m in memberships]
    students = [s for s in (session.get(Student, p) for p in phones) if s]
    assignments = session.exec(
        select(Assignment).where(col(Assignment.student_phone).in_(phones))
    ).all() if phones else []
    graded = [a for a in assignments if a.status == "graded" and a.result]
    avg_score = sum(a.result.score for a in graded) / len(graded) if graded else 0

    cluster_data = {
        "cluster_name": cluster.name, "grade_level": cluster.grade_level,
        "is_custom": cluster.is_custom, "member_count": len(students),
        "avg_score": round(avg_score, 2), "total_assessments": len(assignments),
        "graded_assessments": len(graded),
        "students": [{"name": s.name, "grade": s.grade, "aptitude": s.aptitude_level, "state": s.state} for s in students[:10]],
        "response_rate": round(sum(1 for a in assignments if a.response_text) / len(assignments), 2) if assignments else 0,
    }
    insights = generate_cluster_insights(cluster_data)
    insights["generated_at"] = now.isoformat()
    insights["cached"] = False
    _cluster_insights_cache[cluster_id] = {"data": insights, "generated_at": now}
    return insights


@app.post("/api/clusters/{cluster_id}/send")
async def send_to_cluster(
    cluster_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    cluster = session.get(Cluster, cluster_id)
    if not cluster:
        return JSONResponse({"error": "Cluster not found."}, status_code=404)
    d = await request.json()
    question_ids = d.get("question_ids", [])
    memberships = session.exec(
        select(ClusterMembership).where(ClusterMembership.cluster_id == cluster_id)
    ).all()
    phones = [m.student_phone for m in memberships]
    if not phones or not question_ids:
        return JSONResponse({"error": "No students in cluster or no questions selected."}, status_code=400)
    count = 0
    for qid in question_ids:
        question = session.get(Question, qid)
        if not question:
            continue
        for phone in phones:
            assignment = Assignment(question_id=qid, student_phone=phone, status="pending")
            session.add(assignment)
            session.commit()
            session.refresh(assignment)
            background_tasks.add_task(_send_assignment_sms, assignment.id)
            count += 1
    return {"sent": count, "cluster_id": cluster_id, "cluster_name": cluster.name, "students": len(phones)}


@app.post("/api/clusters/{cluster_id}/generate")
async def generate_for_cluster(
    cluster_id: int, request: Request,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    cluster = session.get(Cluster, cluster_id)
    if not cluster:
        return JSONResponse({"error": "Cluster not found."}, status_code=404)
    d = await request.json()
    topic_id = d.get("topic_id")
    topic = session.get(Topic, topic_id)
    if not topic:
        return JSONResponse({"error": "Topic not found."}, status_code=404)
    count = min(d.get("count", 5), 10)
    bloom = d.get("bloom_level", "understand")
    difficulty = d.get("difficulty", topic.difficulty)
    grade = cluster.grade_level or d.get("grade", "")
    questions = generate_questions(
        topic_title=topic.title, topic_description=topic.description,
        difficulty=difficulty, bloom_level=bloom, count=count,
        language=d.get("language", "English"), grade=grade,
    )
    saved = []
    for q in questions:
        obj = Question(
            topic_id=topic_id, text=q.get("text", "")[:150],
            difficulty=q.get("difficulty", difficulty),
            bloom_level=q.get("bloom_level", bloom),
            correct_hint=q.get("correct_hint", "")[:50],
            generated_by="llm",
        )
        session.add(obj)
        session.commit()
        session.refresh(obj)
        saved.append({"id": obj.id, "text": obj.text, "difficulty": obj.difficulty,
                       "bloom_level": obj.bloom_level, "correct_hint": obj.correct_hint})
    return saved


# ═══════════════════════════════════════════════════════
# ALERTS
# ═══════════════════════════════════════════════════════

@app.get("/api/alerts")
async def list_alerts(
    severity: str | None = None,
    dismissed: bool = False,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    stmt = select(Alert).where(Alert.dismissed == dismissed)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    alerts = session.exec(stmt.order_by(col(Alert.created_at).desc())).all()
    return [
        {
            "id": a.id, "student_phone": a.student_phone,
            "student_name": a.student.name if a.student else "?",
            "type": a.alert_type, "severity": a.severity,
            "message": a.message, "dismissed": a.dismissed,
            "created": a.created_at.isoformat(),
        }
        for a in alerts
    ]


@app.post("/api/alerts/{alert_id}/nudge")
async def nudge_student(alert_id: int, session: Session = Depends(get_session), instructor: Instructor = Depends(require_instructor)):
    alert = session.get(Alert, alert_id)
    if not alert:
        return JSONResponse({"error": "Alert not found."}, status_code=404)
    student = session.get(Student, alert.student_phone)
    if student:
        send_nudge(student.phone_number, student.name)
    alert.dismissed = True
    session.add(alert)
    session.commit()
    return {"nudged": alert.student_phone}


@app.post("/api/alerts/{alert_id}/dismiss")
async def dismiss_alert(alert_id: int, session: Session = Depends(get_session), instructor: Instructor = Depends(require_instructor)):
    alert = session.get(Alert, alert_id)
    if not alert:
        return JSONResponse({"error": "Alert not found."}, status_code=404)
    alert.dismissed = True
    session.add(alert)
    session.commit()
    return {"dismissed": alert_id}


# ═══════════════════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════════════════

@app.get("/api/stats")
async def get_stats(session: Session = Depends(get_session), instructor: Instructor = Depends(require_instructor)):
    students = session.exec(select(Student)).all()
    topics = session.exec(select(Topic)).all()
    assignments = session.exec(select(Assignment)).all()
    graded = [a for a in assignments if a.status == "graded"]
    alerts = session.exec(select(Alert).where(Alert.dismissed == False)).all()

    avg_score = sum(a.result.score for a in graded if a.result) / len(graded) if graded else 0
    response_rate = sum(1 for a in assignments if a.response_text) / len(assignments) if assignments else 0

    return {
        "total_students": len(students),
        "total_topics": len(topics),
        "total_assignments": len(assignments),
        "total_graded": len(graded),
        "avg_score": round(avg_score, 2),
        "response_rate": round(response_rate, 2),
        "active_alerts": len(alerts),
        "students_by_state": {
            state: sum(1 for s in students if s.state == state)
            for state in set(s.state for s in students)
        },
    }


@app.get("/api/stats/trends")
async def get_stats_trends(
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    """30-day time-series data for charts."""
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)

    # Get all assessment results from the last 30 days
    results = session.exec(
        select(AssessmentResult, Assignment)
        .join(Assignment, AssessmentResult.assignment_id == Assignment.id)
        .where(AssessmentResult.graded_at >= datetime(thirty_days_ago.year, thirty_days_ago.month, thirty_days_ago.day, tzinfo=timezone.utc))
    ).all()

    # Group by date
    from collections import defaultdict
    daily_scores: dict[str, list[float]] = defaultdict(list)
    daily_graded: dict[str, int] = defaultdict(int)
    for ar, asgn in results:
        day_str = ar.graded_at.strftime("%Y-%m-%d") if ar.graded_at else ""
        if day_str:
            daily_scores[day_str].append(ar.score)
            daily_graded[day_str] += 1

    # Get all assignments for daily_sent
    all_assignments = session.exec(
        select(Assignment).where(
            Assignment.created_at >= datetime(thirty_days_ago.year, thirty_days_ago.month, thirty_days_ago.day, tzinfo=timezone.utc)
        )
    ).all()
    daily_sent: dict[str, int] = defaultdict(int)
    for a in all_assignments:
        day_str = a.created_at.strftime("%Y-%m-%d") if a.created_at else ""
        if day_str:
            daily_sent[day_str] += 1

    # Active students per day (based on last_interaction)
    students = session.exec(select(Student)).all()
    daily_active: dict[str, int] = defaultdict(int)
    for st in students:
        if st.last_interaction:
            day_str = st.last_interaction.strftime("%Y-%m-%d")
            if day_str >= thirty_days_ago.isoformat():
                daily_active[day_str] += 1

    # Build sorted arrays for all 30 days
    all_dates = [(thirty_days_ago + timedelta(days=i)).isoformat() for i in range(31)]

    return {
        "daily_scores": [
            {"date": d, "avg_score": round(sum(daily_scores[d]) / len(daily_scores[d]), 2) if daily_scores[d] else None, "count": len(daily_scores[d])}
            for d in all_dates
        ],
        "daily_active": [
            {"date": d, "active_students": daily_active.get(d, 0)}
            for d in all_dates
        ],
        "daily_assignments": [
            {"date": d, "sent": daily_sent.get(d, 0), "graded": daily_graded.get(d, 0)}
            for d in all_dates
        ],
    }


@app.get("/api/stats/analytics")
async def get_stats_analytics(
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    """Detailed analytical breakdowns for charts."""
    students = session.exec(select(Student)).all()
    topics = session.exec(select(Topic)).all()

    # Aptitude distribution
    aptitude_dist = {}
    for s in students:
        aptitude_dist[s.aptitude_level] = aptitude_dist.get(s.aptitude_level, 0) + 1

    # State distribution
    state_dist = {}
    for s in students:
        state_dist[s.state] = state_dist.get(s.state, 0) + 1

    # Topic performance
    topic_perf = []
    for t in topics:
        t_assignments = session.exec(
            select(Assignment).where(
                Assignment.question_id.in_(
                    select(Question.id).where(Question.topic_id == t.id)
                )
            )
        ).all()
        graded = [a for a in t_assignments if a.status == "graded" and a.result]
        avg = sum(a.result.score for a in graded) / len(graded) if graded else 0
        topic_perf.append({
            "topic": t.title,
            "subject": t.subject,
            "avg_score": round(avg, 2),
            "total": len(t_assignments),
            "graded": len(graded),
        })

    # Bloom level distribution
    all_results = session.exec(select(AssessmentResult)).all()
    bloom_dist = {}
    for r in all_results:
        bloom_dist[r.bloom_level_achieved] = bloom_dist.get(r.bloom_level_achieved, 0) + 1

    # Top improvement areas
    from collections import Counter
    area_counter = Counter()
    for r in all_results:
        if r.improvement_areas and r.improvement_areas not in ("none", "unknown", ""):
            area_counter[r.improvement_areas] += 1
    top_areas = [{"area": a, "count": c} for a, c in area_counter.most_common(10)]

    # Response time average
    assignments_with_response = session.exec(
        select(Assignment).where(
            Assignment.sent_at.isnot(None),
            Assignment.responded_at.isnot(None),
        )
    ).all()
    if assignments_with_response:
        total_mins = sum(
            (a.responded_at - a.sent_at).total_seconds() / 60
            for a in assignments_with_response
        )
        avg_response_mins = total_mins / len(assignments_with_response)
    else:
        avg_response_mins = 0

    # Engagement rate
    active_count = sum(1 for s in students if s.state in ("active", "aptitude_test"))
    engagement_rate = active_count / len(students) if students else 0

    return {
        "aptitude_distribution": aptitude_dist,
        "state_distribution": state_dist,
        "topic_performance": topic_perf,
        "bloom_distribution": bloom_dist,
        "top_improvement_areas": top_areas,
        "response_time_avg_minutes": round(avg_response_mins, 1),
        "engagement_rate": round(engagement_rate, 2),
    }


@app.get("/api/stats/student/{phone}/trends")
async def get_student_trends(
    phone: str,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    """Per-student time-series and topic breakdown."""
    student = session.get(Student, phone)
    if not student:
        return JSONResponse({"error": "Student not found."}, status_code=404)

    # Score history over time
    results = session.exec(
        select(AssessmentResult, Assignment)
        .join(Assignment, AssessmentResult.assignment_id == Assignment.id)
        .where(Assignment.student_phone == phone)
        .order_by(AssessmentResult.graded_at)
    ).all()

    score_history = []
    for ar, asgn in results:
        question = session.get(Question, asgn.question_id) if asgn.question_id else None
        topic_name = ""
        if question and question.topic_id:
            topic = session.get(Topic, question.topic_id)
            topic_name = topic.title if topic else ""
        score_history.append({
            "date": ar.graded_at.isoformat() if ar.graded_at else "",
            "score": ar.score,
            "topic": topic_name,
        })

    # Topic breakdown
    progress_records = session.exec(
        select(StudentProgress).where(StudentProgress.student_phone == phone)
    ).all()
    topic_breakdown = []
    for p in progress_records:
        topic = session.get(Topic, p.topic_id)
        accuracy = p.questions_correct / p.questions_attempted if p.questions_attempted > 0 else 0
        topic_breakdown.append({
            "topic": topic.title if topic else f"Topic {p.topic_id}",
            "attempted": p.questions_attempted,
            "correct": p.questions_correct,
            "accuracy": round(accuracy, 2),
            "difficulty": p.current_difficulty,
        })

    return {
        "score_history": score_history,
        "topic_breakdown": topic_breakdown,
    }


# ── LLM-Powered Insights (cached) ────────────────────

_insights_cache: dict = {"data": None, "generated_at": None}


@app.get("/api/stats/insights")
async def get_class_insights(
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    """LLM-powered class analytics insights. Cached for 30 minutes."""
    now = datetime.now(timezone.utc)

    # Return cache if fresh (< 30 min old)
    if _insights_cache["data"] and _insights_cache["generated_at"]:
        age = (now - _insights_cache["generated_at"]).total_seconds()
        if age < 1800:
            return {**_insights_cache["data"], "generated_at": _insights_cache["generated_at"].isoformat(), "cached": True}

    # Gather stats for LLM analysis
    students = session.exec(select(Student)).all()
    all_results = session.exec(select(AssessmentResult)).all()
    recent_results = []
    for r in all_results:
        if r.graded_at:
            graded = r.graded_at if r.graded_at.tzinfo else r.graded_at.replace(tzinfo=timezone.utc)
            if (now - graded).days <= 7:
                recent_results.append(r)

    avg_score_all = sum(r.score for r in all_results) / len(all_results) if all_results else 0
    avg_score_week = sum(r.score for r in recent_results) / len(recent_results) if recent_results else 0

    # Find at-risk students
    at_risk_info = []
    for st in students:
        if st.state == "idle":
            at_risk_info.append(f"{st.name} ({st.grade}) - inactive/idle")

    # Per-student score aggregation
    student_scores = {}
    for r in all_results:
        asgn = session.get(Assignment, r.assignment_id)
        if asgn:
            student_scores.setdefault(asgn.student_phone, []).append(r.score)

    for phone, scores in student_scores.items():
        if len(scores) >= 3 and all(s < 0.3 for s in scores[-3:]):
            st = session.get(Student, phone)
            if st:
                at_risk_info.append(f"{st.name} ({st.grade}) - 3+ consecutive low scores")

    # Common weak areas
    from collections import Counter
    area_counter = Counter()
    for r in all_results:
        if r.improvement_areas and r.improvement_areas not in ("none", "unknown", ""):
            area_counter[r.improvement_areas] += 1

    stats_for_llm = {
        "total_students": len(students),
        "total_assessments": len(all_results),
        "avg_score_overall": round(avg_score_all, 2),
        "avg_score_this_week": round(avg_score_week, 2),
        "assessments_this_week": len(recent_results),
        "students_by_state": {s.state: 0 for s in students},
        "at_risk_students": at_risk_info[:5],
        "common_weak_areas": [{"area": a, "count": c} for a, c in area_counter.most_common(5)],
        "aptitude_distribution": {},
    }
    for s in students:
        stats_for_llm["students_by_state"][s.state] = stats_for_llm["students_by_state"].get(s.state, 0) + 1
        stats_for_llm["aptitude_distribution"][s.aptitude_level] = stats_for_llm["aptitude_distribution"].get(s.aptitude_level, 0) + 1

    insights = generate_class_insights(stats_for_llm)
    insights["generated_at"] = now.isoformat()
    insights["cached"] = False

    _insights_cache["data"] = insights
    _insights_cache["generated_at"] = now

    return insights


# ═══════════════════════════════════════════════════════
# SMS WEBHOOK — Student's only channel
# ═══════════════════════════════════════════════════════

def _start_aptitude(phone: str):
    """Send welcome SMS and first aptitude question."""
    with Session(engine) as s:
        student = s.get(Student, phone)
        if not student:
            return
        # Determine subject from active topic or default
        subject = "General"
        if student.active_topic_id:
            topic = s.get(Topic, student.active_topic_id)
            if topic:
                subject = topic.subject
        welcome = f"Welcome {student.name}! Quick test to find your level. "
        result = generate_aptitude_question(
            grade=student.grade, step=0,
            language=student.preferred_language,
            subject=subject,
        )
        q_text = result["question"]
        q_answer = result["correct_answer"]
        msg = (welcome + q_text)[:155]
        send_sms(to=phone, message=msg)
        student.state = "aptitude_test"
        student.aptitude_step = 0
        # Store question and correct answer together
        student.aptitude_current_q = f"Q:{q_text}|A:{q_answer}" if q_answer else q_text
        s.add(student)
        s.commit()


def _process_sms(phone: str, text: str, msg_id: str | None):
    """Background worker: full SMS conversation state machine."""
    import traceback
    print(f"[SMS] >>> Incoming from {phone}: {text!r}")
    try:
        _process_sms_inner(phone, text, msg_id)
    except Exception as e:
        print(f"[SMS] !!! UNHANDLED ERROR processing {phone}: {e}")
        traceback.print_exc()


def _process_sms_inner(phone: str, text: str, msg_id: str | None):
    """Inner SMS processing logic."""
    with Session(engine) as s:
        # Idempotency
        if msg_id:
            if s.get(ProcessedMessage, msg_id):
                return
            s.add(ProcessedMessage(message_id=msg_id))
            s.commit()

        # Get student
        student = s.get(Student, phone)
        if student is None:
            print(f"[SMS] Student not found for {phone} — sending registration prompt")
            # Unknown number — send info message
            send_sms(to=phone, message="Hi! Ask your instructor to register you for SMS tutoring.")
            return

        # Rate limit
        if not _check_limit(student, s):
            send_sms(to=phone, message="Daily limit reached (10 msgs). Try again tomorrow!")
            return

        txt = text.strip()
        txt_upper = txt.upper()
        print(f"[SMS] Student found: {student.name}, state={student.state}, phone={student.phone_number}")

        # ── State: registered (shouldn't receive SMS yet, but handle gracefully)
        if student.state == "registered":
            _start_aptitude(phone)
            _inc_usage(student, s)
            return

        # ── State: aptitude_test ──
        if student.state == "aptitude_test":
            print(f"[SMS] State=aptitude_test, step={student.aptitude_step}, stored_q={student.aptitude_current_q!r}")
            step = student.aptitude_step

            # Parse stored question and correct answer
            stored = student.aptitude_current_q or ""
            if stored.startswith("Q:") and "|A:" in stored:
                q_text = stored.split("|A:")[0][2:]
                q_answer = stored.split("|A:")[1]
            else:
                q_text = stored
                q_answer = ""

            # Grade using the actual question text and correct answer
            print(f"[SMS] Grading aptitude answer: q={q_text!r}, answer={txt!r}, hint={q_answer!r}")
            result = grade_answer(
                question_text=q_text or f"Aptitude Q{step + 1} for {student.grade}",
                student_answer=txt,
                correct_hint=q_answer or "evaluate correctness based on the question",
                difficulty="beginner" if step < 2 else "intermediate",
                language=student.preferred_language,
                grade=student.grade,
            )

            if result["correct"]:
                student.aptitude_correct += 1

            print(f"[SMS] Grade result: score={result['score']}, correct={result['correct']}, feedback={result['feedback']!r}")

            student.aptitude_step = step + 1
            s.add(student)
            s.commit()

            # Check if test is complete (5 questions)
            if student.aptitude_step >= 5:
                score = student.aptitude_correct / 5.0
                student.aptitude_score = score
                if score >= 0.7:
                    student.aptitude_level = "advanced"
                elif score >= 0.4:
                    student.aptitude_level = "intermediate"
                else:
                    student.aptitude_level = "beginner"
                cluster_name = f"{student.grade}-{student.aptitude_level}"
                student.cluster_id = cluster_name
                student.state = "active"
                student.aptitude_current_q = None
                s.add(student)
                s.commit()

                # Ensure Cluster record exists and add membership
                auto_cluster = s.exec(
                    select(Cluster).where(Cluster.name == cluster_name, Cluster.is_custom == False)
                ).first()
                if not auto_cluster:
                    auto_cluster = Cluster(
                        name=cluster_name, is_custom=False, grade_level=student.grade,
                        description=f"Auto: {student.grade} students at {student.aptitude_level} level",
                    )
                    s.add(auto_cluster)
                    s.commit()
                    s.refresh(auto_cluster)
                existing_membership = s.exec(
                    select(ClusterMembership).where(
                        ClusterMembership.cluster_id == auto_cluster.id,
                        ClusterMembership.student_phone == phone,
                    )
                ).first()
                if not existing_membership:
                    s.add(ClusterMembership(cluster_id=auto_cluster.id, student_phone=phone))
                    s.commit()

                msg = f"Test done! Score: {student.aptitude_correct}/5. Level: {student.aptitude_level}. Send MENU to pick a subject."
                send_sms(to=phone, message=msg)
                _inc_usage(student, s)
                return

            # Send next aptitude question and store it
            next_result = generate_aptitude_question(
                grade=student.grade,
                step=student.aptitude_step,
                language=student.preferred_language,
            )
            q_text = next_result["question"]
            q_answer = next_result["correct_answer"]
            student.aptitude_current_q = f"Q:{q_text}|A:{q_answer}" if q_answer else q_text
            s.add(student)
            s.commit()
            feedback = result["feedback"][:60] + " " if result["feedback"] else ""
            msg = (feedback + q_text)[:155]
            send_sms(to=phone, message=msg)
            _inc_usage(student, s)
            return

        # ── State: active / idle ──
        if student.state in ("active", "idle"):
            # Reactivate idle students
            if student.state == "idle":
                student.state = "active"
                s.add(student)
                s.commit()

            # MENU command
            if txt_upper in ("MENU", "STOP", "TOPICS"):
                topics = s.exec(select(Topic)).all()
                menu = "Pick a subject:\n"
                for i, t in enumerate(topics, 1):
                    menu += f"{i}. {t.title}\n"
                menu += "Reply with the number."
                send_sms(to=phone, message=menu)
                student.active_topic_id = None
                s.add(student)
                _inc_usage(student, s)
                return

            # HELP command
            if txt_upper == "HELP":
                send_sms(
                    to=phone,
                    message="Commands: MENU=pick subject, HELP=this msg. Reply number to choose topic. Text answers to questions.",
                )
                _inc_usage(student, s)
                return

            # Check if this is a response to an assigned question
            pending_assignment = s.exec(
                select(Assignment).where(
                    Assignment.student_phone == phone,
                    Assignment.status == "sent",
                ).order_by(Assignment.sent_at.desc())
            ).first()

            if pending_assignment:
                question = s.get(Question, pending_assignment.question_id)
                if question:
                    # Grade the answer
                    result = grade_answer(
                        question_text=question.text,
                        student_answer=txt,
                        correct_hint=question.correct_hint,
                        difficulty=question.difficulty,
                        language=student.preferred_language,
                        grade=student.grade,
                    )
                    # Store result
                    pending_assignment.response_text = txt
                    pending_assignment.responded_at = datetime.now(timezone.utc)
                    pending_assignment.status = "graded"
                    s.add(pending_assignment)

                    assessment = AssessmentResult(
                        assignment_id=pending_assignment.id,
                        score=result["score"],
                        correct=result["correct"],
                        feedback=result["feedback"],
                        improvement_areas=result.get("improvement_area", ""),
                        bloom_level_achieved=question.bloom_level,
                    )
                    s.add(assessment)

                    # Update progress
                    prog = s.exec(
                        select(StudentProgress).where(
                            StudentProgress.student_phone == phone,
                            StudentProgress.topic_id == question.topic_id,
                        )
                    ).first()
                    if not prog:
                        prog = StudentProgress(student_phone=phone, topic_id=question.topic_id)
                        s.add(prog)
                        s.commit()
                        s.refresh(prog)

                    prog.questions_attempted += 1
                    if result["correct"]:
                        prog.questions_correct += 1
                    prog.last_active = datetime.now(timezone.utc)
                    s.add(prog)
                    s.commit()

                    # Send feedback via SMS
                    fb = result["feedback"] or "Answer received."
                    send_sms(to=phone, message=fb)
                    _inc_usage(student, s)

                    # Send improvement suggestion if student is struggling
                    if not result["correct"] and prog.questions_attempted >= 3:
                        recent_results = s.exec(
                            select(AssessmentResult)
                            .join(Assignment)
                            .where(Assignment.student_phone == phone)
                            .order_by(col(AssessmentResult.graded_at).desc())
                        ).all()
                        weak_areas = [
                            r.improvement_areas for r in recent_results[:5]
                            if r.improvement_areas and r.improvement_areas != "none"
                        ]
                        if weak_areas:
                            suggestion = suggest_improvements(
                                weak_areas=weak_areas,
                                grade=student.grade,
                                language=student.preferred_language,
                            )
                            send_sms(to=phone, message=suggestion)
                    return

            # Topic selection (numeric input when no active topic)
            if txt_upper.isdigit() and not student.active_topic_id:
                topics = s.exec(select(Topic)).all()
                idx = int(txt_upper) - 1
                if 0 <= idx < len(topics):
                    chosen = topics[idx]
                    student.active_topic_id = chosen.id
                    s.add(student)
                    s.commit()

                    # Get or create progress
                    prog = s.exec(
                        select(StudentProgress).where(
                            StudentProgress.student_phone == phone,
                            StudentProgress.topic_id == chosen.id,
                        )
                    ).first()
                    if not prog:
                        prog = StudentProgress(student_phone=phone, topic_id=chosen.id)
                        s.add(prog)
                        s.commit()
                        s.refresh(prog)

                    # LLM generates first question
                    llm_result = generate_sms_reply(
                        student_message=f"I want to learn {chosen.title}.",
                        history_summary=prog.history_summary,
                        current_step=prog.questions_attempted,
                        topic_title=chosen.title,
                        topic_description=chosen.description,
                        difficulty=prog.current_difficulty,
                        language=student.preferred_language,
                        grade=student.grade,
                    )
                    reply = llm_result["reply"]
                    prog.history_summary = summarize_history(prog.history_summary, "START", reply)
                    prog.last_active = datetime.now(timezone.utc)
                    s.add(prog)
                    send_sms(to=phone, message=reply)
                    _inc_usage(student, s)
                    s.commit()
                    return
                else:
                    send_sms(to=phone, message="Invalid choice. Send MENU to see topics.")
                    _inc_usage(student, s)
                    return

            # Free-form tutoring (active topic)
            if student.active_topic_id:
                topic = s.get(Topic, student.active_topic_id)
                if not topic:
                    student.active_topic_id = None
                    s.add(student)
                    s.commit()
                    send_sms(to=phone, message="Topic not found. Send MENU to see topics.")
                    return

                prog = s.exec(
                    select(StudentProgress).where(
                        StudentProgress.student_phone == phone,
                        StudentProgress.topic_id == topic.id,
                    )
                ).first()
                if not prog:
                    prog = StudentProgress(student_phone=phone, topic_id=topic.id)
                    s.add(prog)
                    s.commit()
                    s.refresh(prog)

                llm_result = generate_sms_reply(
                    student_message=txt,
                    history_summary=prog.history_summary,
                    current_step=prog.questions_attempted,
                    topic_title=topic.title,
                    topic_description=topic.description,
                    difficulty=prog.current_difficulty,
                    language=student.preferred_language,
                    grade=student.grade,
                )
                reply = llm_result["reply"]
                is_answer = llm_result.get("is_answer", False)
                score = llm_result.get("score")

                prog.history_summary = summarize_history(prog.history_summary, txt, reply)
                prog.last_active = datetime.now(timezone.utc)

                # Only count and grade actual answers (not greetings or off-topic)
                if is_answer and score is not None:
                    prog.questions_attempted += 1
                    correct = score >= 0.5
                    if correct:
                        prog.questions_correct += 1

                    # Create an AssessmentResult via a virtual assignment
                    # so free-form tutoring gets tracked in analytics
                    virtual_assignment = Assignment(
                        question_id=None,  # free-form tutoring — no stored question
                        student_phone=phone,
                        sent_at=datetime.now(timezone.utc),
                        delivered=True,
                        response_text=txt,
                        responded_at=datetime.now(timezone.utc),
                        status="graded",
                    )
                    s.add(virtual_assignment)
                    s.commit()
                    s.refresh(virtual_assignment)

                    assessment = AssessmentResult(
                        assignment_id=virtual_assignment.id,
                        score=score,
                        correct=correct,
                        feedback=reply[:100],
                        improvement_areas="none" if correct else "practice needed",
                        bloom_level_achieved="understand" if correct else "remember",
                    )
                    s.add(assessment)

                    # Adaptive difficulty: check after every 5 graded answers
                    if prog.questions_attempted > 0 and prog.questions_attempted % 5 == 0:
                        recent_count = min(prog.questions_attempted, 5)
                        if recent_count > 0:
                            accuracy = prog.questions_correct / prog.questions_attempted
                            old_diff = prog.current_difficulty
                            if accuracy >= 0.8 and old_diff != "advanced":
                                prog.current_difficulty = "intermediate" if old_diff == "beginner" else "advanced"
                            elif accuracy <= 0.3 and old_diff != "beginner":
                                prog.current_difficulty = "intermediate" if old_diff == "advanced" else "beginner"

                s.add(prog)
                send_sms(to=phone, message=reply)
                _inc_usage(student, s)
                s.commit()
                return

            # No active topic — show menu
            topics = s.exec(select(Topic)).all()
            if topics:
                menu = "Pick a subject:\n"
                for i, t in enumerate(topics, 1):
                    menu += f"{i}. {t.title}\n"
                menu += "Reply with the number."
                send_sms(to=phone, message=menu[:155])
            else:
                send_sms(to=phone, message="No topics available yet. Check back later!")
            _inc_usage(student, s)

    print(f"[SMS] Processed from {phone}")


@app.post("/webhook", status_code=200)
async def incoming_sms(
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(default=None),
    To: str = Form(default=None),
    NumMedia: str = Form(default=None),
):
    background_tasks.add_task(_process_sms, From, Body, MessageSid)
    # Twilio expects TwiML XML response
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )


# ═══════════════════════════════════════════════════════
# SMS SIMULATOR
# ═══════════════════════════════════════════════════════

@app.post("/api/simulate-sms")
async def simulate_sms(
    request: Request,
    session: Session = Depends(get_session),
    instructor: Instructor = Depends(require_instructor),
):
    """Simulate an incoming SMS and return all outgoing replies."""
    d = await request.json()
    phone = d.get("phone_number", "").strip()
    text = d.get("message", "").strip()

    if not phone or not text:
        return JSONResponse({"error": "Phone and message are required."}, status_code=400)

    set_capture_mode(True)
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _process_sms, phone, text, None)
        replies = get_captured_messages()
    finally:
        set_capture_mode(False)

    # Return current student state for the UI
    student = session.get(Student, phone)
    return {
        "replies": replies,
        "student_state": student.state if student else "unknown",
        "student_name": student.name if student else None,
        "aptitude_level": student.aptitude_level if student else None,
    }


@app.get("/health")
async def health():
    return {"service": "Somo", "status": "running"}
