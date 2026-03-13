# Somo: SMS-Powered Adaptive Learning for Displaced Learners

## Summary Report

**Project Name:** Somo (Swahili for "lesson")
**Challenge:** Displaced Learning Lifeline and Accessibility
**Problem Focus:** Displacement, No Internet, Interrupted Schooling, Education
**Author:** Victor Koech
**Date:** March 2026
**Repository:** https://github.com/Kipp-irl/somo-sms-learning

---

## 1. Problem Statement

Over 82 million people worldwide have been forcibly displaced from their homes. In East Africa, millions of these are school-age children whose education has been completely derailed. The barriers they face stack on top of one another in ways that make traditional solutions useless:

There is no internet. Refugee camps and rural displacement areas have little to no connectivity. Schooling has been interrupted for months or years, creating huge gaps in foundational knowledge. Families cannot afford smartphones or laptops, but many do own basic feature phones. There are not enough teachers — a single instructor might be responsible for hundreds of students across different grade levels. And students arrive from different countries and educational systems, so there is no shared starting point.

Every mainstream edtech platform — whether it is an app, a video course, or a learning management system — requires internet access and a capable device. That means the learners who need the most help are the ones who are completely locked out.

But there is one piece of technology that works almost everywhere, even in places with zero internet: SMS. Basic text messaging reaches approximately 95% of people in refugee camp settings, compared to less than 15% for app-based solutions. Somo is built on that insight.

---

## 2. The Solution

Somo turns any basic feature phone into a personal AI tutor. Students interact entirely through SMS. There is nothing to download, no account to create, and no data plan needed. If a student can send and receive text messages, they can learn with Somo.

On the other side, instructors manage everything through a web dashboard where they can register students, create learning topics, generate curriculum-aligned questions using AI, monitor student progress in real time, and receive alerts when students fall behind.

The system is built around Kenya's Competency-Based Curriculum (CBC), covering every grade level from Pre-Primary (PP1-PP2) through Senior Secondary (Grade 10-12) and every learning area within those levels. This means students are not just getting random quiz questions — they are working through material that aligns with what they would be learning in a formal school setting, which matters a lot for students who may eventually return to the classroom.

---

## 3. How It Works — Full Workflow

### 3.1 Student Registration

An instructor logs into the web dashboard and registers a new student by entering their name, phone number, grade level, and preferred language. Most students are set up with English, but the system supports localized interaction.

As soon as the registration is saved, the system automatically begins the onboarding process. The student does not need to do anything to start — the first message comes to them.

### 3.2 Adaptive Aptitude Test

Within moments of registration, the student receives a welcome SMS followed by the first question of a 5-question aptitude test. This test is designed to figure out where the student actually stands academically, which is often very different from their enrolled grade level given the disruptions they have experienced.

The test works like this:

