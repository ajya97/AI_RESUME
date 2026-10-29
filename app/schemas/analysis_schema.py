"""
Pydantic schema for the deep resume analysis produced by the LLM chain.

The field names and nesting intentionally match the JSON contract the
frontend (static/js/pages/analyze.js) already expects, so no frontend
changes are required.
"""

from typing import List
from pydantic import BaseModel, Field


class RecommendedSkill(BaseModel):
    skill: str = Field(description="Name of the skill to learn")
    reason: str = Field(description="Why this skill matters for the candidate's target role")
    resource: str = Field(description="A platform or resource to learn it (e.g. Coursera, official docs)")


class SkillGapAnalysis(BaseModel):
    strong_skills: List[str] = Field(default_factory=list)
    weak_areas: List[str] = Field(default_factory=list)
    missing_critical_skills: List[str] = Field(default_factory=list)
    recommended_skills_to_learn: List[RecommendedSkill] = Field(default_factory=list)


class KeywordRecommendations(BaseModel):
    missing_ats_keywords: List[str] = Field(default_factory=list)
    recommended_technical_keywords: List[str] = Field(default_factory=list)
    industry_keywords: List[str] = Field(default_factory=list)
    role_specific_keywords: List[str] = Field(default_factory=list)


class ImprovementSuggestion(BaseModel):
    priority: str = Field(description="High, Medium, or Low")
    category: str = Field(description="e.g. Content, Skills, Formatting, ATS, Branding")
    suggestion: str = Field(description="A specific, actionable tip")


class InterviewReadiness(BaseModel):
    score: int = Field(ge=0, le=100, description="Interview readiness score out of 100")
    strengths: List[str] = Field(default_factory=list)
    weak_points: List[str] = Field(default_factory=list)
    preparation_tips: List[str] = Field(default_factory=list)


class ResumeAnalysis(BaseModel):
    """Top-level structured output for the /api/upload GPT deep analysis step."""

    target_role: str = Field(description="Detected or most likely target role")
    profile_summary: str = Field(description="2-3 sentence professional summary of this candidate")
    skill_gap_analysis: SkillGapAnalysis
    keyword_recommendations: KeywordRecommendations
    improvement_suggestions: List[ImprovementSuggestion] = Field(default_factory=list)
    interview_readiness: InterviewReadiness
    resume_strength_score: int = Field(ge=0, le=100)
    overall_feedback: str = Field(description="One paragraph of honest, constructive overall feedback")
