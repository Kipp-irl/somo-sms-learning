# Somo — SMS-Powered Adaptive Learning for Displaced Learners

**Somo** (Swahili for *"lesson"*) is an AI-powered SMS learning platform that delivers personalized education to displaced and underserved students — no internet, no smartphone, no app required. Just a basic phone and the ability to send a text message.

---

## The Problem: Displaced Learning Lifeline

**Millions of people** are forcibly displaced worldwide. In East Africa alone, millions of school-age children face:

- **No internet access** — Refugee camps and rural displacement areas have minimal connectivity
- **Interrupted schooling** — Children miss months or years of education during displacement
- **No devices** — Smartphones and laptops are unaffordable; most families only have basic feature phones
- **Teacher shortages** — A single teacher may serve hundreds of students across multiple grade levels
- **No curriculum continuity** — Students arrive from different educational systems with varying levels of knowledge

Traditional edtech solutions (apps, video learning, LMS platforms) require internet and smartphones — resources that the most vulnerable learners simply don't have. **SMS is the one technology that reaches everyone.**

## The Solution: Somo

Somo bridges the education gap by turning every basic phone into a personal tutor:

1. **Instructor registers a student** with their phone number and grade level
2. **Adaptive aptitude test** is sent via SMS to determine the student's level (5 questions, auto-graded by AI)
3. **Students are auto-clustered** by grade and aptitude (e.g., "Grade 5-beginner", "Grade 8-advanced")
4. **AI generates grade-appropriate questions** aligned to Kenya's CBC curriculum
5. **Students answer via SMS** — AI grades responses, gives feedback, and adapts difficulty
6. **Instructors monitor everything** from a real-time web dashboard with analytics, alerts, and AI insights

### Why SMS?

| Feature | SMS | App-based |
|---|---|---|
| Requires internet | No | Yes |
| Works on feature phones | Yes | No |
| Reach in refugee camps | ~95% | <15% |
| Cost to student | Free (inbound) | Data costs |
| Setup needed | None | Download, account |

---

## Key Features

### For Students (SMS-only interaction)
- **Adaptive aptitude testing** — 5-question diagnostic determines skill level automatically
- **Personalized tutoring** — AI adjusts questions to student's grade, aptitude, and language
- **Multi-subject support** — Mathematics, English, Science, Kiswahili, Social Studies, and more
- **Difficulty progression** — Moves from beginner to advanced based on performance
- **Instant feedback** — AI grades every answer and explains mistakes
- **Improvement suggestions** — When struggling, students receive targeted study tips

### For Instructors (Web Dashboard)
- **Student management** — Register students, view profiles, track progress
- **Question generation** — AI generates grade-aware questions from any topic
- **Smart clusters** — Auto-clustered by aptitude + custom instructor-created groups
- **Cluster analytics** — Per-cluster stats, score trends, topic performance, AI insights
- **Assessment tracking** — Full history with filters, pagination, score distributions
- **Engagement alerts** — Automatic detection of disengaged students with nudge SMS
- **SMS simulator** — Test the full student experience without sending real messages
- **LLM-powered analytics** — AI-generated class overview with actionable recommendations

### Curriculum
Fully aligned to **Kenya's Competency-Based Curriculum (CBC)**:
- **Pre-Primary** (PP1–PP2): Literacy, Numeracy, Hygiene, Environment
- **Lower Primary** (Grade 1–3): English, Kiswahili, Mathematics, Science & Technology
- **Upper Primary** (Grade 4–6): English, Kiswahili, Mathematics, Science & Technology, Social Studies
- **Junior Secondary** (Grade 7–9): English, Kiswahili, Mathematics, Integrated Science, Social Studies
- **Senior Secondary** (Grade 10–12): English, Kiswahili, Mathematics, Sciences, Humanities

---

## Architecture

```
Student (feature phone)          Instructor (web browser)
       |                                |
   SMS via Twilio                  Dashboard UI
       |                                |
       v                                v
  ┌──────────────────────────────────────────┐
  │              FastAPI Backend              │
  │                                          │
  │  Webhook ──> State Machine ──> LLM       │
  │  (Twilio)    (aptitude,       (DeepSeek  │
  │               tutoring,        V3.1)     │
  │               grading)                   │
  │                                          │
  │  REST API ──> Dashboard ──> Analytics    │
  │  (CRUD,       (Charts,      (Insights,  │
  │   filters,     clusters,     alerts)    │
  │   pagination)  assessments)             │
  ├──────────────────────────────────────────┤
  │          SQLite + SQLModel               │
  └──────────────────────────────────────────┘
```

### Tech Stack
| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, SQLModel/SQLAlchemy |
| Database | SQLite (portable, zero-config) |
| AI/LLM | DeepSeek V3.1 via Lightning AI (OpenAI-compatible) |
| SMS Gateway | Twilio Programmable Messaging |
| Frontend | Vanilla HTML/CSS/JS, Chart.js 4.x |
| SMS Safety | Custom GSM-7 sanitization + 155-char truncation |

---

## Getting Started

### Prerequisites
- Python 3.11+
- A Twilio account (free trial works)
- A DeepSeek API key via Lightning AI

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/somo-sms-learning.git
cd somo-sms-learning
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```env
DEEPSEEK_API_KEY=your-lightning-ai-api-key
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_MESSAGING_SERVICE_SID=your-messaging-service-sid
TWILIO_PHONE_NUMBER=+1234567890
INSTRUCTOR_PASSCODE=your-secure-passcode
```

### Run

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser. The dashboard auto-seeds with demo data (18 students, 10 topics, 56 questions, 18 clusters) so you can explore immediately.

**Default login:** Name: `Default Instructor` / Passcode: `admin123`

### Twilio Webhook

Point your Twilio phone number's incoming message webhook to:
```
https://your-server.com/webhook
```

---

## Project Structure

```
somo-sms-learning/
├── main.py                 # FastAPI app — all endpoints + SMS state machine
├── models.py               # SQLModel schemas (Student, Cluster, Assignment, etc.)
├── database.py             # SQLite engine + session management
├── llm_service.py          # DeepSeek LLM integration (questions, grading, insights)
├── curriculum.py           # Kenya CBC curriculum structure + subjects
├── twilio_service.py       # Twilio SMS wrapper + simulator capture
├── sms_utils.py            # GSM-7 sanitization + truncation
├── engagement_monitor.py   # Background engagement alerts
├── seed_demo.py            # Demo data generator
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── templates/
│   ├── dashboard.html      # Instructor dashboard (single-page app)
│   └── login.html          # Login page
└── static/
    └── style.css           # Dashboard styles
```

---

## Impact

Somo makes education accessible to learners who have been excluded from every other digital learning solution. By meeting students where they are — on the most basic communication technology available — we ensure that displacement doesn't mean the end of learning.

- **Zero barrier to entry**: No app, no internet, no smartphone. Just SMS.
- **AI-personalized at scale**: One instructor can effectively support hundreds of students at different levels through automated adaptive learning.
- **Curriculum-aligned**: Students don't just learn random facts — they follow Kenya's official CBC, maintaining continuity if/when they return to formal schooling.
- **Real-time visibility**: Instructors see who's struggling, who's disengaged, and where to focus their limited time.

---

## License

This project is licensed under the [MIT License](LICENSE).
