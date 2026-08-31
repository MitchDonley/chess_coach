from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ChesscomConfig:
    username: str
    contact_email: str


@dataclass
class StockfishConfig:
    path: str = "/opt/homebrew/bin/stockfish"
    threads: int = 4
    hash_mb: int = 1024
    depth: int = 10
    multipv: int = 2


@dataclass
class PuzzleConfig:
    min_cp_loss: int = 250
    min_pv_gap: int = 150
    min_pv_length: int = 3
    skip_book_plies: int = 6
    min_clock_seconds: int = 15
    max_per_report: int = 15


@dataclass
class OpeningsConfig:
    recommendations_per_run: int = 2
    curated_file: str = "data/openings.yaml"


@dataclass
class OutputConfig:
    reports_dir: str = "reports"
    open_report_after_run: bool = True


@dataclass
class CacheConfig:
    pgn_dir: str = "data/pgn_cache"
    analysis_db: str = "data/analysis_cache.sqlite"


@dataclass
class Config:
    chesscom: ChesscomConfig
    stockfish: StockfishConfig
    puzzles: PuzzleConfig
    openings: OpeningsConfig
    output: OutputConfig
    cache: CacheConfig
    lookback_days: int = 30
    time_classes: list[str] = field(default_factory=lambda: ["blitz"])

    # resolved absolute paths based on config file location
    root_dir: Path = field(default_factory=Path.cwd)

    def resolve(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        return self.root_dir / p


def _load_section(raw: dict, cls: type, key: str, defaults: dict | None = None) -> Any:
    section = raw.get(key, {})
    if defaults:
        for k, v in defaults.items():
            section.setdefault(k, v)
    try:
        return cls(**{k: v for k, v in section.items() if k in cls.__dataclass_fields__})
    except TypeError as e:
        print(f"Config error in [{key}]: {e}", file=sys.stderr)
        sys.exit(1)


def load(path: Path) -> Config:
    if not path.exists():
        print(f"Config file not found: {path}", file=sys.stderr)
        print("Copy config.example.yaml to config.yaml and fill in your details.", file=sys.stderr)
        sys.exit(1)

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    chesscom_raw = raw.get("chesscom", {})
    if not chesscom_raw.get("username"):
        print("Config error: chesscom.username is required", file=sys.stderr)
        sys.exit(1)
    if not chesscom_raw.get("contact_email"):
        print("Config error: chesscom.contact_email is required (chess.com API User-Agent policy)", file=sys.stderr)
        sys.exit(1)

    chesscom = ChesscomConfig(
        username=chesscom_raw["username"],
        contact_email=chesscom_raw["contact_email"],
    )

    cfg = Config(
        chesscom=chesscom,
        stockfish=_load_section(raw, StockfishConfig, "stockfish"),
        puzzles=_load_section(raw, PuzzleConfig, "puzzles"),
        openings=_load_section(raw, OpeningsConfig, "openings"),
        output=_load_section(raw, OutputConfig, "output"),
        cache=_load_section(raw, CacheConfig, "cache"),
        lookback_days=raw.get("lookback_days", 30),
        time_classes=raw.get("time_classes", ["blitz"]),
        root_dir=path.parent.resolve(),
    )

    sf_path = Path(cfg.stockfish.path)
    if not sf_path.exists():
        print(f"Stockfish not found at {sf_path}. Install with: brew install stockfish", file=sys.stderr)
        sys.exit(1)

    return cfg
