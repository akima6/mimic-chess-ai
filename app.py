# app.py (Final Version - Hybrid AI with PostgreSQL Database)

import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import chess
import requests
import json
import datetime
import random

app = Flask(__name__)
# --- Configuration ---
app.config['SECRET_KEY'] = 'a_super_secret_key_that_you_should_change'
# This line reads the database URL from the environment variable we set on Render
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', '').replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

print("--- Application starting up. AI moves will be provided by a Hybrid AI. ---")

# --- Global Game State ---
board = chess.Board()
player_move_history = []

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class GameLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    result = db.Column(db.String(10), nullable=False)
    moves_json = db.Column(db.Text, nullable=False)
    played_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# Create the database tables if they don't already exist.
with app.app_context():
    db.create_all()
    print("--- Database tables checked/created successfully. ---")


# --- NEW: Secondary Brain - Pure Python Evaluation ---
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

# --- NEW: Primary Brain - Lichess API with Smart Fallback ---
def get_ai_best_move(board):
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
    print("!!! API failed or returned invalid move. Using fallback AI. !!!")
    return get_simple_best_move(board)

# --- User Account Routes (Unchanged) ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    # ... (code is unchanged)
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
    # ... (code is unchanged)
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
    # ... (code is unchanged)
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('login'))


# --- Main Game Routes ---
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    board.reset()
    player_move_history.clear()
    return render_template('index.html')

@app.route('/move', methods=['POST'])
def handle_move():
    if 'user_id' not in session: return jsonify({'status': 'Error', 'message': 'Not authenticated'}), 401
    player_move_uci = request.json.get('move')
    move_object = chess.Move.from_uci(player_move_uci)
    if move_object in board.legal_moves:
        move_data = { "turn": board.fullmove_number, "move_san": board.san(move_object) }
        player_move_history.append(move_data)
        board.push(move_object)
        if board.is_game_over():
            save_game_log()
            return jsonify({'status': 'Game Over', 'result': board.result()})
        
        # --- AI's Turn using the new Hybrid Brain ---
        ai_move_uci = get_ai_best_move(board)
        
        if ai_move_uci:
            board.push(chess.Move.from_uci(ai_move_uci))
        if board.is_game_over():
            save_game_log()
        return jsonify({'status': 'Success', 'ai_move': ai_move_uci})
    return jsonify({'status': 'Error', 'message': 'Illegal move'}), 400

# --- Game Log Saving to Database (Unchanged) ---
def save_game_log():
    if 'username' not in session: return
    username = session['username']
    result = board.result()
    moves_as_json_string = json.dumps(player_move_history)
    new_log = GameLog(username=username, result=result, moves_json=moves_as_json_string)
    db.session.add(new_log)
    db.session.commit()
    print(f"Game log saved to database for user '{username}'")

# This is only for running locally
if __name__ == '__main__':
    app.run(debug=True)