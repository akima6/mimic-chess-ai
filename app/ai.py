# app/ai.py

import chess
from pystockfish import Engine
import json
import random

# --- Global AI Engine ---
# This engine is used for post-game analysis. It's powerful but slow.
try:
    analysis_engine = Engine(depth=20)
    print("--- AI Analysis Engine initialized successfully. ---")
except Exception as e:
    print(f"--- FATAL ERROR: Could not initialize AI Analysis Engine. Error: {e} ---")
    analysis_engine = None

# This engine is used for live games. It's faster to ensure a good user experience.
try:
    live_game_engine = Engine(depth=10)
    print("--- AI Live Game Engine initialized successfully. ---")
except Exception as e:
    print(f"--- FATAL ERROR: Could not initialize AI Live Game Engine. Error: {e} ---")
    live_game_engine = None
    
# --- Player Profile Management ---
# This dictionary will act as a live cache for player profiles
# Format: { 'username': { 'aggression': 0.5, ... } }
profile_cache = {}

def analyze_player_style(all_games_for_user):
    """
    Analyzes a user's entire game history to build a profile.
    'all_games_for_user' is a list of GameLog objects from the database.
    """
    if not analysis_engine or not all_games_for_user:
        return {"aggression": 0.2, "precision": 0.8, "piece_preference": {}} # Default profile

    all_player_moves = []
    
    print(f"Analyzing {len(all_games_for_user)} games to build profile...")
    
    # Iterate through every game the user has played
    for game_log in all_games_for_user:
        moves_data = json.loads(game_log.moves_json)
        board = chess.Board()
        
        # Replay the game turn by turn to analyze each of the player's moves
        for i, move_info in enumerate(moves_data):
            # We only analyze the player's moves (assuming player is always White for now)
            if i % 2 == 0:
                # Get a ranked list of all possible moves at that board state
                analysis_engine.setfen(board.fen())
                ranked_moves = [move['Move'] for move in analysis_engine.get_top_moves(count=len(list(board.legal_moves)))]
                
                player_move_san = move_info['move_san']
                try:
                    player_move_uci = board.parse_san(player_move_san).uci()
                    
                    move_rank = ranked_moves.index(player_move_uci) + 1 if player_move_uci in ranked_moves else len(ranked_moves)
                    piece_moved = board.piece_at(board.parse_san(player_move_san).from_square).symbol()
                    
                    # Store the detailed analysis of the player's move
                    all_player_moves.append({
                        "move_rank": move_rank,
                        "total_options": len(ranked_moves),
                        "piece": piece_moved,
                        "is_capture": board.is_capture(board.parse_san(player_move_san)),
                        "is_check": board.gives_check(board.parse_san(player_move_san))
                    })
                except (ValueError, AttributeError):
                    # Handle rare cases where a move might be invalid in the log
                    continue
            
            # Make the move on our internal board to proceed to the next turn
            try:
                board.push_san(move_info['move_san'])
            except ValueError:
                break # Stop analyzing this game if a move is illegal

    # Now, calculate the final profile stats from all the analyzed moves
    if not all_player_moves:
        return {"aggression": 0.2, "precision": 0.8, "piece_preference": {}}

    aggressive_moves = sum(1 for move in all_player_moves if move["is_capture"] or move["is_check"])
    aggression_score = aggressive_moves / len(all_player_moves)
    
    total_rank_percent = sum(move["move_rank"] / move["total_options"] for move in all_player_moves if move["total_options"] > 0)
    avg_rank_percent = total_rank_percent / len(all_player_moves) if len(all_player_moves) > 0 else 0
    
    piece_counts = {}
    for move in all_player_moves:
        piece = move["piece"].upper()
        piece_counts[piece] = piece_counts.get(piece, 0) + 1
        
    final_profile = {
        "aggression": aggression_score,
        "precision": 1.0 - avg_rank_percent,
        "piece_preference": piece_counts
    }
    
    print(f"Profile built successfully: {final_profile}")
    return final_profile

def get_ai_move(board, username):
    """
    The main AI decision function. It uses the player's cached profile.
    """
    if not live_game_engine:
        # Fallback if the engine failed to initialize
        return list(board.legal_moves)[0].uci()

    profile = profile_cache.get(username, {"aggression": 0.2, "precision": 0.8, "piece_preference": {}})
    
    live_game_engine.setfen(board.fen())
    all_moves_ranked = [move['Move'] for move in live_game_engine.get_top_moves(count=len(list(board.legal_moves)))]

    if not all_moves_ranked:
        return list(board.legal_moves)[0].uci()

    # --- Generate Move Probabilities ---
    move_scores = {}
    for i, move_uci in enumerate(all_moves_ranked):
        score = 0.01 # Give all moves a tiny base score
        move = chess.Move.from_uci(move_uci)
        
        # Bonus for aggression
        if (board.is_capture(move) or board.gives_check(move)):
            score += profile['aggression'] * 10
            
        # Bonus for piece preference
        moved_piece = board.piece_at(move.from_square).symbol().upper()
        if moved_piece in profile.get('piece_preference', {}):
            score += profile['piece_preference'][moved_piece] * 0.1
            
        # Penalty based on precision (higher precision means we stick closer to the top moves)
        # We use (1 - precision) so that low precision means more randomness
        score -= (i * (1 - profile['precision'])) 
        
        move_scores[move_uci] = score
    
    # Convert scores to probabilities (simple softmax-like approach)
    # Give higher scores a much higher chance of being picked
    exp_scores = {move: pow(10, score) for move, score in move_scores.items()}
    total_score = sum(exp_scores.values())
    probabilities = {move: score / total_score for move, score in exp_scores.items()}
    
    # Randomly sample a move based on the calculated probabilities
    moves = list(probabilities.keys())
    probs = list(probabilities.values())
    chosen_move = random.choices(moves, weights=probs, k=1)[0]
    
    print(f"AI chose move '{chosen_move}' based on profile for '{username}'")
    return chosen_move