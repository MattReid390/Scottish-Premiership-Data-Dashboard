"""Shared match-result arithmetic used by the league table engine and form
guide (see docs/analysis_methodology.md sections 2 and 3). Kept separate so
both modules - and the dashboard's home/away split view - apply identical
win/draw/loss and points rules rather than each re-deriving them.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


def result_letter(goals_for: int, goals_against: int) -> str:
    if goals_for > goals_against:
        return "W"
    if goals_for < goals_against:
        return "L"
    return "D"


RESULT_POINTS = {"W": 3, "D": 1, "L": 0}


@dataclass(frozen=True)
class ResultTotals:
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    @property
    def points(self) -> int:
        return self.wins * RESULT_POINTS["W"] + self.draws * RESULT_POINTS["D"]

    def with_result(self, goals_for: int, goals_against: int) -> ResultTotals:
        outcome = result_letter(goals_for, goals_against)
        return replace(
            self,
            played=self.played + 1,
            wins=self.wins + (outcome == "W"),
            draws=self.draws + (outcome == "D"),
            losses=self.losses + (outcome == "L"),
            goals_for=self.goals_for + goals_for,
            goals_against=self.goals_against + goals_against,
        )
