"""
llm_service.py – DeepSeek V3.1 via Lightning AI (Somo).

Capabilities:
  - generate_aptitude_question()  → adaptive aptitude test questions with correct answer
  - generate_questions()          → batch question generation for a topic
  - grade_answer()                → structured grading with feedback
  - generate_sms_reply()          → free-form Socratic tutoring with inline evaluation
  - suggest_improvements()        → actionable improvement SMS
  - summarize_history()           → LLM-assisted rolling context window
  - generate_class_insights()     → LLM-powered analytics for instructors
"""

import json
import os
from openai import OpenAI

from sms_utils import sanitize_gsm7 as _sanitize, truncate_sms as _truncate
from curriculum import get_curriculum_context

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url="https://lightning.ai/api/v1",
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        )
    return _client


MODEL = "lightning-ai/DeepSeek-V3.1"


def _call_llm(messages: list[dict], max_tokens: int = 100, temperature: float = 0.6) -> str:
    """Centralized LLM call with error handling."""
    try:
        r = _get_client().chat.completions.create(
            model=MODEL, messages=messages,
            max_tokens=max_tokens, temperature=temperature, top_p=0.95,
        )
        return r.choices[0].message.content or ""
    except Exception as e:
        print(f"[LLM] Error: {e}")
        return ""


def _strip_fences(raw: str) -> str:
    """Remove markdown code fences from LLM output."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    return cleaned


# ── Aptitude test generation ──────────────────────────

def generate_aptitude_question(
    grade: str,
    step: int,
    language: str = "English",
    subject: str = "General",
) -> dict:
    """Generate one adaptive aptitude question with its correct answer.

    Returns: {"question": str, "correct_answer": str}
    """
    bloom_levels = ["remember", "remember", "understand", "understand", "apply"]
    bloom = bloom_levels[min(step, 4)]

    curriculum = get_curriculum_context(grade, subject)

    system = f"""\
You are creating a short aptitude test for a {grade} student.
Language: {language}

CURRICULUM CONTEXT:
{curriculum}

Generate exactly ONE question at the "{bloom}" level of Bloom's taxonomy.
The question MUST test knowledge from the curriculum context above.
Step {step + 1} of 5 — {"start easy" if step == 0 else "increase difficulty slightly"}.

Return a JSON object with exactly two keys:
- "question": the question text (under 120 characters, plain text, no emojis)
- "correct_answer": the expected correct answer (under 50 characters)

Return ONLY the JSON object, no other text.
"""
    raw = _call_llm([
        {"role": "system", "content": system},
        {"role": "user", "content": "Generate the question now."},
    ], max_tokens=120, temperature=0.7)

    try:
        result = json.loads(_strip_fences(raw))
        q = _truncate(_sanitize(str(result.get("question", ""))), 120)
        a = str(result.get("correct_answer", ""))[:50]
        if q:
            return {"question": q, "correct_answer": a}
    except (json.JSONDecodeError, Exception) as e:
        print(f"[LLM] Failed to parse aptitude Q: {e}\nRaw: {raw}")

    # Fallback: treat raw output as the question
    q = _truncate(_sanitize(raw.strip()), 120)
    return {"question": q, "correct_answer": ""}


# ── Batch question generation ─────────────────────────

def generate_questions(
    topic_title: str,
    topic_description: str,
    difficulty: str,
    bloom_level: str = "understand",
    count: int = 5,
    language: str = "English",
    grade: str = "",
) -> list[dict]:
    """Generate multiple questions for a topic. Returns list of {text, difficulty, bloom_level, correct_hint}."""
    curriculum = get_curriculum_context(grade, topic_title) if grade else ""

    system = f"""\
You are a curriculum designer creating SMS-based quiz questions.
Language: {language}
{"Grade level: " + grade if grade else ""}
{"Curriculum context: " + curriculum if curriculum else ""}

Generate exactly {count} questions about:
TOPIC: {topic_title}
DETAILS: {topic_description}
DIFFICULTY: {difficulty}
BLOOM LEVEL: {bloom_level}

Return a JSON array. Each item must have:
- "text": the question (under 140 characters, plain text, no emojis)
- "difficulty": "{difficulty}"
- "bloom_level": "{bloom_level}"
- "correct_hint": a brief phrase describing the correct answer (under 50 chars)

