# app.py (Full, Render-Ready Version)

import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import chess
from pystockfish import Engine
import json
import datetime

app = Flask(__name__)

# --- Configuration ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secret-key')
db_url = os.environ.get('DATABASE_URL', '')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Engine Setup ---
try:
    engine_path = os.path.join(os.path.dirname(__file__), "engine", "stockfish")
    engine = Engine(path=engine_path, depth=15)
    print("--- Stockfish engine initialized successfully ---")
except Exception as e:
    print(f"--- FATAL ERROR: Could not initialize Stockfish engine: {e} ---")
    exit()

# --- Global Game State ---
board = chess.Board()
player_move_history = []

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class GameLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    result = db.Column(db.String(10), nullable=False)
    moves_json = db.Column(db.Text, nullable=False)
    played_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

with app.app_context():
    db.create_all()
    print("--- Database tables checked/created successfully ---")

# --- Helper Function for AI ---
def get_ranked_moves(board_state):
    engine.setfen(board_state.fen())
    top_moves = engine.get_top_moves(count=len(list(board_state.legal_moves)))
    if not top_moves:
        return []
    return [move['Move'] for move in top_moves]

# --- User Account Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
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
    if 'user_id' not in session:
        return jsonify({'status': 'Error', 'message': 'Not authenticated'}), 401
    player_move_uci = request.json.get('move')
    move_object = chess.Move.from_uci(player_move_uci)
    if move_object in board.legal_moves:
        ranked_moves = get_ranked_moves(board)
        move_rank = ranked_moves.index(move_object.uci()) + 1 if move_object.uci() in ranked_moves else len(ranked_moves)
        piece_moved = board.piece_at(move_object.from_square).symbol()
        move_data = {
            "turn": board.fullmove_number,
            "move_san": board.san(move_object),
            "move_rank": move_rank,
            "total_options": len(ranked_moves),
            "piece": piece_moved,
            "is_capture": board.is_capture(move_object),
            "is_check": board.gives_check(move_object)
        }
        player_move_history.append(move_data)
        board.push(move_object)

        if board.is_game_over():
            save_game_log()
            return jsonify({'status': 'Game Over', 'result': board.result()})

        engine.setfen(board.fen())
        ai_move_uci = engine.get_best_move()
        if ai_move_uci:
            board.push(chess.Move.from_uci(ai_move_uci))

        if board.is_game_over():
            save_game_log()
        return jsonify({'status': 'Success', 'ai_move': ai_move_uci})

    return jsonify({'status': 'Error', 'message': 'Illegal move'}), 400

# --- Game Log Saving ---
def save_game_log():
    if 'username' not in session:
        return
    username = session['username']
    result = board.result()
    moves_as_json_string = json.dumps(player_move_history)
    new_log = GameLog(username=username, result=result, moves_json=moves_as_json_string)
    db.session.add(new_log)
    db.session.commit()
    print(f"Game log saved for user '{username}'")

# --- Run App ---
if __name__ == '__main__':
    app.run(debug=True)
