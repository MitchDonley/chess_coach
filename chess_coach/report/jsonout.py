from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone

from ..openings.recommend import OpeningRecommendation
from ..openings.repertoire import OpeningStats
from ..puzzles import Puzzle


def _puzzle_dict(p: Puzzle) -> dict:
    return {
        "fen": p.fen,
        "side_to_move": p.side_to_move,
        "best_line_uci": p.best_line_uci,
        "eval_before_cp": p.eval_before_cp,
        "eval_after_played_cp": p.eval_after_played_cp,
        "cp_loss": p.cp_loss,
        "severity": p.severity,
        "themes": p.themes,
        "game_url": p.game_url,
        "ply": p.ply,
        "played_move_uci": p.played_move_uci,
        "played_move_san": p.played_move_san,
        "best_move_san": p.best_move_san,
        "clock_seconds": p.clock_seconds,
        "time_pressure": p.time_pressure,
        "analysis_url": p.analysis_url,
    }


def _stats_dict(s: OpeningStats) -> dict:
    return {
        "eco": s.eco,
        "name": s.name,
        "color": s.color,
        "games": s.games,
        "wins": s.wins,
        "losses": s.losses,
        "draws": s.draws,
        "score_pct": round(s.score_pct, 1),
        "avg_early_cpl": round(s.avg_early_cpl, 1),
        "sample_urls": s.sample_urls,
        "is_weak": s.is_weak,
    }


def _rec_dict(r: OpeningRecommendation) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "color": r.color,
        "eco": r.eco,
        "main_line": r.main_line,
        "key_ideas": r.key_ideas,
        "traps": r.traps,
        "style_tags": r.style_tags,
        "counters_to": r.counters_to,
        "lichess_study": r.lichess_study,
        "rationale": r.rationale,
    }


def render(
    period_from: str,
    period_to: str,
    all_puzzles: list[Puzzle],
    repertoire: dict[str, list[OpeningStats]],
    recommendations: list[OpeningRecommendation],
    stats: dict,
    cfg,
) -> str:
    doc = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": {
            "from": period_from,
            "to": period_to,
            "lookback_days": cfg.lookback_days,
        },
        "config_snapshot": {
            "username": cfg.chesscom.username,
            "time_classes": cfg.time_classes,
            "engine_depth": cfg.stockfish.depth,
            "min_cp_loss": cfg.puzzles.min_cp_loss,
        },
        "stats": stats,
        "puzzles": [_puzzle_dict(p) for p in all_puzzles],
        "repertoire": {
            color: [_stats_dict(s) for s in stats_list if s.games >= 1]
            for color, stats_list in repertoire.items()
        },
        "recommendations": [_rec_dict(r) for r in recommendations],
    }
    return json.dumps(doc, indent=2)
