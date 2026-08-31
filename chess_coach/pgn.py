from __future__ import annotations

import io
import re
from dataclasses import dataclass

import chess
import chess.pgn

from .fetch import GameRecord


_CLK_RE = re.compile(r"\[%clk\s+(\d+):(\d+):(\d+(?:\.\d+)?)\]")


def _parse_clock(comment: str) -> int | None:
    m = _CLK_RE.search(comment)
    if not m:
        return None
    h, mins, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return int(h * 3600 + mins * 60 + s)


@dataclass
class MoveRecord:
    ply: int             # half-move number (1-indexed from game start)
    board_before: chess.Board
    move: chess.Move
    san: str
    uci: str
    clock_seconds: int | None  # player's clock before this move, None if not annotated


def parse_game(record: GameRecord) -> tuple[chess.pgn.Game | None, list[MoveRecord]]:
    game = chess.pgn.read_game(io.StringIO(record.pgn))
    if game is None:
        return None, []

    player_color = chess.WHITE if record.player_color == "white" else chess.BLACK
    moves: list[MoveRecord] = []
    board = game.board()
    ply = 0

    for node in game.mainline():
        ply += 1
        move = node.move
        san = board.san(move)
        uci = move.uci()
        board_before = board.copy()

        clock = None
        if board.turn == player_color:
            clock = _parse_clock(node.comment)

        moves.append(MoveRecord(
            ply=ply,
            board_before=board_before,
            move=move,
            san=san,
            uci=uci,
            clock_seconds=clock,
        ))
        board.push(move)

    return game, moves


def eco_from_game(game: chess.pgn.Game) -> tuple[str, str]:
    eco = game.headers.get("ECO", "")
    eco_url = game.headers.get("ECOUrl", "")
    name = eco_url.split("/")[-1].replace("-", " ").title() if eco_url else eco
    return eco, name


def opening_moves_key(game: chess.pgn.Game, max_ply: int = 12) -> str:
    board = game.board()
    moves = []
    for i, node in enumerate(game.mainline()):
        if i >= max_ply:
            break
        moves.append(node.move.uci())
        board.push(node.move)
    return " ".join(moves)
