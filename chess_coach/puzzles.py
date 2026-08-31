from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import chess

from .classify import classify_move
from .config import Config
from .engine import AnalysisResult, Engine, cp_from_player_pov
from .fetch import GameRecord
from .pgn import MoveRecord, parse_game


@dataclass
class Puzzle:
    fen: str
    side_to_move: str            # "w" or "b"
    best_line_uci: list[str]
    eval_before_cp: int          # from player's POV
    eval_after_played_cp: int    # from player's POV
    cp_loss: int
    severity: str
    themes: list[str]
    game_url: str
    ply: int
    played_move_uci: str
    played_move_san: str
    best_move_san: str
    clock_seconds: int | None
    time_pressure: bool
    analysis_url: str


def _build_analysis_url(fen: str, side_to_move: str) -> str:
    encoded = quote(fen, safe="")
    flip = "true" if side_to_move == "b" else "false"
    return f"https://www.chess.com/analysis?fen={encoded}&flip={flip}"


def _is_puzzle_worthy(
    ply: int,
    cp_loss: int,
    pv1_cp: int,
    pv2_cp: int | None,
    pv1_len: int,
    cfg: Config,
) -> bool:
    if ply < cfg.puzzles.skip_book_plies:
        return False
    if cp_loss < cfg.puzzles.min_cp_loss:
        return False
    if pv2_cp is not None and abs(pv1_cp - pv2_cp) < cfg.puzzles.min_pv_gap:
        return False
    if pv1_len < cfg.puzzles.min_pv_length:
        return False
    return True


def extract_puzzles(record: GameRecord, engine: Engine, cfg: Config) -> list[Puzzle]:
    game, move_records = parse_game(record)
    if game is None or not move_records:
        return []

    player_color = chess.WHITE if record.player_color == "white" else chess.BLACK
    puzzles: list[Puzzle] = []

    for mr in move_records:
        board = mr.board_before
        if board.turn != player_color:
            continue

        # Analyze position before player's move (best move from engine)
        before_result = engine.analyze(board)

        # Analyze position after player's actual move
        board_after = board.copy()
        board_after.push(mr.move)
        after_result = engine.analyze(board_after)

        cp_loss, severity, themes = classify_move(board, before_result, after_result, player_color)

        if severity not in ("blunder", "mistake"):
            continue

        time_pressure = (
            mr.clock_seconds is not None
            and mr.clock_seconds < cfg.puzzles.min_clock_seconds
        )

        pv1_pov = cp_from_player_pov(before_result.pv1_cp, player_color)
        pv2_pov = (
            cp_from_player_pov(before_result.pv2_cp, player_color)
            if before_result.pv2_cp is not None
            else None
        )

        if not _is_puzzle_worthy(
            mr.ply, cp_loss, pv1_pov, pv2_pov, len(before_result.pv1_uci), cfg
        ):
            continue

        fen = board.fen()
        side = "w" if board.turn == chess.WHITE else "b"

        best_move_san = ""
        if before_result.pv1_uci:
            try:
                best_move = chess.Move.from_uci(before_result.pv1_uci[0])
                best_move_san = board.san(best_move)
            except Exception:
                pass

        puzzles.append(Puzzle(
            fen=fen,
            side_to_move=side,
            best_line_uci=before_result.pv1_uci,
            eval_before_cp=pv1_pov,
            eval_after_played_cp=cp_from_player_pov(after_result.pv1_cp, player_color),
            cp_loss=cp_loss,
            severity=severity,
            themes=themes,
            game_url=record.url,
            ply=mr.ply,
            played_move_uci=mr.uci,
            played_move_san=mr.san,
            best_move_san=best_move_san,
            clock_seconds=mr.clock_seconds,
            time_pressure=time_pressure,
            analysis_url=_build_analysis_url(fen, side),
        ))

    # Sort by cp_loss descending — biggest blunders first
    puzzles.sort(key=lambda p: p.cp_loss, reverse=True)
    return puzzles
