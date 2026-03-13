"""
seed_demo.py – Generate realistic demo data for Somo.

All demo data is clearly marked with [Demo] prefix on student names
and uses fake +2547000001XX phone numbers to avoid confusion with
real students.

Called from main.py _seed_defaults() when the database is fresh.
"""

import random
from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session

from models import (
    Student, Topic, Question, Assignment, AssessmentResult,
    StudentProgress, Alert, Cluster, ClusterMembership,
)


# ── Demo student definitions ─────────────────────────

DEMO_STUDENTS = [
    # Pre-Primary
    {"name": "[Demo] Aisha M.",     "grade": "PP1",       "aptitude": "beginner",     "state": "active"},
    {"name": "[Demo] Brian T.",     "grade": "PP2",       "aptitude": "beginner",     "state": "active"},
    # Lower Primary
    {"name": "[Demo] Cynthia W.",   "grade": "Grade 1",   "aptitude": "beginner",     "state": "active"},
    {"name": "[Demo] David O.",     "grade": "Grade 2",   "aptitude": "intermediate", "state": "active"},
    {"name": "[Demo] Esther N.",    "grade": "Grade 3",   "aptitude": "intermediate", "state": "active"},
    # Upper Primary
    {"name": "[Demo] Felix A.",     "grade": "Grade 4",   "aptitude": "intermediate", "state": "idle"},
    {"name": "[Demo] Grace M.",     "grade": "Grade 5",   "aptitude": "beginner",     "state": "active"},
    {"name": "[Demo] Hassan J.",    "grade": "Grade 5",   "aptitude": "advanced",     "state": "active"},
    {"name": "[Demo] Irene P.",     "grade": "Grade 6",   "aptitude": "intermediate", "state": "active"},
    # Junior Secondary
    {"name": "[Demo] James K.",     "grade": "Grade 7",   "aptitude": "advanced",     "state": "active"},
    {"name": "[Demo] Karen L.",     "grade": "Grade 8",   "aptitude": "intermediate", "state": "idle"},
    {"name": "[Demo] Liam T.",      "grade": "Grade 8",   "aptitude": "intermediate", "state": "active"},
    {"name": "[Demo] Mary W.",      "grade": "Grade 9",   "aptitude": "beginner",     "state": "active"},
    # Senior Secondary
    {"name": "[Demo] Nathan R.",    "grade": "Grade 10",  "aptitude": "advanced",     "state": "active"},
    {"name": "[Demo] Olive S.",     "grade": "Grade 10",  "aptitude": "intermediate", "state": "active"},
    {"name": "[Demo] Peter G.",     "grade": "Grade 11",  "aptitude": "advanced",     "state": "active"},
    {"name": "[Demo] Ruth D.",      "grade": "Grade 12",  "aptitude": "intermediate", "state": "aptitude_test"},
    {"name": "[Demo] Samuel B.",    "grade": "Grade 4",   "aptitude": "untested",     "state": "registered"},
]

# ── Demo topic definitions ────────────────────────────

DEMO_TOPICS = [
    {"title": "Fractions & Decimals", "subject": "Mathematics", "difficulty": "intermediate",
     "description": "Understanding, comparing, adding, and subtracting fractions and decimals. Converting between forms."},
    {"title": "Reading Comprehension", "subject": "English", "difficulty": "intermediate",
     "description": "Understanding passages, identifying main ideas, drawing inferences, and vocabulary in context."},
    {"title": "Basic Science", "subject": "Science & Technology", "difficulty": "beginner",
     "description": "States of matter, living things, weather, simple machines, and the human body basics. (Upper Primary)"},
    {"title": "Kenya Geography", "subject": "Social Studies", "difficulty": "beginner",
     "description": "Counties of Kenya, physical features, economic activities, maps, and climate zones."},
    {"title": "Algebra Fundamentals", "subject": "Mathematics", "difficulty": "advanced",
     "description": "Variables, expressions, simple equations, inequalities, and linear graphs. (Junior/Senior Secondary)"},
    {"title": "Creative Writing", "subject": "English", "difficulty": "advanced",
     "description": "Narrative writing, descriptive language, story structure, dialogue, and character development."},
    {"title": "Kiswahili Msingi", "subject": "Kiswahili", "difficulty": "beginner",
     "description": "Herufi, silabi, maneno rahisi, sentensi fupi, salamu, na msamiati wa msingi."},
    {"title": "Integrated Science", "subject": "Integrated Science", "difficulty": "intermediate",
     "description": "Atoms, elements, forces, energy, cells, genetics, and ecology. (Junior Secondary)"},
]

