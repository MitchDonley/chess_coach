from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from ..openings.recommend import OpeningRecommendation
from ..openings.repertoire import OpeningStats
from ..puzzles import Puzzle


def _header(period_from: str, period_to: str, n_games: int, time_classes: list[str]) -> str:
    classes = ", ".join(time_classes)
    return (
        f"# Chess Coach Report — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n"
        f"**Period:** {period_from} → {period_to}  "
        f"**Games analyzed:** {n_games}  "
        f"**Time controls:** {classes}\n"
    )


def _summary(
    wins: int, losses: int, draws: int,
    blunders: int, mistakes: int, inaccuracies: int,
    avg_cpl: float,
    theme_counts: Counter,
    time_pressure_excluded: int,
) -> str:
    total = wins + losses + draws
    score_pct = (wins + 0.5 * draws) / total * 100 if total else 0
    top_themes = ", ".join(t for t, _ in theme_counts.most_common(5) if t not in ("opening", "middlegame", "endgame"))

    lines = [
        "## Summary\n",
        f"- **Record:** {wins}–{losses}–{draws} ({score_pct:.0f}% score)",
        f"- **Blunders:** {blunders}  •  **Mistakes:** {mistakes}  •  **Inaccuracies:** {inaccuracies}",
        f"- **Avg centipawn loss:** {avg_cpl:.0f}",
    ]
    if top_themes:
        lines.append(f"- **Recurring themes:** {top_themes}")
    if time_pressure_excluded:
        lines.append(f"- **Time-pressure mistakes excluded from puzzles:** {time_pressure_excluded}")
    return "\n".join(lines) + "\n"


def _puzzle_card(i: int, puzzle: Puzzle) -> str:
    move_num = (puzzle.ply + 1) // 2
    side = "White" if puzzle.side_to_move == "w" else "Black"
    themes_str = ", ".join(puzzle.themes)
    tp_note = "  *(time-pressure position — kept for reference)*" if puzzle.time_pressure else ""

    return (
        f"### Puzzle {i}: {puzzle.severity.capitalize()} — {themes_str}\n\n"
        f"- **From:** [{side} to move, move {move_num}]({puzzle.game_url})\n"
        f"- **Position:** [Open on chess.com]({puzzle.analysis_url})\n"
        f"- You played: `{puzzle.played_move_san}` → Best: `{puzzle.best_move_san}` "
        f"(eval swing: {puzzle.eval_before_cp:+}cp → {puzzle.eval_after_played_cp:+}cp, "
        f"loss: **{puzzle.cp_loss}cp**){tp_note}\n"
    )


def _puzzles_section(puzzles: list[Puzzle]) -> str:
    if not puzzles:
        return "## Top Puzzles\n\n*No qualifying puzzles found this period. Try lowering `puzzles.min_cp_loss` in config.*\n"

    lines = [f"## Top Puzzles ({len(puzzles)})\n"]
    for i, p in enumerate(puzzles, 1):
        lines.append(_puzzle_card(i, p))
    return "\n".join(lines)


def _repertoire_section(repertoire: dict[str, list[OpeningStats]]) -> str:
    lines = ["## Opening Review\n"]

    for color in ("white", "black"):
        stats_list = [s for s in repertoire.get(color, []) if s.games >= 3]
        if not stats_list:
            continue

        lines.append(f"### As {color.capitalize()}\n")
        lines.append("| ECO | Opening | Games | Score% | Weak? |")
        lines.append("|-----|---------|-------|--------|-------|")

        for s in sorted(stats_list, key=lambda x: x.games, reverse=True)[:15]:
            weak = "⚠️" if s.is_weak else ""
            lines.append(
                f"| {s.eco} | {s.name} | {s.games} | {s.score_pct:.0f}% | {weak} |"
            )
        lines.append("")

    return "\n".join(lines)


def _recommendation_card(rec: OpeningRecommendation) -> str:
    main = " ".join(rec.main_line) if rec.main_line else "—"
    ideas = "\n".join(f"  - {idea}" for idea in rec.key_ideas) if rec.key_ideas else "  - (no notes)"

    trap_section = ""
    if rec.traps:
        trap = rec.traps[0]
        trap_line = " ".join(trap.get("line", []))
        trap_section = (
            f"- **Common trap:** {trap.get('name', '')} — `{trap_line}`\n"
            f"  Response: {trap.get('response', '')}\n"
        )

    study_link = f"- [Lichess study]({rec.lichess_study})\n" if rec.lichess_study else ""

    return (
        f"### {rec.name} ({rec.color.capitalize()}, {rec.eco}) — *{rec.rationale}*\n\n"
        f"- **Main line:** {main}\n"
        f"- **Key ideas:**\n{ideas}\n"
        f"{trap_section}"
        f"{study_link}"
    )


def _recommendations_section(recommendations: list[OpeningRecommendation]) -> str:
    if not recommendations:
        return (
            "## Opening Recommendations\n\n"
            "*No recommendations available. Seed `data/openings.yaml` with curated openings.*\n"
        )

    lines = [f"## Opening Recommendations ({len(recommendations)})\n"]
    for rec in recommendations:
        lines.append(_recommendation_card(rec))
    return "\n".join(lines)


def _notes_section(time_pressure_excluded: int, depth: int) -> str:
    return (
        "## Notes & Limitations\n\n"
        f"- Engine: Stockfish at depth {depth}.\n"
        f"- Time-pressure mistakes (< configured clock threshold) excluded from puzzle list: {time_pressure_excluded}. "
        "They appear in the JSON sidecar with `time_pressure: true`.\n"
        "- Theme tags are heuristic approximations — treat them as hints, not ground truth.\n"
    )


def render(
    period_from: str,
    period_to: str,
    games: list,
    puzzles: list[Puzzle],
    all_puzzles_including_tp: list[Puzzle],
    repertoire: dict[str, list[OpeningStats]],
    recommendations: list[OpeningRecommendation],
    stats: dict,
    cfg,
) -> str:
    time_pressure_excluded = sum(1 for p in all_puzzles_including_tp if p.time_pressure)
    display_puzzles = [p for p in all_puzzles_including_tp if not p.time_pressure][: cfg.puzzles.max_per_report]

    theme_counts: Counter = Counter()
    for p in display_puzzles:
        theme_counts.update(p.themes)

    sections = [
        _header(period_from, period_to, len(games), cfg.time_classes),
        _summary(
            stats["wins"], stats["losses"], stats["draws"],
            stats["blunders"], stats["mistakes"], stats["inaccuracies"],
            stats["avg_cpl"],
            theme_counts,
            time_pressure_excluded,
        ),
        _puzzles_section(display_puzzles),
        _repertoire_section(repertoire),
        _recommendations_section(recommendations),
        _notes_section(time_pressure_excluded, cfg.stockfish.depth),
    ]
    return "\n".join(sections)
