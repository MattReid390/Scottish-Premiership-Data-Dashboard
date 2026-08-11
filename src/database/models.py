"""SQLAlchemy ORM models for the Phase 1 schema.

Mirrors docs/database_schema.md sections 3.1-3.4 and 3.9 (season, team, venue,
match, ingestion_log). The derived/summary tables described in the schema doc
(team_season_stats, league_table_snapshot, team_rating, match_event) are
introduced later, once the analysis layer that populates them exists.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Season(Base):
    """A single league season, e.g. "2025-26"."""

    __tablename__ = "season"

    season_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(default=False, nullable=False)

    matches: Mapped[list[Match]] = relationship(back_populates="season")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"Season(id={self.season_id}, label={self.label!r})"


class Venue(Base):
    """A stadium/ground."""

    __tablename__ = "venue"

    venue_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    teams: Mapped[list[Team]] = relationship(back_populates="venue")
    matches: Mapped[list[Match]] = relationship(back_populates="venue")

    def __repr__(self) -> str:  # pragma: no cover
        return f"Venue(id={self.venue_id}, name={self.name!r})"


class Team(Base):
    """A club. Holds all teams observed historically, not just current-season
    Premiership members (see docs/database_schema.md section 3.2)."""

    __tablename__ = "team"

    team_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    canonical_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    venue_id: Mapped[int | None] = mapped_column(
        ForeignKey("venue.venue_id"), nullable=True
    )

    venue: Mapped[Venue | None] = relationship(back_populates="teams")
    home_matches: Mapped[list[Match]] = relationship(
        back_populates="home_team",
        foreign_keys="Match.home_team_id",
    )
    away_matches: Mapped[list[Match]] = relationship(
        back_populates="away_team",
        foreign_keys="Match.away_team_id",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"Team(id={self.team_id}, name={self.name!r})"


class Match(Base):
    """A fixture. The canonical fact table (see docs/database_schema.md
    section 3.4). Uniqueness is enforced on the natural key so repeated
    ingestion runs upsert rather than duplicate fixtures."""

    __tablename__ = "match"
    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "home_team_id",
            "away_team_id",
            "match_date",
            name="uq_match_natural_key",
        ),
        CheckConstraint("home_team_id <> away_team_id", name="ck_match_distinct_teams"),
        CheckConstraint(
            "status IN ('scheduled', 'played', 'postponed', 'abandoned')",
            name="ck_match_status_enum",
        ),
        Index("ix_match_season_matchweek", "season_id", "matchweek"),
        Index("ix_match_home_team", "home_team_id"),
        Index("ix_match_away_team", "away_team_id"),
        Index("ix_match_date", "match_date"),
    )

    match_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("season.season_id"), nullable=False
    )
    match_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    matchweek: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_team_id: Mapped[int] = mapped_column(
        ForeignKey("team.team_id"), nullable=False
    )
    away_team_id: Mapped[int] = mapped_column(
        ForeignKey("team.team_id"), nullable=False
    )
    venue_id: Mapped[int | None] = mapped_column(
        ForeignKey("venue.venue_id"), nullable=True
    )
    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="scheduled")
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    season: Mapped[Season] = relationship(back_populates="matches")
    venue: Mapped[Venue | None] = relationship(back_populates="matches")
    home_team: Mapped[Team] = relationship(
        back_populates="home_matches", foreign_keys=[home_team_id]
    )
    away_team: Mapped[Team] = relationship(
        back_populates="away_matches", foreign_keys=[away_team_id]
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Match(id={self.match_id}, season_id={self.season_id}, "
            f"home={self.home_team_id}, away={self.away_team_id}, "
            f"date={self.match_date}, status={self.status!r})"
        )


class IngestionLog(Base):
    """One row per ingestion run, for operational visibility (see
    docs/data_ingestion.md section 7)."""

    __tablename__ = "ingestion_log"
    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'partial', 'failed')",
            name="ck_ingestion_log_status_enum",
        ),
    )

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    run_started_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    run_finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    records_fetched: Mapped[int | None] = mapped_column(Integer, nullable=True)
    records_loaded: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"IngestionLog(id={self.log_id}, source={self.source!r}, "
            f"status={self.status!r})"
        )
