from __future__ import annotations

import chess

from .engine import AnalysisResult, MATE_CP, cp_from_player_pov


PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,
}


def classify_severity(cp_loss: int, eval_before: int, eval_after: int) -> str:
    if eval_before > 200 and eval_after < -100:
        return "blunder"
    if cp_loss >= 300:
        return "blunder"
    if cp_loss >= 100:
        return "mistake"
    if cp_loss >= 50:
        return "inaccuracy"
    return "ok"


def _piece_value(piece_type: chess.PieceType) -> int:
    return PIECE_VALUES.get(piece_type, 0)


def _is_undefended(board: chess.Board, square: chess.Square, color: chess.Color) -> bool:
    return not bool(board.attackers(color, square))


def _detect_themes(
    board_before: chess.Board,
    best_move: chess.Move,
    pv_uci: list[str],
    eval_before_pov: int,
    eval_after_pov: int,
) -> list[str]:
    themes: list[str] = []
    color = board_before.turn

    # Phase
    piece_count = len(board_before.piece_map())
    ply = board_before.fullmove_number * 2 - (1 if color == chess.WHITE else 0)
    if ply <= 20:
        themes.append("opening")
    elif piece_count <= 12:
        themes.append("endgame")
    else:
        themes.append("middlegame")

    # Material context
    if eval_before_pov > 200 and eval_after_pov < -100:
        themes.append("winning_to_losing")
    elif eval_before_pov > 50 and eval_after_pov < -100:
        themes.append("up_material_blundered")

    # Promotion
    if best_move.promotion is not None:
        themes.append("promotion")
        return themes

    # Mate in N
    board_after_best = board_before.copy()
    board_after_best.push(best_move)
    if board_after_best.is_checkmate():
        themes.append("mate_in_1")
        return themes

    if pv_uci:
        best_board = board_before.copy()
        for i, uci in enumerate(pv_uci[:5]):
            try:
                move = chess.Move.from_uci(uci)
                best_board.push(move)
                if best_board.is_checkmate():
                    themes.append(f"mate_in_{i + 1}")
                    return themes
            except Exception:
                break

    # Hanging piece (best move captures undefended piece)
    to_sq = best_move.to_square
    target = board_before.piece_at(to_sq)
    if target and target.color != color:
        if _is_undefended(board_before, to_sq, color):
            themes.append("hanging_piece")
            return themes

    # Fork (after best move, the moving piece attacks 2+ higher-or-equal value enemy pieces)
    moved_piece = board_before.piece_at(best_move.from_square)
    if moved_piece:
        board_after = board_before.copy()
        board_after.push(best_move)
        landing = best_move.to_square
        attacked = board_after.attacks(landing)
        enemy = board_after.occupied_co[not color]
        targets_attacked = []
        for sq in chess.SquareSet(attacked & enemy):
            p = board_after.piece_at(sq)
            if p and _piece_value(p.piece_type) >= _piece_value(moved_piece.piece_type):
                targets_attacked.append(sq)
        if len(targets_attacked) >= 2:
            themes.append("fork")
            return themes

    # Back rank
    if board_after_best.is_check():
        king_sq = board_after_best.king(not color)
        if king_sq is not None:
            king_rank = chess.square_rank(king_sq)
            if king_rank in (0, 7):
                back_rank = 0 if king_rank == 0 else 7
                escape_blocked = True
                for escape in board_after_best.attacks(king_sq):
                    if chess.square_rank(escape) != back_rank:
                        p = board_after_best.piece_at(escape)
                        if p is None or p.color == (not color):
                            escape_blocked = False
                            break
                if escape_blocked:
                    themes.append("back_rank")
                    return themes

    # Pin / skewer (simplified: best move is by a sliding piece that creates a ray attack)
    if moved_piece and moved_piece.piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        board_after = board_before.copy()
        board_after.push(best_move)
        ray_targets = board_after.attacks(best_move.to_square)
        for sq in chess.SquareSet(ray_targets & board_after.occupied_co[not color]):
            p = board_after.piece_at(sq)
            if p is None:
                continue
            behind = chess.SquareSet(chess.ray(best_move.to_square, sq)) & board_after.occupied
            behind_sq = None
            for bsq in behind:
                if bsq != best_move.to_square and bsq != sq:
                    behind_sq = bsq
                    break
            if behind_sq is not None:
                behind_piece = board_after.piece_at(behind_sq)
                if behind_piece and behind_piece.color == (not color):
                    if _piece_value(behind_piece.piece_type) > _piece_value(p.piece_type):
                        themes.append("pin")
                    else:
                        themes.append("skewer")
                    return themes

    return themes


def classify_move(
    board_before: chess.Board,
    best_result: AnalysisResult,
    played_result: AnalysisResult,
    player_color: chess.Color,
) -> tuple[int, str, list[str]]:
    eval_before_pov = cp_from_player_pov(best_result.pv1_cp, player_color)
    eval_after_pov = cp_from_player_pov(played_result.pv1_cp, player_color)
    cp_loss = eval_before_pov - eval_after_pov

    severity = classify_severity(cp_loss, eval_before_pov, eval_after_pov)

    best_move = None
    if best_result.pv1_uci:
        try:
            best_move = chess.Move.from_uci(best_result.pv1_uci[0])
        except Exception:
            pass

    themes: list[str] = []
    if best_move:
        try:
            themes = _detect_themes(
                board_before,
                best_move,
                best_result.pv1_uci,
                eval_before_pov,
                eval_after_pov,
            )
        except Exception:
            themes = ["middlegame"]

    return cp_loss, severity, themes
