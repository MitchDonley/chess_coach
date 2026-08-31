from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import Config


@dataclass
class GameRecord:
    game_id: str
    url: str
    pgn: str
    time_class: str
    time_control: str
    end_time: int
    white_username: str
    black_username: str
    player_color: str  # "white" or "black"
    result: str  # "win", "loss", "draw" from player's perspective


def _session(contact_email: str) -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = f"chess-coach/0.1 (contact: {contact_email})"
    return s


def _archive_cache_path(pgn_dir: Path, username: str, year: int, month: int) -> Path:
    return pgn_dir / f"{username}-{year:04d}-{month:02d}.json"


def _is_current_month(year: int, month: int) -> bool:
    now = datetime.now(timezone.utc)
    return now.year == year and now.month == month


def _parse_result(game: dict, username: str) -> tuple[str, str]:
    white = game.get("white", {})
    black = game.get("black", {})
    white_name = white.get("username", "").lower()
    black_name = black.get("username", "").lower()
    user = username.lower()

    if white_name == user:
        color = "white"
        result_raw = white.get("result", "")
    else:
        color = "black"
        result_raw = black.get("result", "")

    if result_raw == "win":
        result = "win"
    elif result_raw in ("checkmated", "timeout", "resigned", "lose", "abandoned", "kingofthehill",
                         "threecheck", "bughousepartnerlose", "timevsinsufficient"):
        result = "loss"
    else:
        result = "draw"

    return color, result


def list_archives(cfg: Config, session: requests.Session) -> list[str]:
    url = f"https://api.chess.com/pub/player/{cfg.chesscom.username}/games/archives"
    resp = session.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json().get("archives", [])


def _fetch_archive_raw(url: str, session: requests.Session) -> list[dict]:
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json().get("games", [])


def _load_or_fetch_archive(
    url: str,
    year: int,
    month: int,
    cfg: Config,
    session: requests.Session,
) -> list[dict]:
    pgn_dir = cfg.resolve(cfg.cache.pgn_dir)
    pgn_dir.mkdir(parents=True, exist_ok=True)
    cache_path = _archive_cache_path(pgn_dir, cfg.chesscom.username, year, month)

    if cache_path.exists() and not _is_current_month(year, month):
        with open(cache_path) as f:
            return json.load(f)

    games = _fetch_archive_raw(url, session)
    with open(cache_path, "w") as f:
        json.dump(games, f)
    return games


def recent_games(cfg: Config, verbose: bool = False) -> list[GameRecord]:
    session = _session(cfg.chesscom.contact_email)
    cutoff_ts = int(time.time()) - cfg.lookback_days * 86400

    archives = list_archives(cfg, session)

    records: list[GameRecord] = []
    for archive_url in archives:
        parts = archive_url.rstrip("/").split("/")
        year, month = int(parts[-2]), int(parts[-1])
        archive_cutoff = datetime(year, month, 1, tzinfo=timezone.utc).timestamp()
        if archive_cutoff + 31 * 86400 < cutoff_ts:
            continue

        if verbose:
            print(f"  Fetching archive {year}-{month:02d}...")

        raw_games = _load_or_fetch_archive(archive_url, year, month, cfg, session)

        for g in raw_games:
            if g.get("rules") != "chess":
                continue
            if g.get("time_class") not in cfg.time_classes:
                continue
            end_time = g.get("end_time", 0)
            if end_time < cutoff_ts:
                continue
            pgn = g.get("pgn", "")
            if not pgn or pgn.count("\n") < 4:
                continue

            white_user = g.get("white", {}).get("username", "")
            black_user = g.get("black", {}).get("username", "")
            user = cfg.chesscom.username.lower()
            if white_user.lower() != user and black_user.lower() != user:
                continue

            color, result = _parse_result(g, cfg.chesscom.username)
            game_url = g.get("url", "")
            game_id = game_url.split("/")[-1] if game_url else str(end_time)

            records.append(GameRecord(
                game_id=game_id,
                url=game_url,
                pgn=pgn,
                time_class=g.get("time_class", ""),
                time_control=g.get("time_control", ""),
                end_time=end_time,
                white_username=white_user,
                black_username=black_user,
                player_color=color,
                result=result,
            ))

    records.sort(key=lambda g: g.end_time)
    return records
