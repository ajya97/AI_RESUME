"""
Interview Service
LangChain chains for generating interview questions from a resume (and
optionally a job description) and for evaluating a candidate's answer.
"""

from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser

from app.core.exceptions import AIOutputError
from app.prompts.formatting import format_candidate_context, format_interview_resume_summary
from app.prompts.interview_prompts import answer_evaluation_prompt, question_generation_prompt
from app.schemas.interview_schema import AnswerEvaluation, InterviewQuestionSet
from app.services.ai_parsing import parse_model_output
from app.services.llm_client import get_chat_model, invoke_chain

DIFFICULTIES = ("Easy", "Medium", "Hard", "Mixed")
CATEGORIES = ("Technical", "HR", "Project-Based", "Scenario-Based")

_DIFFICULTY_TEXT = {
    "Easy": "all questions Easy (fundamentals, entry-level).",
    "Medium": "all questions Medium.",
    "Hard": "all questions Hard (deep, senior-level reasoning).",
    "Mixed": "a balanced mix of Easy, Medium and Hard.",
}


def generate_interview_questions(parsed: dict, difficulty: str = "Mixed",
                                 job_description: str | None = None) -> dict:
    """Generate 16 categorised questions (4 each: Technical, HR, Project-Based,
    Scenario-Based) from resume content, optionally tailored to a job description."""
    difficulty = difficulty if difficulty in DIFFICULTIES else "Mixed"
    llm = get_chat_model(temperature=0.6, max_tokens=9000)
    parser = PydanticOutputParser(pydantic_object=InterviewQuestionSet)
    chain = question_generation_prompt | llm | StrOutputParser()

    jd = (job_description or "").strip()
    raw = invoke_chain(chain, {
        "resume_summary": format_interview_resume_summary(parsed),
        "format_instructions": parser.get_format_instructions(),
        "total": 16, "per_category": 4,
        "difficulty_instruction": _DIFFICULTY_TEXT[difficulty],
        "jd_clause": " and the job description" if jd else "",
        "jd_block": f"\n<job_description>\n{jd}\n</job_description>\n" if jd else "",
    })
    result = parse_model_output(raw, InterviewQuestionSet)
    questions = result.get("questions") or []
    if not questions:
        raise AIOutputError("The AI did not return any interview questions. Your credits were refunded.")
    # normalise ids so the frontend/DB can rely on 1..N
    for i, q in enumerate(questions, start=1):
        q["id"] = i
    result["questions"] = questions
    print(f"Generated {len(questions)} questions (difficulty={difficulty}, job_description={'present' if jd else 'absent'})")
    return result


def evaluate_answer(question: str, answer: str, category: str, parsed_resume: dict) -> dict:
    """Evaluate a candidate's answer; returns score (0-10), feedback, and a model answer.

    Uses the dedicated EVALUATION_MODEL_NAME (default "gpt-4o-mini"), as the
    original implementation did."""
    from flask import current_app

    llm = get_chat_model(model_name=current_app.config.get("EVALUATION_MODEL_NAME"),
                         temperature=0.3, max_tokens=2000)
    parser = PydanticOutputParser(pydantic_object=AnswerEvaluation)
    chain = answer_evaluation_prompt | llm | StrOutputParser()

    raw = invoke_chain(chain, {
        "candidate_context": format_candidate_context(parsed_resume),
        "category": category, "question": question, "answer": answer,
        "format_instructions": parser.get_format_instructions(),
    })
    return parse_model_output(raw, AnswerEvaluation)
