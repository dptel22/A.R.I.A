"""Structured-output schema for the grounded contract assistant.

The LLM must answer with exactly this shape; deterministic post-validation in
``rag_service`` then checks every citation against the retrieved evidence set.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class RagSource(BaseModel):
    chunk_id: int = Field(description="ID of the evidence chunk that supports the answer")
    page: int = Field(description="1-based page number of the evidence chunk")
    section: str | None = Field(default=None, description="Section heading, if any")
    clause: str | None = Field(default=None, description="Clause number, if any")
    quote: str = Field(description="Short verbatim quote from the evidence supporting the answer")


class RagAnswer(BaseModel):
    answer: str = Field(
        description="Grounded answer. When supported is false, explain what evidence is missing."
    )
    supported: bool = Field(
        description="True only if the retrieved evidence directly answers the question."
    )
    confidence: str = Field(description="One of: high, medium, low")
    sources: list[RagSource] = Field(default_factory=list)
