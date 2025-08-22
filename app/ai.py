# app/ai.py (Hybrid AI Brain)
import chess
import requests
import random
import json

# --- NO MORE ENGINE INITIALIZATION! ---

# --- Secondary Brain - Pure Python Evaluation ---
def evaluate_board(board):
    piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
    score = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            value = piece_values[piece.piece_type]
            score += value if piece.color == chess.WHITE else -value
    return score

def get_simple_best_move(board):
    legal_moves = list(board.legal_moves)
    if not legal_moves: return None
    best_move = None
    best_score = -float('inf') if board.turn == chess.WHITE else float('inf')
    for move in legal_moves:
        board.push(move)
        score = evaluate_board(board)
        board.pop()
        if board.turn == chess.WHITE:
            if score > best_score:
                best_score = score
                best_move = move
        else:
            if score < best_score:
                best_score = score
                best_move = move
    return best_move.uci() if best_move else random.choice(legal_moves).uci()

# --- Primary Brain - Lichess API with Smart Fallback ---
def get_ai_move(board):
    api_url = "https://lichess.org/api/cloud-eval"
    params = {"fen": board.fen()}
    try:
        res = requests.get(api_url, params=params, timeout=5)
        res.raise_for_status()
        data = res.json()
        if data and 'pvs' in data and len(data['pvs']) > 0:
            best_move_uci = data['pvs'][0]['moves'].split(' ')[0]
            if chess.Move.from_uci(best_move_uci) in board.legal_moves:
                print(f"Lichess API returned best move: {best_move_uci}")
                return best_move_uci
    except requests.exceptions.RequestException as e:
        print(f"!!! API REQUEST FAILED: {e}. Using fallback AI. !!!")

    print("!!! API failed or returned invalid move. Using pure Python fallback AI. !!!")
    return get_simple_best_move(board)

# We still need the analysis logic for post-game
def analyze_player_style(all_games_for_user):
    # This is a placeholder for now, as we need a reliable engine first.
    # The real analysis would happen offline.
    print(f"Analyzing {len(all_games_for_user)} games to build profile (placeholder)...")
    return {"aggression": 0.5, "precision": 0.5, "piece_preference": {}}