# ── Question templates per topic ──────────────────────

DEMO_QUESTIONS = {
    "Basic Math": [
        {"text": "What is 7 + 8?", "hint": "15", "bloom": "remember", "diff": "beginner"},
        {"text": "What is 15 - 9?", "hint": "6", "bloom": "remember", "diff": "beginner"},
        {"text": "What is 6 x 4?", "hint": "24", "bloom": "remember", "diff": "beginner"},
        {"text": "A box has 12 apples. You eat 5. How many are left?", "hint": "7", "bloom": "understand", "diff": "beginner"},
        {"text": "What is 48 divided by 6?", "hint": "8", "bloom": "understand", "diff": "beginner"},
        {"text": "Round 67 to the nearest ten.", "hint": "70", "bloom": "apply", "diff": "beginner"},
    ],
    "English Grammar": [
        {"text": "Fill in: She ___ to school every day. (go)", "hint": "goes", "bloom": "remember", "diff": "beginner"},
        {"text": "What is the plural of child?", "hint": "children", "bloom": "remember", "diff": "beginner"},
        {"text": "Choose the correct word: Their/There/They're going home.", "hint": "They're", "bloom": "understand", "diff": "beginner"},
        {"text": "What type of word is 'quickly'? (noun, verb, adjective, adverb)", "hint": "adverb", "bloom": "understand", "diff": "beginner"},
        {"text": "Rewrite in past tense: I walk to the park.", "hint": "I walked to the park", "bloom": "apply", "diff": "beginner"},
        {"text": "Add a comma: After dinner we played outside.", "hint": "After dinner, we played", "bloom": "apply", "diff": "beginner"},
    ],
    "Fractions & Decimals": [
        {"text": "What is 1/2 + 1/4?", "hint": "3/4", "bloom": "remember", "diff": "intermediate"},
        {"text": "Convert 0.75 to a fraction.", "hint": "3/4", "bloom": "understand", "diff": "intermediate"},
        {"text": "Which is larger: 2/3 or 3/5?", "hint": "2/3", "bloom": "understand", "diff": "intermediate"},
        {"text": "What is 3/8 as a decimal?", "hint": "0.375", "bloom": "apply", "diff": "intermediate"},
        {"text": "Simplify 12/18.", "hint": "2/3", "bloom": "apply", "diff": "intermediate"},
        {"text": "What is 2.5 x 0.4?", "hint": "1.0", "bloom": "apply", "diff": "intermediate"},
    ],
    "Reading Comprehension": [
        {"text": "What is the main idea of a paragraph?", "hint": "central point or message", "bloom": "remember", "diff": "intermediate"},
        {"text": "What does 'infer' mean in reading?", "hint": "draw a conclusion from clues", "bloom": "understand", "diff": "intermediate"},
        {"text": "Name one type of context clue.", "hint": "definition, synonym, example", "bloom": "remember", "diff": "intermediate"},
        {"text": "What is a theme in a story?", "hint": "central message or lesson", "bloom": "understand", "diff": "intermediate"},
        {"text": "What is the difference between fact and opinion?", "hint": "fact is provable, opinion is belief", "bloom": "analyze", "diff": "intermediate"},
    ],
    "Basic Science": [
        {"text": "Name the three states of matter.", "hint": "solid, liquid, gas", "bloom": "remember", "diff": "beginner"},
        {"text": "What do plants need to make food?", "hint": "sunlight, water, carbon dioxide", "bloom": "remember", "diff": "beginner"},
        {"text": "What organ pumps blood in your body?", "hint": "heart", "bloom": "remember", "diff": "beginner"},
        {"text": "Why does ice float on water?", "hint": "ice is less dense than water", "bloom": "understand", "diff": "beginner"},
        {"text": "Name one simple machine.", "hint": "lever, pulley, wheel, inclined plane", "bloom": "remember", "diff": "beginner"},
        {"text": "What causes day and night?", "hint": "Earth's rotation", "bloom": "understand", "diff": "beginner"},
    ],
    "Kenya Geography": [
        {"text": "How many counties does Kenya have?", "hint": "47", "bloom": "remember", "diff": "beginner"},
        {"text": "What is the capital city of Kenya?", "hint": "Nairobi", "bloom": "remember", "diff": "beginner"},
        {"text": "What is the highest mountain in Kenya?", "hint": "Mt. Kenya", "bloom": "remember", "diff": "beginner"},
        {"text": "Name the two main rivers in Kenya.", "hint": "Tana and Athi", "bloom": "remember", "diff": "beginner"},
        {"text": "Which lake borders Kenya to the west?", "hint": "Lake Victoria", "bloom": "understand", "diff": "beginner"},
    ],
    "Algebra Fundamentals": [
        {"text": "Solve: x + 5 = 12", "hint": "x = 7", "bloom": "apply", "diff": "advanced"},
        {"text": "Simplify: 3x + 2x", "hint": "5x", "bloom": "understand", "diff": "advanced"},
        {"text": "What is the value of y if 2y = 10?", "hint": "y = 5", "bloom": "apply", "diff": "advanced"},
        {"text": "Write an expression: 5 more than a number n.", "hint": "n + 5", "bloom": "understand", "diff": "advanced"},
        {"text": "Solve: 3(x - 2) = 9", "hint": "x = 5", "bloom": "apply", "diff": "advanced"},
        {"text": "What is the slope of y = 2x + 3?", "hint": "2", "bloom": "analyze", "diff": "advanced"},
    ],
    "Creative Writing": [
        {"text": "What are the 5 elements of a story?", "hint": "character, setting, plot, conflict, resolution", "bloom": "remember", "diff": "advanced"},
        {"text": "Give an example of a simile.", "hint": "comparison using like or as", "bloom": "understand", "diff": "advanced"},
        {"text": "What is the purpose of dialogue in a story?", "hint": "reveal character, advance plot", "bloom": "understand", "diff": "advanced"},
        {"text": "What makes a good opening sentence?", "hint": "hooks the reader, creates curiosity", "bloom": "analyze", "diff": "advanced"},
        {"text": "What is 'show dont tell' in writing?", "hint": "use details instead of stating", "bloom": "apply", "diff": "advanced"},
    ],
    "Kiswahili Msingi": [
        {"text": "Tafsiri kwa Kiswahili: 'Good morning'", "hint": "Habari za asubuhi", "bloom": "remember", "diff": "beginner"},
        {"text": "Andika wingi wa 'mtoto'.", "hint": "watoto", "bloom": "remember", "diff": "beginner"},
        {"text": "Jaza pengo: Mama ___ chakula. (pika)", "hint": "anapika", "bloom": "apply", "diff": "beginner"},
        {"text": "Taja siku tatu za wiki.", "hint": "Jumatatu, Jumanne, Jumatano", "bloom": "remember", "diff": "beginner"},
        {"text": "Neno 'shule' linamaanisha nini kwa Kiingereza?", "hint": "school", "bloom": "understand", "diff": "beginner"},
    ],
    "Integrated Science": [
        {"text": "What is the smallest unit of an element?", "hint": "atom", "bloom": "remember", "diff": "intermediate"},
        {"text": "State Newton's first law of motion.", "hint": "an object at rest stays at rest unless acted on by a force", "bloom": "remember", "diff": "intermediate"},
        {"text": "What is the function of the cell membrane?", "hint": "controls what enters and leaves the cell", "bloom": "understand", "diff": "intermediate"},
        {"text": "Name two types of energy.", "hint": "kinetic and potential", "bloom": "remember", "diff": "intermediate"},
        {"text": "What is the difference between an element and a compound?", "hint": "element is one type of atom, compound has two or more", "bloom": "understand", "diff": "intermediate"},
        {"text": "What happens during photosynthesis?", "hint": "plants convert light energy to food (glucose)", "bloom": "understand", "diff": "intermediate"},
    ],
}

