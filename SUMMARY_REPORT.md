# Somo: SMS-Powered Adaptive Learning for Displaced Learners

## Summary Report

**Project Name:** Somo (Swahili for "lesson")
**Problem Focus:** Displaced Learning Lifeline and Accessibility
**Author:** Victor Koech
**Date:** March 2026
**Repository:** https://github.com/Kipp-irl/somo-sms-learning

---

## Problem Statement

Around the world, over 82 million people have been forcibly displaced. In East Africa alone, millions of school-age children have had their education completely disrupted. These children face a set of overlapping barriers that most edtech solutions simply aren't designed to handle:

- They have no reliable internet access. Refugee camps and rural displacement zones are often connectivity dead zones.
- Their schooling has been interrupted, sometimes for months or years at a time, leaving massive gaps in foundational knowledge.
- Smartphones and laptops are out of reach for most families. What they do have, in many cases, is a basic feature phone.
- There are severe teacher shortages. A single instructor may be responsible for hundreds of students spread across multiple grade levels.
- Students arrive from different educational systems, making it nearly impossible to pick up a standard curriculum where they left off.

Every major digital learning platform today — apps, video courses, LMS tools — assumes internet connectivity and a smartphone at minimum. That assumption excludes the learners who need help the most. But there is one technology that reaches nearly everyone: SMS.

## Our Solution

Somo turns a basic feature phone into a personal AI tutor. The entire student experience happens over SMS — no internet, no app downloads, no account creation. A student just needs to be able to send and receive text messages.

Here's how it works in practice:

1. An instructor registers a student through a web dashboard, entering their phone number and grade level.
2. The student immediately receives a 5-question adaptive aptitude test via SMS. The AI grades each answer in real time to figure out where the student actually is academically — not just what grade they're enrolled in.
3. Based on grade level and test performance, students are automatically grouped into learning clusters (for example, "Grade 5 — Beginner" or "Grade 8 — Advanced"). Instructors can also create custom clusters.
4. The AI then generates curriculum-aligned questions tailored to each student's level, drawing from Kenya's Competency-Based Curriculum (CBC) covering Pre-Primary through Senior Secondary.
5. Students answer questions via SMS. The AI grades their responses, provides feedback explaining what they got right or wrong, and adjusts the difficulty of future questions accordingly.
6. Instructors monitor all of this through a real-time web dashboard — tracking individual progress, reviewing cluster performance, receiving alerts when students disengage, and getting AI-generated insights about where to focus their limited time.

The key insight behind Somo is that SMS reaches roughly 95% of people in refugee camps, while app-based solutions reach less than 15%. By building on the most basic communication layer available, we meet students exactly where they are.

## Technical Approach

### Architecture

The system is split into two interfaces serving two user types:

- **Students** interact entirely through SMS on any basic phone. Messages are routed through Twilio's programmable messaging service.
- **Instructors** use a web-based dashboard to manage students, create topics, generate questions, monitor progress, and respond to engagement alerts.

Both interfaces feed into a single FastAPI backend that handles all the logic — the SMS state machine, AI processing, data persistence, and the REST API for the dashboard.

### How the SMS Flow Works

When a student sends a text message, Twilio forwards it to our webhook endpoint. The server immediately acknowledges receipt (to avoid timeout issues and duplicate messages), then processes the message in the background. A state machine tracks where each student is in their journey — whether they're in the middle of an aptitude test, actively answering questions on a topic, or idle waiting for new material. The AI generates a response, which gets sanitized to ensure it only uses GSM-7 compatible characters (to avoid the encoding trap where a single emoji or smart quote would cut the character limit from 160 down to 70), truncated to 155 characters for safe single-segment delivery, and sent back via Twilio.

### AI and Curriculum