Return ONLY the JSON array, no other text.
"""
    raw = _call_llm(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": "Generate the questions now."},
        ],
        max_tokens=800, temperature=0.7,
    )
    try:
        return json.loads(_strip_fences(raw))
    except (json.JSONDecodeError, Exception) as e:
        print(f"[LLM] Failed to parse questions: {e}\nRaw: {raw}")
        return []


# ── Grading engine ────────────────────────────────────

def grade_answer(
    question_text: str,
    student_answer: str,
    correct_hint: str,
    difficulty: str = "beginner",
    language: str = "English",
    grade: str = "",
) -> dict:
    """Grade a student's answer. Returns {score, correct, feedback, improvement_area}."""
    curriculum = get_curriculum_context(grade, "") if grade else ""

    system = f"""\
You are grading a student's SMS answer to a quiz question.
Language: {language}
{"Student grade level: " + grade if grade else ""}
{"Curriculum expectations: " + curriculum if curriculum else ""}

QUESTION: {question_text}
EXPECTED ANSWER: {correct_hint}
DIFFICULTY: {difficulty}

The student answered: "{student_answer}"

Grade their answer considering what is appropriate for their grade level.
Return a JSON object with:
- "score": float 0.0 to 1.0 (0=wrong, 0.5=partially correct, 1.0=perfect)
- "correct": boolean (true if score >= 0.5)
- "feedback": encouraging feedback under 100 characters (plain text, no emojis)
- "improvement_area": one specific weak area if wrong, or "none" if correct (under 30 chars)

Return ONLY the JSON object, no other text.
"""
    raw = _call_llm(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": "Grade the answer now."},
        ],
        max_tokens=150, temperature=0.3,
    )
    try:
        result = json.loads(_strip_fences(raw))
        return {
            "score": float(result.get("score", 0)),
            "correct": bool(result.get("correct", False)),
            "feedback": _sanitize(str(result.get("feedback", "")))[:100],
            "improvement_area": str(result.get("improvement_area", "none"))[:30],
        }
    except (json.JSONDecodeError, Exception) as e:
        print(f"[LLM] Failed to parse grade: {e}\nRaw: {raw}")
        return {
            "score": 0.0, "correct": False,
            "feedback": "Could not grade. Try again!",
            "improvement_area": "unknown",
        }


# ── Improvement suggestions ───────────────────────────

def suggest_improvements(
    weak_areas: list[str],
    grade: str,
    language: str = "English",
) -> str:
    """Summarize weak areas into actionable improvement SMS."""
    areas = ", ".join(set(a for a in weak_areas if a and a != "none"))
    if not areas:
        return "Great job! Keep up the good work."

    curriculum = get_curriculum_context(grade, "")

    system = f"""\
A {grade} student is weak in: {areas}.
Language: {language}
Curriculum: {curriculum}

Write ONE encouraging SMS (under 150 chars, plain text, no emojis) suggesting
what they should focus on next. Be specific to their grade level and warm.
"""
    raw = _call_llm([
        {"role": "system", "content": system},
        {"role": "user", "content": "Write the suggestion now."},
    ], max_tokens=80)
    return _truncate(_sanitize(raw.strip())) or f"Focus on: {areas[:100]}"


# ── Free-form Socratic reply ─────────────────────────

def generate_sms_reply(
    student_message: str,
    history_summary: str | None = None,
    current_step: int = 0,
    topic_title: str = "",
    topic_description: str = "",
    difficulty: str = "beginner",
    language: str = "English",
    grade: str = "",
) -> dict:
    """Generate a Socratic tutoring reply with optional inline evaluation.

    Returns: {"reply": str, "is_answer": bool, "score": float|None}
    """
    curriculum = get_curriculum_context(grade, topic_title) if grade else ""

    system = f"""\
You are an SMS tutor for a {grade} student on a feature phone.
Language: {language}

CURRICULUM CONTEXT:
{curriculum}

YOUR JOB:
- Generate questions about the topic below, one at a time.
- When the student answers, evaluate their answer, give brief feedback, then ask the next question.
- Use Socratic questioning — guide, don't reveal answers directly.
- Adapt difficulty to the student's grade level and performance.

RULES:
- Plain text ONLY. NO emojis, NO bold, NO asterisks.
- Be warm, encouraging, direct. No filler.

TOPIC: {topic_title}
DETAILS: {topic_description}
LEVEL: {difficulty}
STEP: {current_step}

After generating your reply, also evaluate: is the student's message an ANSWER to a question?

Return a JSON object:
- "reply": your SMS reply text (under 150 characters, plain text)
- "is_answer": true if the student message is attempting to answer a question, false if it's a greeting/request/off-topic
- "score": float 0.0 to 1.0 if is_answer is true (null if false)

Return ONLY the JSON object, no other text.
"""
    messages: list[dict] = [{"role": "system", "content": system}]
    if history_summary:
        messages.append({
            "role": "system",
            "content": f"[Conversation so far] {history_summary}",
        })
    messages.append({"role": "user", "content": student_message})

    raw = _call_llm(messages, max_tokens=150)

    try:
        result = json.loads(_strip_fences(raw))
        reply = _truncate(_sanitize(str(result.get("reply", ""))), 155)
        is_answer = bool(result.get("is_answer", False))
        score = result.get("score")
        if score is not None:
            score = max(0.0, min(1.0, float(score)))
        if reply:
            return {"reply": reply, "is_answer": is_answer, "score": score}
    except (json.JSONDecodeError, Exception) as e:
        print(f"[LLM] Failed to parse reply JSON: {e}\nRaw: {raw}")

    # Fallback: treat raw as plain reply
    reply = _truncate(_sanitize(raw.strip()), 155)
    return {
        "reply": reply or "Send your answer and I will help you learn!",
        "is_answer": False,
        "score": None,
    }