# ── Improvement area pools ────────────────────────────

IMPROVEMENT_AREAS = [
    "fractions", "decimals", "multiplication", "division", "algebra",
    "grammar", "spelling", "vocabulary", "comprehension", "writing",
    "problem solving", "calculation", "reading speed", "critical thinking",
    "word problems", "geometry", "measurement",
]

# ── Realistic student response texts ─────────────────

CORRECT_RESPONSES = [
    "15", "7", "children", "3/4", "heart", "47",
    "solid liquid gas", "Nairobi", "x = 7", "5x", "goes",
    "adverb", "Mt. Kenya", "2/3", "they're", "70",
    "watoto", "atom", "Habari za asubuhi",
]

WRONG_RESPONSES = [
    "I dont know", "maybe 12?", "is it 5?", "idk", "cat",
    "the answer is blue", "13", "not sure", "hmm", "help",
    "2/5", "noun", "Mombasa", "zero", "its", "60",
]


def seed_demo_data(session: Session, instructor_id: int):
    """Seed the database with realistic demo data for all dashboard features."""
    now = datetime.now(timezone.utc)
    today = date.today()
    random.seed(42)  # Reproducible data

    # ── Create demo topics ────────────────────────────
    topic_map = {}  # title -> Topic object

    # First, get existing seeded topics
    from sqlmodel import select
    existing_topics = session.exec(select(Topic)).all()
    for t in existing_topics:
        topic_map[t.title] = t

    for td in DEMO_TOPICS:
        if td["title"] not in topic_map:
            topic = Topic(
                title=td["title"],
                subject=td["subject"],
                difficulty=td["difficulty"],
                description=td["description"],
                instructor_id=instructor_id,
            )
            session.add(topic)
            session.commit()
            session.refresh(topic)
            topic_map[td["title"]] = topic

    # ── Create questions for all topics ───────────────
    question_map = {}  # topic_title -> [Question objects]
    for topic_title, q_list in DEMO_QUESTIONS.items():
        topic = topic_map.get(topic_title)
        if not topic:
            continue
        questions = []
        for qd in q_list:
            q = Question(
                topic_id=topic.id,
                text=qd["text"],
                difficulty=qd["diff"],
                bloom_level=qd["bloom"],
                correct_hint=qd["hint"],
                generated_by="llm",
            )
            session.add(q)
            session.commit()
            session.refresh(q)
            questions.append(q)
        question_map[topic_title] = questions

    # ── Create demo students ──────────────────────────
    students = []
    for i, sd in enumerate(DEMO_STUDENTS):
        phone = f"+254700000{100 + i}"
        aptitude_level = sd["aptitude"]
        aptitude_score = {
            "beginner": round(random.uniform(0.15, 0.39), 2),
            "intermediate": round(random.uniform(0.40, 0.69), 2),
            "advanced": round(random.uniform(0.70, 0.95), 2),
            "untested": None,
        }[aptitude_level]
        cluster_id = f"{sd['grade']}-{aptitude_level}" if aptitude_level != "untested" else None

        # Age based on CBC level
        grade_str = sd["grade"]
        if grade_str.startswith("PP"):
            age = random.randint(4, 6)
        elif grade_str in ("Grade 1", "Grade 2", "Grade 3"):
            age = random.randint(6, 9)
        elif grade_str in ("Grade 4", "Grade 5", "Grade 6"):
            age = random.randint(9, 12)
        elif grade_str in ("Grade 7", "Grade 8", "Grade 9"):
            age = random.randint(12, 15)
        else:  # Grade 10-12
            age = random.randint(15, 18)

        student = Student(
            phone_number=phone,
            name=sd["name"],
            age=age,
            grade=sd["grade"],
            preferred_language="English",
            aptitude_score=aptitude_score,
            aptitude_level=aptitude_level,
            cluster_id=cluster_id,
            state=sd["state"],
            aptitude_step=5 if aptitude_level != "untested" else 0,
            aptitude_correct=int((aptitude_score or 0) * 5),
            last_interaction=now - timedelta(hours=random.randint(1, 72)),
            created_at=now - timedelta(days=random.randint(15, 35)),
        )
        session.add(student)
        session.commit()
        session.refresh(student)
        students.append(student)

    # ── Generate assignments + assessment results ─────
    all_topics = list(topic_map.values())
    all_questions = []
    for qs in question_map.values():
        all_questions.extend(qs)

    if not all_questions:
        print("[SEED] No questions created, skipping assignments")
        return

    for student in students:
        if student.state in ("registered", "aptitude_test"):
            continue  # These students don't have assignments yet

        # Score distribution based on aptitude
        score_mean = {"beginner": 0.45, "intermediate": 0.65, "advanced": 0.82}.get(
            student.aptitude_level, 0.55
        )
        score_std = {"beginner": 0.20, "intermediate": 0.15, "advanced": 0.10}.get(
            student.aptitude_level, 0.18
        )

        # Each active student gets 10-20 assignments spread over 30 days
        num_assignments = random.randint(10, 20)
        # Pick 2-3 topics for this student
        student_topics = random.sample(all_topics, min(len(all_topics), random.randint(2, 3)))

        # Set an active topic
        student.active_topic_id = student_topics[0].id
        session.add(student)

        for j in range(num_assignments):
            topic = random.choice(student_topics)
            topic_questions = question_map.get(topic.title, [])
            if not topic_questions:
                topic_questions = all_questions
            question = random.choice(topic_questions)

            # Spread over 30 days
            days_ago = random.randint(0, 30)
            hours_ago = random.randint(0, 23)
            sent_time = now - timedelta(days=days_ago, hours=hours_ago)

            # Determine score
            raw_score = max(0.0, min(1.0, random.gauss(score_mean, score_std)))
            score = round(raw_score, 2)
            correct = score >= 0.5

            # Response time: 5 min to 24 hours
            response_delay = timedelta(minutes=random.randint(5, 1440))
            responded_time = sent_time + response_delay

            # Pick a realistic response
            response_text = random.choice(CORRECT_RESPONSES if correct else WRONG_RESPONSES)

            # Determine assignment status — mostly graded, some others
            status_roll = random.random()
            if status_roll < 0.80:
                status = "graded"
            elif status_roll < 0.88:
                status = "answered"
            elif status_roll < 0.94:
                status = "sent"
            else:
                status = "pending"

            assignment = Assignment(
                question_id=question.id,
                student_phone=student.phone_number,
                sent_at=sent_time if status != "pending" else None,
                delivered=status not in ("pending",),
                response_text=response_text if status in ("answered", "graded") else None,
                responded_at=responded_time if status in ("answered", "graded") else None,
                status=status,
                created_at=sent_time - timedelta(minutes=5),
            )
            session.add(assignment)
            session.commit()
            session.refresh(assignment)

            # Create assessment result for graded assignments
            if status == "graded":
                improvement = "none" if correct else random.choice(IMPROVEMENT_AREAS)
                bloom_achieved = random.choice(["remember", "understand", "apply", "analyze"])

                result = AssessmentResult(
                    assignment_id=assignment.id,
                    score=score,
                    correct=correct,
                    feedback="Good work!" if correct else "Keep practicing, you'll get it!",
                    improvement_areas=improvement,
                    bloom_level_achieved=bloom_achieved,
                    graded_at=responded_time + timedelta(seconds=random.randint(1, 30)),
                )
                session.add(result)

        session.commit()

        # ── Create StudentProgress records ────────────
        for topic in student_topics:
            topic_assignments = session.exec(
                select(Assignment).where(
                    Assignment.student_phone == student.phone_number,
                    Assignment.question_id.in_([q.id for q in question_map.get(topic.title, [])]),
                    Assignment.status == "graded",
                )
            ).all()

            attempted = len(topic_assignments)
            if attempted == 0:
                attempted = random.randint(3, 8)
            correct_count = int(attempted * score_mean * random.uniform(0.8, 1.2))
            correct_count = max(0, min(attempted, correct_count))

            difficulty = "beginner"
            if score_mean >= 0.7:
                difficulty = "advanced"
            elif score_mean >= 0.5:
                difficulty = "intermediate"

            prog = StudentProgress(
                student_phone=student.phone_number,
                topic_id=topic.id,
                questions_attempted=attempted,
                questions_correct=correct_count,
                current_difficulty=difficulty,
                history_summary=f"S:Started {topic.title}|T:Welcome! Let's begin.",
                last_active=now - timedelta(hours=random.randint(1, 48)),
            )
            session.add(prog)

        session.commit()

    # ── Create demo alerts ────────────────────────────
    alert_data = [
        {"phone": students[5].phone_number, "type": "disengaged", "severity": "critical",
         "message": f"{students[5].name} has not responded in 3 days."},
        {"phone": students[10].phone_number, "type": "disengaged", "severity": "critical",
         "message": f"{students[10].name} has been inactive for 48+ hours."},
        {"phone": students[6].phone_number, "type": "low_score", "severity": "info",
         "message": f"{students[6].name} scored below 30% on their last assessment."},
        {"phone": students[0].phone_number, "type": "no_response", "severity": "warning",
         "message": f"{students[0].name} has not responded in 24 hours."},
        {"phone": students[12].phone_number, "type": "low_score", "severity": "info",
         "message": f"{students[12].name} is struggling with fractions."},
        {"phone": students[2].phone_number, "type": "no_response", "severity": "warning",
         "message": f"{students[2].name} missed their last assignment."},
        {"phone": students[8].phone_number, "type": "low_score", "severity": "info",
         "message": f"{students[8].name} scored 25% on algebra quiz.", "dismissed": True},
    ]

    for ad in alert_data:
        alert = Alert(
            student_phone=ad["phone"],
            alert_type=ad["type"],
            severity=ad["severity"],
            message=ad["message"],
            dismissed=ad.get("dismissed", False),
            created_at=now - timedelta(hours=random.randint(1, 72)),
        )
        session.add(alert)

    session.commit()

    # ── Create demo clusters + memberships ───────────
    cluster_map: dict[str, Cluster] = {}  # cluster_name -> Cluster object

    # Auto-clusters from student aptitude data
    for student in students:
        if student.cluster_id:
            if student.cluster_id not in cluster_map:
                cluster = Cluster(
                    name=student.cluster_id,
                    is_custom=False,
                    grade_level=student.cluster_id.rsplit("-", 1)[0] if "-" in student.cluster_id else "",
                    description=f"Auto: {student.cluster_id}",
                    instructor_id=instructor_id,
                )
                session.add(cluster)
                session.commit()
                session.refresh(cluster)
                cluster_map[student.cluster_id] = cluster
            c = cluster_map[student.cluster_id]
            session.add(ClusterMembership(cluster_id=c.id, student_phone=student.phone_number))
    session.commit()

    # Custom demo clusters
    custom_clusters = [
        {
            "name": "Remedial Math Group",
            "description": "Students needing extra support in Mathematics across grades.",
            "grade_level": "",
            "phones": [students[0].phone_number, students[2].phone_number,
                       students[6].phone_number, students[12].phone_number],
        },
        {
            "name": "Advanced Readers",
            "description": "Top-performing students in English and Creative Writing.",
            "grade_level": "",
            "phones": [students[7].phone_number, students[9].phone_number,
                       students[13].phone_number, students[15].phone_number],
        },
    ]
    for cd in custom_clusters:
        cluster = Cluster(
            name=cd["name"], description=cd["description"],
            is_custom=True, grade_level=cd["grade_level"],
            instructor_id=instructor_id,
        )
        session.add(cluster)
        session.commit()
        session.refresh(cluster)
        for phone in cd["phones"]:
            session.add(ClusterMembership(cluster_id=cluster.id, student_phone=phone))
        session.commit()

    total_clusters = len(cluster_map) + len(custom_clusters)
    print(f"[SEED] Demo data created: {len(students)} students, {len(all_questions)} questions, {total_clusters} clusters, assignments across {len(topic_map)} topics")


# Allow running standalone for testing
if __name__ == "__main__":
    from database import engine, init_db
    init_db()
    with Session(engine) as s:
        seed_demo_data(s, instructor_id=1)
