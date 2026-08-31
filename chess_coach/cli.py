from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .config import Config, load
from .engine import Engine
from .fetch import GameRecord, recent_games
from .openings.recommend import recommend_openings
from .openings.repertoire import build_repertoire
from .puzzles import Puzzle, extract_puzzles
from .report import markdown as md_report
from .report import jsonout as json_report


def _notify(title: str, message: str) -> None:
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "{title}"'],
            check=False,
            timeout=5,
        )
    except Exception:
        pass


def _compute_stats(
    records: list[GameRecord],
    all_puzzles: list[Puzzle],
) -> dict:
    wins = sum(1 for r in records if r.result == "win")
    losses = sum(1 for r in records if r.result == "loss")
    draws = sum(1 for r in records if r.result == "draw")
    blunders = sum(1 for p in all_puzzles if p.severity == "blunder")
    mistakes = sum(1 for p in all_puzzles if p.severity == "mistake")
    inaccuracies = 0  # inaccuracies are filtered out before puzzle stage; count separately if needed
    cpls = [p.cp_loss for p in all_puzzles if p.cp_loss > 0]
    avg_cpl = sum(cpls) / len(cpls) if cpls else 0.0
    theme_counts = Counter()
    for p in all_puzzles:
        theme_counts.update(p.themes)
    return {
        "games": len(records),
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "blunders": blunders,
        "mistakes": mistakes,
        "inaccuracies": inaccuracies,
        "avg_cpl": round(avg_cpl, 1),
        "theme_counts": dict(theme_counts.most_common()),
    }


def _run(cfg: Config, specific_game_url: str | None = None) -> None:
    print(f"Fetching games for {cfg.chesscom.username} (last {cfg.lookback_days} days)...")
    all_records = recent_games(cfg, verbose=True)

    if specific_game_url:
        all_records = [r for r in all_records if r.url == specific_game_url]
        if not all_records:
            print(f"Game not found in recent history: {specific_game_url}", file=sys.stderr)
            sys.exit(1)

    print(f"Found {len(all_records)} game(s) to analyze.")

    all_puzzles: list[Puzzle] = []
    with Engine(cfg) as engine:
        for i, record in enumerate(all_records, 1):
            print(f"  [{i}/{len(all_records)}] Analyzing {record.url} ...", end="\r")
            puzzles = extract_puzzles(record, engine, cfg)
            all_puzzles.extend(puzzles)

    print(f"\nFound {len(all_puzzles)} puzzle-worthy position(s).")

    repertoire = build_repertoire(all_records)
    recommendations = recommend_openings(cfg, repertoire)

    stats = _compute_stats(all_records, all_puzzles)

    now = datetime.now(timezone.utc)
    period_to = now.strftime("%Y-%m-%d")
    cutoff_ts = int(time.time()) - cfg.lookback_days * 86400
    period_from = datetime.fromtimestamp(cutoff_ts, tz=timezone.utc).strftime("%Y-%m-%d")

    report_dir = cfg.resolve(cfg.output.reports_dir) / now.strftime("%Y-%m-%d")
    report_dir.mkdir(parents=True, exist_ok=True)
    md_path = report_dir / "report.md"
    json_path = report_dir / "report.json"

    md_content = md_report.render(
        period_from=period_from,
        period_to=period_to,
        games=all_records,
        puzzles=[p for p in all_puzzles if not p.time_pressure],
        all_puzzles_including_tp=all_puzzles,
        repertoire=repertoire,
        recommendations=recommendations,
        stats=stats,
        cfg=cfg,
    )

    json_content = json_report.render(
        period_from=period_from,
        period_to=period_to,
        all_puzzles=all_puzzles,
        repertoire=repertoire,
        recommendations=recommendations,
        stats=stats,
        cfg=cfg,
    )

    md_path.write_text(md_content)
    json_path.write_text(json_content)

    print(f"\nReport written to:\n  {md_path}\n  {json_path}")

    if cfg.output.open_report_after_run:
        try:
            subprocess.run(["open", str(md_path)], check=False)
        except Exception:
            pass
        _notify("Chess Coach", f"Report ready: {now.strftime('%Y-%m-%d')} — {stats['blunders']} blunders found")


def _dry_run_fetch(cfg: Config) -> None:
    print(f"Fetching game list for {cfg.chesscom.username} (last {cfg.lookback_days} days, NO engine analysis)...")
    records = recent_games(cfg, verbose=True)
    print(f"\n{len(records)} game(s) match filter:")
    for r in records:
        print(f"  {r.url}  [{r.time_class}] {r.player_color} {r.result}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="chess-coach",
        description="Analyze your chess.com games and generate a coaching report.",
    )
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="Override lookback_days from config",
    )
    parser.add_argument(
        "--only-game",
        metavar="URL",
        default=None,
        help="Analyze a single chess.com game URL (for debugging)",
    )
    parser.add_argument(
        "--dry-run-fetch",
        action="store_true",
        help="List games that would be analyzed without running Stockfish",
    )

    args = parser.parse_args()

    config_path = args.config
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    cfg = load(config_path)

    if args.lookback_days is not None:
        cfg.lookback_days = args.lookback_days

    if args.dry_run_fetch:
        _dry_run_fetch(cfg)
    else:
        _run(cfg, specific_game_url=args.only_game)
