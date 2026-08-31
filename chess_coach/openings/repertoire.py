from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import chess.pgn

from ..fetch import GameRecord
from ..pgn import eco_from_game, opening_moves_key, parse_game


@dataclass
class OpeningStats:
    eco: str
    name: str
    color: str
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    total_early_cpl: float = 0.0
    early_cpl_count: int = 0
    sample_urls: list[str] = field(default_factory=list)

    @property
    def score_pct(self) -> float:
        if self.games == 0:
            return 0.0
        return (self.wins + 0.5 * self.draws) / self.games * 100

    @property
    def avg_early_cpl(self) -> float:
        if self.early_cpl_count == 0:
            return 0.0
        return self.total_early_cpl / self.early_cpl_count

    @property
    def is_weak(self) -> bool:
        return (self.games >= 5 and self.score_pct < 40) or (
            self.early_cpl_count >= 5 and self.avg_early_cpl > 50
        )


def build_repertoire(
    records: list[GameRecord],
    move_analyses: dict[str, list] | None = None,
) -> dict[str, list[OpeningStats]]:
    stats_by_color: dict[str, dict[str, OpeningStats]] = {
        "white": defaultdict(lambda: OpeningStats(eco="", name="", color="white")),
        "black": defaultdict(lambda: OpeningStats(eco="", name="", color="black")),
    }

    for record in records:
        game, move_records = parse_game(record)
        if game is None:
            continue

        eco, name = eco_from_game(game)
        if not eco:
            continue

        color = record.player_color
        key = eco  # group by ECO code

        s = stats_by_color[color][key]
        s.eco = eco
        s.name = name
        s.color = color
        s.games += 1

        if record.result == "win":
            s.wins += 1
        elif record.result == "loss":
            s.losses += 1
        else:
            s.draws += 1

        if len(s.sample_urls) < 3 and record.url:
            s.sample_urls.append(record.url)

    result: dict[str, list[OpeningStats]] = {}
    for color, stats_map in stats_by_color.items():
        entries = sorted(stats_map.values(), key=lambda s: s.games, reverse=True)
        result[color] = entries

    return result