- The AI generates each question on the fly, tailored to the student's grade level and aligned to the CBC curriculum.
- Questions start easy (Bloom's taxonomy level: "remember") and get progressively harder (moving to "understand" and then "apply") as the test goes on.
- After the student texts back an answer, the AI grades it immediately. The student gets brief feedback and the next question in one message.
- After all 5 questions, the system calculates a score and assigns an aptitude level: beginner (below 40%), intermediate (40-69%), or advanced (70% and above).
- The student is automatically placed into a learning cluster based on their grade and aptitude. For example, a Grade 5 student who scores 2 out of 5 would be placed in "Grade 5-beginner."

The student then receives a message telling them their score and level, and is prompted to send MENU to choose a subject to study.

### 3.3 Topic Selection

When the student sends MENU (or TOPICS or STOP), the system replies with a numbered list of all available subjects. The student picks one by replying with the corresponding number — for instance, sending "1" to select the first topic.

Once a topic is selected, the AI generates an opening question using Socratic questioning. It does not just dump information — it asks the student something that gets them thinking about the topic at the level that matches their aptitude.

### 3.4 Active Learning and Tutoring

From here, the student and the AI go back and forth over SMS. There are two ways learning happens:

**Instructor-assigned questions:** An instructor can select specific questions from the dashboard and send them to individual students or entire clusters at once. When the student replies, the AI grades their answer, stores the result, and sends feedback. If the student gets the answer wrong and has attempted at least 3 questions overall, the system also sends a follow-up message with specific improvement suggestions based on their weak areas.

**Free-form Socratic tutoring:** When a student is engaged with a topic, they can just keep texting naturally. The AI acts as a tutor — asking questions one at a time, evaluating responses, providing hints when the student is stuck, and gradually increasing difficulty. Every message from the student is assessed: the AI determines whether it is an answer attempt, scores it if so, and adjusts accordingly. This is not a static quiz. It is an ongoing conversation adapted to the student's performance in real time.

### 3.5 Adaptive Difficulty

The system tracks every answer a student gives. After every 5 graded responses within a topic, it checks the student's recent accuracy. If they are getting 80% or more correct, the difficulty bumps up one level (beginner to intermediate, or intermediate to advanced). If they are scoring 30% or below, the difficulty drops down. This ensures students are always working at the edge of their ability — challenged enough to learn but not so overwhelmed that they give up.

### 3.6 Conversation Memory

SMS is stateless by nature — each message exists in isolation. But effective tutoring requires memory of what has already been covered. Somo handles this with a rolling context system. Recent exchanges are kept verbatim, while older parts of the conversation are compressed into a summary by the AI. This summary is stored in the database and injected into every LLM call, so the tutor always knows what the student has been working on, what they got right, what they struggled with, and what difficulty level they are at. The total context window is capped at 800 characters to keep costs under control while maintaining continuity.

### 3.7 SMS Safety and Encoding

Every outbound message passes through a safety layer before being sent. This handles two things that can silently break SMS delivery on basic phones:

First, character encoding. If a message contains even a single character outside the GSM-7 alphabet — an emoji, a curly quote, or certain accented characters — the entire message switches from GSM-7 encoding (160 character limit) to UCS-2 encoding (70 character limit). That one stray character could double or triple the cost of the message and cause delivery failures on older phones. The system replaces all non-GSM-7 characters with safe equivalents before sending.

Second, message length. All outgoing messages are truncated to 155 characters on a word boundary. This keeps everything within a single SMS segment with a small safety margin, avoiding the unreliable behavior of multi-segment (concatenated) SMS on basic feature phones.

### 3.8 Rate Limiting and Idempotency

Each student is limited to 10 SMS interactions per day. This controls costs and prevents runaway usage. The counter resets at midnight.

On the receiving end, every incoming webhook from Twilio includes a unique message ID. The system checks this ID against a database table before processing. If the message has already been handled, it is silently skipped. This prevents duplicate processing when Twilio retries a webhook due to network issues — which would otherwise result in the student getting the same reply multiple times and the system burning extra AI tokens.

### 3.9 Engagement Monitoring

A background process runs every 60 minutes and checks on every active student:

- If a student has not replied in 24 hours, a warning alert is created for the instructor.
- If a student has not replied in 48 hours, a critical alert is created and the student's state is automatically changed to idle to prevent wasting resources on further messages.
- If a student's most recent graded assignment scored below 30%, an informational alert is created so the instructor knows the student is struggling.

Instructors can respond to alerts in two ways: they can "nudge" the student (which sends an encouraging SMS like "Hi Sarah! Your tutor misses you. Reply to any message to keep learning. You are doing great!"), or they can dismiss the alert if no action is needed.

When an idle student sends any message, their state is automatically reactivated.

### 3.10 Instructor Dashboard

The web dashboard gives instructors full visibility and control. It has seven main sections:

**Overview** — High-level statistics: total students, topics, assignments, average scores, response rates, and trend charts showing activity over the past 30 days.

**Students** — Register new students, view profiles, track individual progress with per-topic breakdowns and score histories.

**Courses** — Create and manage topics. Use AI to generate batches of curriculum-aligned questions at specific difficulty and Bloom's taxonomy levels.

**Clusters** — View auto-generated aptitude clusters and create custom groups. Each cluster has its own analytics: average score, response rate, per-topic performance, 14-day score trends, and AI-generated insights with specific recommendations.

**Assessments** — Browse all graded work with filters for status, topic, grade, student, and date range. View score distributions and aggregate statistics.

**Alerts** — A feed of engagement warnings with nudge and dismiss actions.

**Simulator** — A chat-style interface that lets instructors test the full SMS student experience without sending real messages or using Twilio credits. The instructor picks a registered student from a dropdown, types messages as if they were that student, and sees exactly how the AI tutor would respond. This is useful for demonstration, quality assurance, and training new instructors.

### 3.11 AI-Powered Analytics

The dashboard includes two layers of AI-generated insights:

**Class-level insights** aggregate statistics across all students and send them to the AI for analysis. The AI returns a summary, a list of at-risk students who need immediate attention, observed strengths, and actionable recommendations. These are cached for 30 minutes to avoid excessive API calls.

**Cluster-level insights** do the same thing but scoped to a specific student group. The AI identifies strengths, weaknesses, recommended focus areas, and suggested topics for that cluster. This helps instructors prioritize their limited time effectively.

---

## 4. Technical Architecture

### System Overview

```
Student (feature phone)              Instructor (web browser)
       |                                    |
   SMS via Twilio                    Dashboard UI
       |                                    |
       v                                    v
  +------------------------------------------------+
  |              FastAPI Backend                    |
  |                                                |
  |  Webhook --> State Machine --> LLM Service     |
  |  (Twilio)   (aptitude,        (DeepSeek V3.1  |
  |              tutoring,         via Lightning   |
  |              grading)          AI)             |
  |                                                |
  |  REST API --> Dashboard --> Analytics           |
  |  (40+ endpoints)  (Charts,    (LLM insights,  |
  |                    clusters,   engagement      |
  |                    simulator)  monitoring)     |
  +------------------------------------------------+
  |            SQLite + SQLModel                   |
  +------------------------------------------------+
```

### Tech Stack

| Component | Technology | Reason |
|---|---|---|
| Backend | Python 3.11+, FastAPI | Async support for handling concurrent SMS and AI processing |
| Database | SQLite via SQLModel | Zero-config, portable, no external server needed |
| AI / LLM | DeepSeek V3.1 via Lightning AI | Cost-effective reasoning with strong instruction-following |
| SMS Gateway | Twilio Programmable Messaging | Reliable global SMS delivery with good developer tools |
| Frontend | Vanilla HTML/CSS/JS, Chart.js | No build step, no framework dependencies, fast to load |
| SMS Safety | Custom GSM-7 sanitizer | Prevents encoding issues on basic feature phones |

### Data Model

The database has 11 tables: Instructor, Student, Cluster, ClusterMembership, Topic, Question, Assignment, AssessmentResult, StudentProgress, Alert, and ProcessedMessage. The student's phone number is the primary key, since it is the only identifier available in an SMS context. Every graded interaction is stored as an AssessmentResult linked to an Assignment, which allows full analytics and historical tracking.

---

## 5. Key Features

- **Adaptive aptitude testing** — 5-question diagnostic that places students at their true academic level, not just their enrolled grade
- **Socratic AI tutoring** — The AI asks guiding questions rather than lecturing, encouraging students to think through problems
- **Curriculum alignment** — All content follows Kenya's CBC from Pre-Primary through Senior Secondary across all learning areas
- **Adaptive difficulty** — Automatically adjusts up or down every 5 answers based on student accuracy
- **Smart clustering** — Auto-groups students by grade and aptitude, with support for custom instructor-defined groups
- **Engagement monitoring** — Background system detects silence (24h warning, 48h critical) and low scores, with SMS nudge capability
- **Rolling conversation memory** — AI-powered context summarization keeps tutoring coherent within an 800-character budget
- **SMS simulator** — Full testing environment without real SMS costs
- **Rate limiting and idempotency** — Controls costs and prevents duplicate processing
- **AI-powered analytics** — Class-level and cluster-level insights with specific, actionable recommendations

---

## 6. Design Decisions

**Twilio over Africa's Talking:** The original technical plan specified Africa's Talking given its strong presence in East African telecom. During implementation, I switched to Twilio for more reliable sandbox behavior and better documentation. The architecture is gateway-agnostic — swapping providers only requires changing the webhook parsing and send function.

**DeepSeek V3.1 over larger models:** Cost is critical for a system processing potentially thousands of SMS interactions daily. DeepSeek delivers strong reasoning and instruction-following ability at a fraction of the cost of larger proprietary models, which matters for sustainability in a humanitarian deployment.

**SQLite over a hosted database:** Zero configuration, portable as a single file, and perfectly adequate for pilot-scale deployments. No external server to manage or credentials to configure.

**Vanilla frontend over a framework:** The dashboard needs to be maintainable by a small team that may not have deep web development expertise. No build step, no dependency management, no framework upgrades to track. It loads quickly and does exactly what it needs to.

**155-character message cap:** Rather than relying on multi-segment SMS concatenation (which is unreliable on older phones and increases cost), every reply is truncated to 155 characters on a word boundary. This ensures single-segment delivery every time.

---

## 7. Future Upgrades and Roadmap

### 7.1 Retrieval-Augmented Generation (RAG)

The current system relies on the LLM's training data and injected curriculum descriptions to generate questions and tutoring content. A significant upgrade would be to implement RAG, where the AI retrieves specific passages from actual textbooks, past exam papers, and curriculum documents before generating its response.

This would mean uploading PDFs of Kenyan CBC textbooks, past KNEC exam papers, and approved learning materials into a vector database (such as ChromaDB or Pinecone). When the AI needs to generate a question or explain a concept, it would first search this knowledge base for relevant passages and use them as grounding material. This would make the tutoring far more accurate and specific to what students actually encounter in formal schooling, rather than relying on the LLM's general knowledge.

### 7.2 Upgraded AI Model

DeepSeek V3.1 was chosen for its cost-efficiency, which was the right call for a prototype. But as the system scales, there is room to upgrade to more capable models. Options include Claude (Anthropic), GPT-4o (OpenAI), or Gemini (Google) — all of which offer stronger reasoning, better instruction following, and more nuanced feedback. The system already uses an OpenAI-compatible API client, so swapping models would be straightforward. A hybrid approach could also work: use a smaller, cheaper model for routine grading and a more powerful one for generating insights and handling edge cases.

### 7.3 Multi-Language Support

The system currently defaults to English with some support for Kiswahili. A major upgrade would be full multi-language tutoring — where a student could interact entirely in Kiswahili, Somali, Amharic, French, or other languages commonly spoken in East African displacement contexts. This would require language detection on incoming messages, language-specific prompt engineering, and potentially language-specific curriculum content. The LLM layer already supports this in principle, but the prompts and SMS templates would need to be adapted.

### 7.4 Voice and USSD Integration

Not all displaced learners are literate enough to engage with text-based tutoring. A future version could add IVR (Interactive Voice Response) support, where students listen to questions read aloud and respond by pressing phone keys or speaking. USSD (Unstructured Supplementary Service Data) is another option — it provides menu-driven interactions that do not require SMS credits and work on every GSM phone. Both would expand the reach of the platform to even more underserved populations.

### 7.5 Offline-First Progressive Web App

The instructor dashboard currently requires an internet connection. A progressive web app (PWA) version with offline caching would allow instructors working in low-connectivity areas to review student data, prepare assignments, and queue actions that sync when connectivity is available.

### 7.6 Multi-Curriculum Support

The current system is built around Kenya's CBC, but displaced students come from many different national education systems. Adding support for additional curricula — Uganda, Tanzania, Ethiopia, South Sudan, DRC — would make the platform useful across the broader displacement context in East Africa. The curriculum module is already structured to support this; it would require adding the curriculum definitions and mapping them to grade levels.

### 7.7 Parent and Guardian Engagement

Many displaced families want to be involved in their children's education but have no visibility into what their child is learning. A simple SMS reporting feature that sends weekly progress summaries to a parent or guardian's phone number would strengthen the connection between families and their children's learning, and could improve student retention.

### 7.8 Analytics and Reporting Exports

Instructors and NGO coordinators often need to produce reports for donors and program oversight. Adding the ability to export assessment data, progress reports, and engagement metrics as CSV or PDF from the dashboard would make the platform more useful in organizational contexts.

### 7.9 Production Infrastructure

For a real deployment at scale, several infrastructure upgrades would be needed:
- Migration from SQLite to PostgreSQL for concurrent access and better reliability
- Deployment on a cloud platform with proper hosting and SSL
- Background task processing via a job queue (Celery or similar) instead of FastAPI BackgroundTasks
- Monitoring, logging, and error alerting for operational visibility
- Automated database backups

---

## 8. Impact

Somo fills a gap that the edtech industry has largely overlooked. The students who are hardest to reach — those without internet, without smartphones, without a stable school to attend — are the ones who need personalized, adaptive education the most.

By building on SMS, the most universally accessible digital communication technology that exists, Somo removes every barrier between a displaced student and a learning experience. A single instructor using the platform can meaningfully support hundreds of students across different grade levels, subjects, and aptitude levels. That kind of scale is simply not possible through traditional teaching in displacement settings.

The system is designed to be deployable wherever SMS works, which is effectively everywhere. While the current implementation targets Kenya's CBC, the architecture is built to accommodate any national curriculum, making it adaptable across displacement contexts in different countries.

Education is one of the first things lost when communities are displaced, and one of the hardest to restore. Somo is an attempt to make sure that losing your home does not have to mean losing your chance to learn.

---

*Built for the Displaced Learning Lifeline and Accessibility challenge.*
