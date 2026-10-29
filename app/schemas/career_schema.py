"""Pydantic schemas for job-match advice and the skill-gap learning plan."""

from typing import List

from pydantic import BaseModel, Field


class RequirementComparison(BaseModel):
    requirement: str
    status: str = Field(description="met, partial, or missing")
    note: str = ""


class TailoredSuggestion(BaseModel):
    section: str = Field(description="Resume section to change, e.g. Summary, Experience, Skills")
    suggestion: str
    example_bullet: str = Field(default="", description="A SUGGESTED bullet, only if true for the candidate")


class JobMatchAdvice(BaseModel):
    summary: str
    requirement_comparison: List[RequirementComparison] = Field(default_factory=list)
    tailored_suggestions: List[TailoredSuggestion] = Field(default_factory=list)
    keywords_to_add: List[str] = Field(default_factory=list)


class LearningItem(BaseModel):
    skill: str
    priority: str = Field(description="High, Medium, or Low")
    why: str
    estimated_weeks: int = Field(default=4, ge=1, le=52)
    resources: List[str] = Field(default_factory=list)
    practice_task: str = ""


class ProjectIdea(BaseModel):
    title: str
    description: str
    skills_practiced: List[str] = Field(default_factory=list)
    difficulty: str = "Intermediate"


class SkillGapPlan(BaseModel):
    summary: str
    learning_plan: List[LearningItem] = Field(default_factory=list)
    project_ideas: List[ProjectIdea] = Field(default_factory=list)
