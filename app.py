# app.py (Final, Complete Version)

import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import chess
from stockfish import Stockfish
import json

# --- App and Database Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_super_secret_key_that_you_should_change'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Chess Engine and Game State Setup ---
try:
    stockfish = Stockfish(path="stockfish.exe")
    stockfish.set_skill_level(5)
    print("Stockfish engine initialized.")
except FileNotFoundError:
    print("FATAL ERROR: 'stockfish.exe' not found.")
    exit()

board = chess.Board()
player_move_history = []
mimic_profile = None  # This will hold the style profile of the player we want to mimic

# --- Database Model ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# --- AI Helper Functions ---
def get_ranked_moves(board_state):
    fen = board_state.fen()
    stockfish.set_fen_position(fen)
    legal_moves_uci = [move.uci() for move in board_state.legal_moves]
    # Get a comprehensive list of moves for our filtering logic
    top_moves_data = stockfish.get_top_moves(len(legal_moves_uci))
    if top_moves_data is None: return legal_moves_uci

    ranked_moves = [move['Move'] for move in top_moves_data]
    for move in legal_moves_uci:
        if move not in ranked_moves:
            ranked_moves.append(move)
    return ranked_moves

def analyze_player_style(history):
    if not history:
        return {"aggression": 0.2, "precision": 0.8, "piece_preference": {}} # Default profile
    aggressive_moves = sum(1 for move in history if move["is_capture"] or move["is_check"])
    aggression_score = aggressive_moves / len(history)
    total_rank_percent = sum(move["move_rank"] / move["total_options"] for move in history if move["total_options"] > 0)
    avg_rank_percent = total_rank_percent / len(history) if len(history) > 0 else 0
    piece_counts = {}
    for move in history:
        piece = move["piece"].upper()
        piece_counts[piece] = piece_counts.get(piece, 0) + 1
    return {
        "aggression": aggression_score,
        "precision": 1.0 - avg_rank_percent,
        "piece_preference": piece_counts
    }

def choose_mimic_move(board_state, profile):
    all_moves = get_ranked_moves(board_state)
    if not all_moves: return None

    # Basic safety check: Don't make an obvious blunder. Let's consider the top 75% of moves as "safe"
    safe_move_count = max(1, int(len(all_moves) * 0.75))
    candidate_moves = all_moves[:safe_move_count]

    move_scores = {}
    for i, move_uci in enumerate(candidate_moves):
        score = 0
        move = chess.Move.from_uci(move_uci)
        # 1. Aggression Score: Prioritize captures/checks if profile is aggressive
        if (board_state.is_capture(move) or board_state.gives_check(move)):
            score += profile['aggression'] * 10
        # 2. Piece Preference Score: Prioritize moving preferred pieces
        moved_piece = board_state.piece_at(move.from_square).symbol().upper()
        if moved_piece in profile['piece_preference']:
            score += profile['piece_preference'][moved_piece] * 0.1
        # 3. Use original rank as a small tie-breaker
        score -= i * 0.01
        move_scores[move_uci] = score

    return max(move_scores, key=move_scores.get)

# --- User Account Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    # ... [This function is complete and correct] ...
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Username and password are required.')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Username is already taken.')
            return redirect(url_for('register'))
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # ... [This function is complete and correct] ...
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Logged in successfully.')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    # ... [This function is complete and correct] ...
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('login'))

# --- Main Chess Game Routes ---
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    board.reset()
    player_move_history.clear()
    return render_template('index.html')

@app.route('/move', methods=['POST'])
def handle_move():
    if 'user_id' not in session:
        return jsonify({'status': 'Error', 'message': 'Not authenticated'}), 401

    player_move_uci = request.json.get('move')
    move_object = chess.Move.from_uci(player_move_uci)

    if move_object in board.legal_moves:
        # --- Detailed move logging is now active ---
        ranked_moves = get_ranked_moves(board)
        move_rank = ranked_moves.index(move_object.uci()) + 1 if move_object.uci() in ranked_moves else len(ranked_moves)
        piece_moved = board.piece_at(move_object.from_square).symbol()
        move_data = {
            "turn": board.fullmove_number, "move_san": board.san(move_object), "move_rank": move_rank,
            "total_options": len(ranked_moves), "piece": piece_moved,
            "is_capture": board.is_capture(move_object), "is_check": board.gives_check(move_object)
        }
        player_move_history.append(move_data)
        
        board.push(move_object) # Player move

        if board.is_game_over():
            save_game_log()
            return jsonify({'status': 'Game Over', 'result': board.result()})

        # --- The intelligent AI logic is now active ---
        print("AI is choosing a move based on the mimic profile...")
        ai_move_uci = choose_mimic_move(board, mimic_profile)
        if ai_move_uci:
            board.push(chess.Move.from_uci(ai_move_uci)) # AI move
        
        if board.is_game_over():
            save_game_log()

        return jsonify({'status': 'Success', 'ai_move': ai_move_uci})
    return jsonify({'status': 'Error', 'message': 'Illegal move'}), 400

def save_game_log():
    if 'username' not in session: return
    username = session['username']
    match_number = 1
    while os.path.exists(f"{username}_match_{match_number}.json"):
        match_number += 1
    
    log_filename = f"{username}_match_{match_number}.json"
    # --- Saves the full, detailed history ---
    with open(log_filename, "w") as f:
        json.dump(player_move_history, f, indent=2)
    print(f"Game history saved for {username} as '{log_filename}'")

# --- Load the mimic profile when the server starts ---
def load_mimic_profile():
    global mimic_profile
    # IMPORTANT: Change this filename to the one your friend generated!
    profile_filename = "friend_match_1.json"  # <--- CHANGE THIS FILENAME
    
    if os.path.exists(profile_filename):
        with open(profile_filename, "r") as f:
            history = json.load(f)
            mimic_profile = analyze_player_style(history)
            print(f"Successfully loaded and analyzed '{profile_filename}'.")
            print("--- Mimic Profile ---")
            print(json.dumps(mimic_profile, indent=2))
            print("---------------------")
    else:
        print(f"WARNING: Mimic profile '{profile_filename}' not found. AI will use a default style.")
        mimic_profile = analyze_player_style([])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    load_mimic_profile() # Load the profile before starting the server
    app.run(debug=True)