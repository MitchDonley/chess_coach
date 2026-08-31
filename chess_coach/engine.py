from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import chess
import chess.engine

from .config import Config

MATE_CP = 10000
CLIP_CP = 2000


@dataclass
class AnalysisResult:
    fen: str
    depth: int
    pv1_cp: int       # centipawns from White's POV (mate clamped to ±MATE_CP)
    pv2_cp: int | None
    pv1_uci: list[str]
    is_mate: bool


def _score_to_cp(score: chess.engine.Score) -> int:
    if score.is_mate():
        mate_in = score.mate()
        return MATE_CP if mate_in is not None and mate_in > 0 else -MATE_CP
    cp = score.score()
    return max(-CLIP_CP, min(CLIP_CP, cp)) if cp is not None else 0


def _init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis (
            fen TEXT NOT NULL,
            depth INTEGER NOT NULL,
            pv1_cp INTEGER NOT NULL,
            pv2_cp INTEGER,
            pv1_uci TEXT NOT NULL,
            is_mate INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (fen, depth)
        )
    """)
    conn.commit()
    return conn


def _cache_get(conn: sqlite3.Connection, fen: str, depth: int) -> AnalysisResult | None:
    row = conn.execute(
        "SELECT pv1_cp, pv2_cp, pv1_uci, is_mate FROM analysis WHERE fen=? AND depth=?",
        (fen, depth),
    ).fetchone()
    if row is None:
        return None
    pv1_cp, pv2_cp, pv1_uci_str, is_mate = row
    return AnalysisResult(
        fen=fen,
        depth=depth,
        pv1_cp=pv1_cp,
        pv2_cp=pv2_cp,
        pv1_uci=pv1_uci_str.split() if pv1_uci_str else [],
        is_mate=bool(is_mate),
    )


def _cache_put(conn: sqlite3.Connection, result: AnalysisResult) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO analysis (fen, depth, pv1_cp, pv2_cp, pv1_uci, is_mate)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            result.fen,
            result.depth,
            result.pv1_cp,
            result.pv2_cp,
            " ".join(result.pv1_uci),
            int(result.is_mate),
        ),
    )
    conn.commit()


class Engine:
    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._engine: chess.engine.SimpleEngine | None = None
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> Engine:
        db_path = self._cfg.resolve(self._cfg.cache.analysis_db)
        self._conn = _init_db(db_path)
        self._engine = chess.engine.SimpleEngine.popen_uci(self._cfg.stockfish.path)
        self._engine.configure({
            "Threads": self._cfg.stockfish.threads,
            "Hash": self._cfg.stockfish.hash_mb,
        })
        return self

    def __exit__(self, *_) -> None:
        if self._engine:
            self._engine.quit()
        if self._conn:
            self._conn.close()

    def analyze(self, board: chess.Board) -> AnalysisResult:
        fen = board.fen()
        depth = self._cfg.stockfish.depth
        multipv = self._cfg.stockfish.multipv

        cached = _cache_get(self._conn, fen, depth)
        if cached is not None:
            return cached

        info_list = self._engine.analyse(
            board,
            chess.engine.Limit(depth=depth),
            multipv=multipv,
        )

        pv1 = info_list[0]
        pv1_score = pv1["score"].white()
        pv1_cp = _score_to_cp(pv1_score)
        pv1_uci = [m.uci() for m in pv1.get("pv", [])]
        is_mate = pv1_score.is_mate()

        pv2_cp: int | None = None
        if len(info_list) > 1:
            pv2_cp = _score_to_cp(info_list[1]["score"].white())

        result = AnalysisResult(
            fen=fen,
            depth=depth,
            pv1_cp=pv1_cp,
            pv2_cp=pv2_cp,
            pv1_uci=pv1_uci,
            is_mate=is_mate,
        )
        _cache_put(self._conn, result)
        return result


def cp_from_player_pov(cp_white: int, player_color: chess.Color) -> int:
    return cp_white if player_color == chess.WHITE else -cp_white
