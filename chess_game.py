import chess
from stockfish import Stockfish
import os
import time

# (Engine initialization and helper functions are unchanged)
try:
    stockfish = Stockfish(path="stockfish.exe")
    stockfish.set_skill_level(5)
    print("Stockfish engine initialized successfully!")
    time.sleep(1)
except FileNotFoundError:
    print("Error: 'stockfish.exe' not found...")
    exit()

def get_ranked_moves(board):
    fen = board.fen()
    stockfish.set_fen_position(fen)
    legal_moves = [move.uci() for move in board.legal_moves]
    top_moves_data = stockfish.get_top_moves(min(len(legal_moves), 15))
    ranked_moves = [move['Move'] for move in top_moves_data]
    for move in legal_moves:
        if move not in ranked_moves:
            ranked_moves.append(move)
    return ranked_moves

# ---- NEW ANALYSIS FUNCTION ----
def analyze_player_style(history):
    """
    Analyzes the move history and returns a player profile.
    """
    if not history: # If history is empty, return a default profile
        return {"aggression": 0, "avg_rank_percent": 0, "piece_preference": {}}

    # 1. Calculate Aggression
    aggressive_moves = sum(1 for move in history if move["is_capture"] or move["is_check"])
    aggression_score = aggressive_moves / len(history)

    # 2. Calculate Average Move Quality (as a percentage)
    total_rank_percent = sum(move["move_rank"] / move["total_options"] for move in history)
    avg_rank_percent = total_rank_percent / len(history)
    
    # 3. Calculate Piece Preference
    piece_counts = {}
    for move in history:
        piece = move["piece"].upper() # Use upper case to group P and p
        piece_counts[piece] = piece_counts.get(piece, 0) + 1
        
    return {
        "aggression": aggression_score,
        "avg_rank_percent": avg_rank_percent,
        "piece_preference": piece_counts
    }

# (unicode_pieces, clear_screen, print_board_unicode are unchanged)
unicode_pieces = {'r':'♜','n':'♞','b':'♝','q':'♛','k':'♚','p':'♟','R':'♖','N':'♘','B':'♗','Q':'♕','K':'♔','P':'♙'}
def clear_screen(): os.system('cls' if os.name == 'nt' else 'clear')
def print_board_unicode(board):
    print("  a b c d e f g h")
    for i in range(8, 0, -1):
        row = str(i) + " "
        for j in range(8):
            piece = board.piece_at(chess.square(j, i - 1))
            row += (unicode_pieces.get(str(piece), ".") + " ")
        print(row)
    print("  a b c d e f g h\n")

# --- Main Game Loop ---
board = chess.Board()
player_move_history = [] 

while not board.is_game_over():
    clear_screen()
    print_board_unicode(board)

    if board.turn == chess.WHITE: # Player's turn
        # (This part is unchanged from the last step)
        ranked_moves = get_ranked_moves(board)
        move_san = input("Your move (White). Enter move (e.g., e4): ")
        try:
            move_object = board.parse_san(move_san)
            move_uci = move_object.uci()
            move_rank = ranked_moves.index(move_uci) + 1
            piece_moved = board.piece_at(move_object.from_square).symbol()
            move_data = {
                "turn": board.fullmove_number, "move_san": move_san,
                "move_rank": move_rank, "total_options": len(ranked_moves),
                "piece": piece_moved, "is_capture": board.is_capture(move_object),
                "is_check": board.gives_check(move_object)
            }
            player_move_history.append(move_data)
            print(f"\n[Move #{len(player_move_history)} logged. You moved your {piece_moved}.]")
            board.push(move_object)
        except Exception:
            print("\n!!! Illegal or invalid move! Please try again. !!!")
            input("Press Enter to continue...")
    
    else: # AI's turn with Style Analysis
        print("AI is analyzing your style...")
        
        # --- NEW AI LOGIC ---
        # Analyze the history to get the player's profile
        player_profile = analyze_player_style(player_move_history)
        
        # Display the analysis
        print("\n--- Player Profile ---")
        print(f"Aggression: {player_profile['aggression']:.2f} (Percentage of attacking moves)")
        print(f"Precision: {1 - player_profile['avg_rank_percent']:.2f} (1.0 is perfect, lower is more random)")
        print(f"Preferred Pieces: {player_profile['piece_preference']}")
        print("----------------------")
        # --- END NEW AI LOGIC ---
        
        # AI still plays the best move for now. Mimicking comes next.
        ai_ranked_moves = get_ranked_moves(board)
        ai_move_uci = ai_ranked_moves[0]
        
        board.push(chess.Move.from_uci(ai_move_uci))
        input("\nAI made its move. Press Enter to continue...")

# --- Game Over ---
clear_screen()
print_board_unicode(board)
print("Game Over!")
print("Result: " + board.result())

