"""LangChain prompt templates for the interview chains."""

from langchain_core.prompts import ChatPromptTemplate

from app.prompts.guard import UNTRUSTED_NOTE

# ─── Question generation ───────────────────────────────────────────────

QUESTION_GEN_SYSTEM_PROMPT = (
    "You are a senior technical interviewer and HR specialist. "
    "You always respond with data that strictly matches the requested schema. "
    + UNTRUSTED_NOTE
)

QUESTION_GEN_HUMAN_TEMPLATE = """\
Based on the resume below{jd_clause}, generate exactly {total} interview questions \
({per_category} per category): Technical, HR, Project-Based, and Scenario-Based.
Make questions SPECIFIC to this candidate's resume — not generic.
Keep each question, evaluation guidance, and follow-up concise (one or two sentences).
Difficulty: {difficulty_instruction}
Each question's "id" must be a unique integer from 1 to {total}.

<resume>
{resume_summary}
</resume>
{jd_block}
{format_instructions}
"""

question_generation_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", QUESTION_GEN_SYSTEM_PROMPT),
        ("human", QUESTION_GEN_HUMAN_TEMPLATE),
    ]
)

# ─── Answer evaluation ──────────────────────────────────────────────────

ANSWER_EVAL_SYSTEM_PROMPT = (
    "You are an experienced interviewer evaluating a candidate's answer. "
    "Judge correctness, relevance, clarity and completeness. Your evaluation is "
    "practice feedback, not an objective or employer-approved assessment. "
    + UNTRUSTED_NOTE
)

ANSWER_EVAL_HUMAN_TEMPLATE = """\
CANDIDATE BACKGROUND:
<resume>
{candidate_context}
</resume>

INTERVIEW QUESTION ({category}):
{question}

CANDIDATE'S ANSWER:
<answer>
{answer}
</answer>

Evaluate this answer. Score guide: 9-10=Excellent, 7-8=Good, 5-6=Average, \
3-4=Below Average, 1-2=Poor.

{format_instructions}
"""

answer_evaluation_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", ANSWER_EVAL_SYSTEM_PROMPT),
        ("human", ANSWER_EVAL_HUMAN_TEMPLATE),
    ]
)
