"""
Resume Analysis Service
LCEL chain (prompt | llm | parser) that sends parsed resume data to the
configured chat model for deep analysis: keyword recommendations, skill-gap
analysis and improvement suggestions.

Behaviour change vs. the original: unparsable model output now raises
AIOutputError (so the caller refunds credits) instead of returning a fake
"Analysis could not be parsed" payload.
"""

from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser

from app.prompts.analysis_prompts import resume_analysis_prompt
from app.prompts.formatting import format_full_resume_summary
from app.schemas.analysis_schema import ResumeAnalysis
from app.services.ai_parsing import parse_model_output
from app.services.llm_client import get_chat_model, invoke_chain


def analyze_resume_with_gpt(parsed: dict) -> dict:
    """Return a dict matching the ResumeAnalysis schema (raises AIProviderError / AIOutputError)."""
    llm = get_chat_model(temperature=0.4, max_tokens=2000)
    parser = PydanticOutputParser(pydantic_object=ResumeAnalysis)
    chain = resume_analysis_prompt | llm | StrOutputParser()

    raw = invoke_chain(chain, {
        "resume_summary": format_full_resume_summary(parsed),
        "format_instructions": parser.get_format_instructions(),
    })
    return parse_model_output(raw, ResumeAnalysis)
