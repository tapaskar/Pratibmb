"""Structured profile data extracted from the user's message corpus."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Relationship:
    """A person the user has a relationship with."""
    person_name: str
    thread_id: str
    thread_name: str
    relation_type: str          # close_friend, family, colleague, acquaintance
    message_count: int
    self_message_count: int
    first_year: int
    last_year: int
    topics: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class LifeEvent:
    """A significant life event detected from messages."""
    year: int
    month: int | None
    event: str
    category: str               # career, relationship, move, education, personal
    confidence: float
    evidence: list[str] = field(default_factory=list)  # sample message texts


@dataclass
class Interest:
    """A topic/interest the user had during a time period."""
    topic: str
    year_start: int
    year_end: int
    intensity: float            # 0-1
    sample_messages: list[str] = field(default_factory=list)


@dataclass
class YearSummary:
    """A summary of what was going on in the user's life that year."""
    year: int
    summary: str
    message_count: int
    top_people: list[str] = field(default_factory=list)
    top_topics: list[str] = field(default_factory=list)


@dataclass
class ThreadSummary:
    """Summary of a conversation thread."""
    thread_id: str
    thread_name: str
    summary: str
    message_count: int
    self_message_count: int
    year_start: int
    year_end: int


@dataclass
class Profile:
    """Complete structured profile of the user."""
    self_name: str
    relationships: list[Relationship] = field(default_factory=list)
    life_events: list[LifeEvent] = field(default_factory=list)
    interests: list[Interest] = field(default_factory=list)
    year_summaries: list[YearSummary] = field(default_factory=list)
    thread_summaries: list[ThreadSummary] = field(default_factory=list)
    communication_style: dict[str, Any] = field(default_factory=dict)

    def get_year_summary(self, year: int) -> YearSummary | None:
        for ys in self.year_summaries:
            if ys.year == year:
                return ys
        return None

    def get_relationships_active_in(self, year: int) -> list[Relationship]:
        return [r for r in self.relationships
                if r.first_year <= year <= r.last_year]

    def get_events_in(self, year: int) -> list[LifeEvent]:
        return [e for e in self.life_events if e.year == year]

    def get_interests_in(self, year: int) -> list[Interest]:
        return [i for i in self.interests
                if i.year_start <= year <= i.year_end]
