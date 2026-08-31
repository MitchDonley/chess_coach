# Source opening recommendations from Lichess, retain AI-authored prose with disclaimer

We replaced the hand-authored `data/openings.yaml` (main lines and stats invented from LLM training data, no verifiable source) with live data from Lichess's canonical `chess-openings` dataset and its free Opening Explorer API for win/draw/loss stats. "Key ideas" and "traps" prose remains AI-authored — no free structured DB supplies narrative explanation — but is now explicitly labeled unverified rather than presented as fact.

Considered: dropping prose entirely for a pure-stats report linking to real master games. Rejected because it made the feature noticeably less useful; the disclaimer approach keeps the narrative value while being honest about provenance.
