# app.py (Final Version - Using Lichess API)

import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import chess
import requests # The library for making web requests
import json
import time

app = Flask(__name__)
# --- Configuration ---
app.config['SECRET_KEY'] = 'a_super_secret_key_that_you_should_change'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- NO MORE LOCAL ENGINE SETUP! ---
print("--- Application starting up. AI moves will be provided by Lichess API. ---")

# --- Global Game State ---
board = chess.Board()
# IMPORTANT: The Lichess API needs the full move history to analyze the position
game_move_history_uci = []

# --- Database Model (Unchanged) ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

# --- NEW AI BRAIN: A FUNCTION TO CALL THE LICHESS API ---
def get_ai_best_move_from_api(fen, moves_list):
    """
    Calls the Lichess API to get the best move for the current position.
    """
    api_url = "https://lichess.org/api/cloud-eval"
    # The API can take the position as a FEN string
    params = {"fen": fen}
    
    try:
        # Make the web request to the API
        res = requests.get(api_url, params=params)
        res.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        data = res.json()
        
        # The best move is in the 'pvs' (principal variations) list
        if data and 'pvs' in data and len(data['pvs']) > 0:
            best_move_uci = data['pvs'][0]['moves'].split(' ')[0]
            print(f"Lichess API returned best move: {best_move_uci}")
            return best_move_uci
    except requests.exceptions.RequestException as e:
        print(f"!!! API REQUEST FAILED: {e} !!!")
    
    # Fallback: If the API fails, just pick a random legal move
    print("!!! API failed. Falling back to a random legal move. !!!")
    legal_moves = list(board.legal_moves)
    if legal_moves:
        return legal_moves[0].uci()
    return None


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
    # Reset game state for a new game
    board.reset()
    game_move_history_uci.clear()
    return render_template('index.html')

@app.route('/move', methods=['POST'])
def handle_move():
    if 'user_id' not in session: return jsonify({'status': 'Error', 'message': 'Not authenticated'}), 401
    
    player_move_uci = request.json.get('move')
    move_object = chess.Move.from_uci(player_move_uci)

    if move_object in board.legal_moves:
        board.push(move_object)
        game_move_history_uci.append(move_object.uci())

        if board.is_game_over():
            save_game_log()
            return jsonify({'status': 'Game Over', 'result': board.result()})

        # 3. AI's Turn: Call the Lichess API
        print("AI is asking Lichess API for the best move...")
        ai_move_uci = get_ai_best_move_from_api(board.fen(), game_move_history_uci)
        
        if ai_move_uci:
            board.push(chess.Move.from_uci(ai_move_uci))
            game_move_history_uci.append(ai_move_uci)
        
        if board.is_game_over():
            save_game_log()

        return jsonify({'status': 'Success', 'ai_move': ai_move_uci})
    
    return jsonify({'status': 'Error', 'message': 'Illegal move'}), 400

# --- Game Log Saving (Unchanged) ---
def save_game_log():
    if 'username' not in session: return
    username = session['username']
    log_dir = "game_logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    match_number = 1
    while os.path.exists(os.path.join(log_dir, f"{username}_match_{match_number}.json")):
        match_number += 1
    log_filename = os.path.join(log_dir, f"{username}_match_{match_number}.json")
    # We will just save the UCI moves for now
    with open(log_filename, "w") as f:
        json.dump({"moves_uci": game_move_history_uci}, f, indent=2)
    print(f"Game history saved for {username} as '{log_filename}'")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)