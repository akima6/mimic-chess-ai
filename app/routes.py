# app/routes.py

from flask import render_template, request, jsonify, session, redirect, url_for, flash, Blueprint
from . import db
from .models import User, GameLog
from .ai import analyze_player_style, get_ai_move, profile_cache
import chess
import json

# A Blueprint is a way to organize a group of related routes
bp = Blueprint('main', __name__)

# This is the global board object for active games
board = chess.Board()
# This dictionary will store the move history for the current game
# We'll key it by user ID to handle multiple simultaneous games if needed
active_games = {}

@bp.route('/register', methods=['GET', 'POST'])
def register():
    # ... (code is unchanged from the last working version)
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Username and password are required.')
            return redirect(url_for('main.register'))
        if User.query.filter_by(username=username).first():
            flash('Username is already taken.')
            return redirect(url_for('main.register'))
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.')
        return redirect(url_for('main.login'))
    return render_template('register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    # ... (code is unchanged from the last working version)
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            
            # --- NEW: Analyze user's style upon login ---
            print(f"User '{username}' logged in. Analyzing game history...")
            all_games = GameLog.query.filter_by(user_id=user.id).all()
            profile = analyze_player_style(all_games)
            profile_cache[username] = profile
            # --- END NEW ---
            
            flash('Logged in successfully.')
            return redirect(url_for('main.home'))
        else:
            flash('Invalid username or password.')
    return render_template('login.html')

@bp.route('/logout')
def logout():
    # ... (code is unchanged from the last working version)
    username = session.get('username')
    if username and username in profile_cache:
        del profile_cache[username] # Clear the user's profile from the cache
        
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('main.login'))

@bp.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    
    # Start a new game for this user
    board.reset()
    active_games[session['user_id']] = [] # Clear move history for a new game
    
    return render_template('index.html')

@bp.route('/move', methods=['POST'])
def handle_move():
    user_id = session.get('user_id')
    username = session.get('username')
    if not user_id or not username:
        return jsonify({'status': 'Error', 'message': 'Not authenticated'}), 401
    
    player_move_uci = request.json.get('move')
    move_object = chess.Move.from_uci(player_move_uci)

    if move_object in board.legal_moves:
        # 1. Record the player's move
        move_data = { "turn": board.fullmove_number, "move_san": board.san(move_object) }
        active_games.setdefault(user_id, []).append(move_data)
        board.push(move_object)

        if board.is_game_over():
            save_game_log()
            return jsonify({'status': 'Game Over', 'result': board.result()})

        # 2. Get the AI's move using the new AI brain
        ai_move_uci = get_ai_move(board, username)
        
        if ai_move_uci:
            # 3. Record the AI's move
            move_data = { "turn": board.fullmove_number, "move_san": board.san(chess.Move.from_uci(ai_move_uci)) }
            active_games[user_id].append(move_data)
            board.push(chess.Move.from_uci(ai_move_uci))
        
        if board.is_game_over():
            save_game_log()
            
        return jsonify({'status': 'Success', 'ai_move': ai_move_uci})
    
    return jsonify({'status': 'Error', 'message': 'Illegal move'}), 400

def save_game_log():
    """Saves the completed game to the database and triggers a profile update."""
    user_id = session.get('user_id')
    username = session.get('username')
    if not user_id or not username: return

    # Save the game to the database
    result = board.result()
    moves_as_json_string = json.dumps(active_games.get(user_id, []))
    new_log = GameLog(user_id=user_id, result=result, moves_json=moves_as_json_string)
    db.session.add(new_log)
    db.session.commit()
    print(f"Game log saved to database for user '{username}'")
    
    # --- NEW: Re-analyze the user's profile with the new game data ---
    print(f"Re-analyzing profile for '{username}'...")
    all_games = GameLog.query.filter_by(user_id=user_id).all()
    new_profile = analyze_player_style(all_games)
    profile_cache[username] = new_profile
    # --- END NEW ---