"""
Pydantic schemas for the interview LLM chains: question generation and
answer evaluation. Field names match what static/js/pages/interview.js
already consumes.
"""

from typing import List
from pydantic import BaseModel, Field


class InterviewQuestion(BaseModel):
    id: int
    category: str = Field(description="Technical, HR, Project-Based, or Scenario-Based")
    difficulty: str = Field(description="Easy, Medium, or Hard")
    question: str
    what_to_look_for: str = Field(description="Key points the answer should cover")
    follow_up: str = Field(description="One natural follow-up question")


class InterviewQuestionSet(BaseModel):
    candidate_name: str
    target_role: str
    questions: List[InterviewQuestion] = Field(default_factory=list)


class AnswerEvaluation(BaseModel):
    score: int = Field(ge=0, le=10)
    score_label: str = Field(description="Excellent, Good, Average, Below Average, or Poor")
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    detailed_feedback: str = Field(description="2-3 sentences of constructive feedback")
    model_answer: str = Field(description="A concise example of what an excellent answer would cover")
    tips_for_improvement: str
    follow_up_suggested: bool = True