# ── Context summarization ────────────────────────────

def summarize_history(
    existing: str | None,
    student_msg: str,
    tutor_reply: str,
) -> str:
    """Smart rolling context window. Uses LLM summarization when history grows large."""
    entry = f"S:{student_msg[:60]}|T:{tutor_reply[:60]}"
    if existing:
        combined = f"{existing}|{entry}"
    else:
        combined = entry

    # If under limit, keep as-is
    if len(combined) <= 800:
        return combined

    # Use LLM to summarize older exchanges, keeping recent ones verbatim
    parts = combined.split("|")
    # Keep the 4 most recent parts (2 exchanges) verbatim
    recent = "|".join(parts[-4:]) if len(parts) >= 4 else combined
    older = "|".join(parts[:-4]) if len(parts) > 4 else ""

    if not older:
        return combined[-800:]

    summary_prompt = f"""\
Summarize these tutor-student SMS exchanges into a brief context note (under 200 chars).
Keep key facts: what topics were covered, what the student got right/wrong, current difficulty level.
Plain text only, no labels.

Exchanges: {older}
"""
    summary = _call_llm([
        {"role": "system", "content": summary_prompt},
        {"role": "user", "content": "Write the summary now."},
    ], max_tokens=80, temperature=0.3)

    summary_clean = _sanitize(summary.strip())[:200]
    result = f"[Summary: {summary_clean}]|{recent}" if summary_clean else recent
    return result[-800:]


# ── Class insights (LLM-powered analytics) ───────────

def generate_class_insights(stats_data: dict) -> dict:
    """Generate LLM-powered class analytics insights for instructors."""
    system = f"""\
You are an education analytics assistant. Analyze the following class performance data
and provide actionable insights for the instructor.

CLASS DATA:
{json.dumps(stats_data, indent=2, default=str)}

Return a JSON object with:
- "summary": 1-2 sentence overview of class performance (under 200 chars)
- "at_risk": array of strings, each identifying a student needing attention with reason (max 3)
- "strengths": array of strings highlighting top performers or positive trends (max 3)
- "recommendations": array of 2-3 actionable suggestions for the instructor

Return ONLY the JSON object, no other text.
"""
    raw = _call_llm([
        {"role": "system", "content": system},
        {"role": "user", "content": "Analyze the data and generate insights now."},
    ], max_tokens=400, temperature=0.4)

    try:
        result = json.loads(_strip_fences(raw))
        return {
            "summary": str(result.get("summary", ""))[:200],
            "at_risk": [str(s)[:100] for s in result.get("at_risk", [])][:5],
            "strengths": [str(s)[:100] for s in result.get("strengths", [])][:5],
            "recommendations": [str(s)[:150] for s in result.get("recommendations", [])][:5],
        }
    except (json.JSONDecodeError, Exception) as e:
        print(f"[LLM] Failed to parse insights: {e}\nRaw: {raw}")
        return {
            "summary": "Unable to generate insights at this time.",
            "at_risk": [],
            "strengths": [],
            "recommendations": [],
        }


# ── Cluster insights (LLM-powered per-cluster analytics) ─

def generate_cluster_insights(cluster_data: dict) -> dict:
    """Generate LLM-powered insights for a specific student cluster."""
    system = f"""\
You are an education analytics assistant analyzing a specific student cluster
in the Kenyan CBC (Competency-Based Curriculum) system.

CLUSTER DATA:
{json.dumps(cluster_data, indent=2, default=str)}

Return a JSON object with:
- "summary": 1-2 sentence cluster performance overview (under 200 chars)
- "strengths": array of up to 3 strings highlighting what this cluster does well
- "weaknesses": array of up to 3 strings identifying areas needing improvement
- "recommendations": array of 2-3 actionable teaching suggestions for this cluster
- "suggested_topics": array of 1-2 topic/subject suggestions the instructor should focus on next

Return ONLY the JSON object, no other text.
"""
    raw = _call_llm([
        {"role": "system", "content": system},
        {"role": "user", "content": "Analyze this cluster and generate insights now."},
    ], max_tokens=400, temperature=0.4)

    try:
        result = json.loads(_strip_fences(raw))
        return {
            "summary": str(result.get("summary", ""))[:200],
            "strengths": [str(s)[:100] for s in result.get("strengths", [])][:3],
            "weaknesses": [str(s)[:100] for s in result.get("weaknesses", [])][:3],
            "recommendations": [str(s)[:150] for s in result.get("recommendations", [])][:3],
            "suggested_topics": [str(s)[:80] for s in result.get("suggested_topics", [])][:2],
        }
    except (json.JSONDecodeError, Exception) as e:
        print(f"[LLM] Failed to parse cluster insights: {e}\nRaw: {raw}")
        return {
            "summary": "Unable to generate cluster insights at this time.",
            "strengths": [], "weaknesses": [],
            "recommendations": [], "suggested_topics": [],
        }
