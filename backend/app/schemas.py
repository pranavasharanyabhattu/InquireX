"""The API contract. app.js in /frontend expects exactly these shapes."""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class DocInfo(BaseModel):
    id: str
    name: str
    pages: int


class Source(BaseModel):
    doc_name: str
    page: Optional[int] = None
    snippet: str
    highlight: Optional[str] = None   # exact phrase inside snippet to mark in yellow


class Conflict(BaseModel):
    summary: str
    sources: list[Source]


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    document_ids: list[str] = Field(default_factory=list)  # empty = search all documents


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    document_ids: list[str] = Field(default_factory=list)


class AccountLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=24, pattern=r"^[A-Za-z0-9_]+$")


class AccountHistoryRequest(BaseModel):
    investigations: list[dict] = Field(default_factory=list, max_length=500)


class AskResponse(BaseModel):
    answer: str
    answer_mode: Literal["generated", "source_only", "insufficient_evidence"] = "generated"
    fallback_reason: Optional[str] = None
    confidence: Literal["high", "medium", "low"]
    confidence_reason: str = ""
    insufficient_evidence: bool = False
    conflict_check_available: bool = True
    sources: list[Source] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
