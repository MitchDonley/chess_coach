# Chess Coach

A personal coaching tool that turns a player's own chess.com blitz game history into targeted puzzles and opening guidance.

## Language

**Puzzle**:
A position taken from the player's own game, immediately before a move that qualified as a Mistake or Blunder, presented for the player to re-solve on chess.com's analysis board.
_Avoid_: Tactic, exercise

**Blunder**:
A played move with centipawn loss of 300 or more, or one that turns a winning evaluation (>+200) into a losing one (<-100).

**Mistake**:
A played move with centipawn loss between 100 and 299.

**Inaccuracy**:
A played move with centipawn loss between 50 and 99. Counted in summary stats; not currently surfaced as a Puzzle.

**Repertoire**:
The set of openings a player has played at least 3 times within the analysis period, grouped by ECO code and player color, with win/loss/draw performance.

**Adopted Opening**:
An opening that has grown to represent more than 10% of a player's games with a given color within the analysis period. Once adopted, an opening is no longer eligible for recommendation.

**Opening Diversity**:
The count of distinct ECO-code openings a player has used within the analysis period, tracked against the same count for the prior period.

**Weakness Pattern**:
A recurring theme-tag-and-phase combination (e.g. "hanging_piece + middlegame") shared across multiple Puzzles from different games. Tracked over time rather than any single Puzzle instance.
_Avoid_: Recurring mistake, tactic weakness

**Resolved** (of a Weakness Pattern):
No longer classified as active because it has not recurred across the player's 10 most recent subsequent games since it was first flagged.
