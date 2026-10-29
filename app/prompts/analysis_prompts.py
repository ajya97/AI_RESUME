"""LangChain prompt template for the deep resume analysis chain."""

from langchain_core.prompts import ChatPromptTemplate

from app.prompts.guard import UNTRUSTED_NOTE

RESUME_ANALYSIS_SYSTEM_PROMPT = (
    "You are an expert ATS Resume Analyzer, HR recruiter, and career coach. "
    "You always respond with data that strictly matches the requested schema. "
    + UNTRUSTED_NOTE
)

RESUME_ANALYSIS_HUMAN_TEMPLATE = """\
Analyze the following resume data and return a detailed report.

<resume>
{resume_summary}
</resume>

{format_instructions}
"""

resume_analysis_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", RESUME_ANALYSIS_SYSTEM_PROMPT),
        ("human", RESUME_ANALYSIS_HUMAN_TEMPLATE),
    ]
)
