from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..config import Config
from .repertoire import OpeningStats


@dataclass
class OpeningRecommendation:
    id: str
    name: str
    color: str
    eco: str
    main_line: list[str]
    key_ideas: list[str]
    traps: list[dict[str, Any]]
    style_tags: list[str]
    counters_to: list[str]
    lichess_study: str
    rationale: str = ""


def load_curated(cfg: Config) -> list[dict]:
    path = cfg.resolve(cfg.openings.curated_file)
    if not path.exists():
        return []
    with open(path) as f:
        data = yaml.safe_load(f) or []
    return data if isinstance(data, list) else []


def _opening_eco_family(eco: str) -> str:
    return eco[0] if eco else ""


def recommend_openings(
    cfg: Config,
    repertoire: dict[str, list[OpeningStats]],
) -> list[OpeningRecommendation]:
    curated = load_curated(cfg)
    if not curated:
        return []

    # Build set of ECOs the user already plays (by color)
    played: dict[str, set[str]] = {"white": set(), "black": set()}
    weak_families: dict[str, set[str]] = {"white": set(), "black": set()}

    for color, stats_list in repertoire.items():
        for s in stats_list:
            if s.games >= 3:
                played[color].add(s.eco)
            if s.is_weak:
                weak_families[color].add(_opening_eco_family(s.eco))

    scored: list[tuple[int, dict]] = []
    for entry in curated:
        color = entry.get("color", "")
        eco = entry.get("eco", "")
        style_tags = entry.get("style_tags", [])
        counters_to = entry.get("counters_to", [])

        score = 0
        rationale_parts: list[str] = []

        # +3 if not in user's current repertoire
        if eco not in played.get(color, set()):
            score += 3
            rationale_parts.append("not in your current repertoire")

        # +2 if it counters / replaces a weak opening family
        family = _opening_eco_family(eco)
        if family in weak_families.get(color, set()):
            score += 2
            rationale_parts.append(f"could replace a weak {family}-family opening")

        # +1 if it has style_tags that complement (heuristic: solid/positional always good)
        if "solid" in style_tags or "positional" in style_tags:
            score += 1
            rationale_parts.append("solid/positional — good for building consistency")

        if score > 0:
            entry = dict(entry)
            entry["_score"] = score
            entry["_rationale"] = "; ".join(rationale_parts) if rationale_parts else "worth exploring"
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[: cfg.openings.recommendations_per_run]

    recommendations = []
    for _, entry in top:
        recommendations.append(OpeningRecommendation(
            id=entry.get("id", ""),
            name=entry.get("name", ""),
            color=entry.get("color", ""),
            eco=entry.get("eco", ""),
            main_line=entry.get("main_line", []),
            key_ideas=entry.get("key_ideas", []),
            traps=entry.get("traps", []),
            style_tags=entry.get("style_tags", []),
            counters_to=entry.get("counters_to", []),
            lichess_study=entry.get("lichess_study", ""),
            rationale=entry.get("_rationale", ""),
        ))

    return recommendations