The AI layer uses DeepSeek V3.1 (accessed through Lightning AI's OpenAI-compatible API) to handle several tasks: generating curriculum-aligned questions at appropriate difficulty levels, grading student answers with structured feedback, providing Socratic tutoring that guides rather than gives answers, summarizing conversation history to maintain context without blowing up token costs, and generating analytics insights for instructors.

All content is aligned to Kenya's CBC, spanning from Pre-Primary literacy and numeracy through Senior Secondary sciences and humanities. The curriculum module covers every learning area at every level, so the AI knows exactly what's appropriate for each student.

### Data and State Management

We use SQLite with SQLModel as the ORM. The database tracks everything: student profiles and SMS state, cluster memberships, topic and question banks, assignment delivery and response cycles, graded assessment results, per-student progress with rolling AI context summaries, and engagement alerts. The phone number serves as the primary key for students, since that's the one identifier that's always available in an SMS interaction.

### Dashboard

The instructor dashboard is a single-page application built with vanilla HTML, CSS, and JavaScript (no framework dependencies to maintain). It includes seven main views: an overview with charts, student management, course/topic management, cluster analytics with AI-powered insights, assessment tracking with filters and pagination, an alert feed for engagement monitoring, and an SMS simulator for testing the student experience without sending real messages.

### Tech Stack

| Component | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI |
| Database | SQLite via SQLModel/SQLAlchemy |
| AI/LLM | DeepSeek V3.1 via Lightning AI |
| SMS Gateway | Twilio Programmable Messaging |
| Frontend | Vanilla HTML/CSS/JS, Chart.js |
| SMS Safety | Custom GSM-7 sanitizer, 155-char truncation |

## Key Features

- **Adaptive aptitude testing** that meets each student at their actual level, not just their enrolled grade
- **Personalized AI tutoring** over SMS with difficulty progression based on real performance
- **Multi-subject support** across the full Kenya CBC curriculum (Mathematics, English, Kiswahili, Sciences, Social Studies, and more)
- **Smart student clustering** by grade and aptitude, with support for custom instructor-defined groups
- **Engagement monitoring** that automatically detects disengaged students (24h and 48h thresholds) and can send nudge messages
- **LLM-powered analytics** giving instructors actionable class-level and cluster-level insights
- **SMS simulator** for testing and demonstration without consuming SMS credits
- **Rate limiting** (10 messages per student per day) and idempotency guards to control costs and prevent duplicate processing

## Design Decisions

A few decisions shaped the project significantly:

**Twilio over Africa's Talking:** The original technical plan specified Africa's Talking as the SMS gateway, given its strong presence in East African telecom. During implementation, we switched to Twilio for more reliable sandbox behavior and better documentation. The architecture is gateway-agnostic — swapping providers would only require changing the webhook parsing and send logic.

**DeepSeek V3.1 over larger models:** Cost matters enormously for a system that processes potentially thousands of SMS interactions daily. DeepSeek provides strong reasoning and instruction-following at a fraction of the cost of larger models, which is critical for sustainability in a humanitarian context.

**SQLite over a hosted database:** Zero configuration, portable as a single file, and perfectly adequate for the scale of a pilot deployment. No server to manage, no credentials to configure — just works.

**Vanilla frontend over a framework:** The dashboard needs to be maintainable by a small team with potentially limited web development resources. No build step, no dependency management, no framework churn. It loads fast and does what it needs to do.

## Impact

Somo addresses a gap that existing edtech solutions have largely ignored. The students who are hardest to reach — those without internet, without smartphones, without stable schooling — are exactly the ones who need adaptive, personalized education most urgently.

By delivering AI-powered learning through the most universally accessible technology available, Somo ensures that displacement doesn't have to mean the end of a child's education. A single instructor using Somo can meaningfully support hundreds of students across different levels, subjects, and locations — something that would be impossible through traditional teaching alone.

The system is designed to be deployable in any context where SMS works, which is effectively everywhere. While the current curriculum is aligned to Kenya's CBC, the architecture supports adding any curriculum structure, making it adaptable to displacement contexts across different countries and educational systems.

---

*Built for the Displaced Learning Lifeline and Accessibility challenge.*
