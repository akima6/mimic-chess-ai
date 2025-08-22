# app/routes.py
from flask import render_template, request, jsonify, session, redirect, url_for, flash, Blueprint
from . import db
from .models import User, GameLog
from .ai import get_ai_move, analyze_player_style # Import the correct AI
import chess
import json

bp = Blueprint('main', __name__)
board = chess.Board()
active_games = {}

@bp.route('/register', methods=['GET', 'POST'])
def register():
    # ... code is unchanged ...
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
    # ... code is unchanged ...
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Logged in successfully.')
            return redirect(url_for('main.home'))
        else:
            flash('Invalid username or password.')
    return render_template('login.html')

@bp.route('/logout')
def logout():
    # ... code is unchanged ...
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('main.login'))

@bp.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))
    board.reset()
    active_games[session['user_id']] = []
    return render_template('index.html')

@bp.route('/move', methods=['POST'])
def handle_move():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': 'Error', 'message': 'Not authenticated'}), 401
    player_move_uci = request.json.get('move')
    move_object = chess.Move.from_uci(player_move_uci)
    if move_object in board.legal_moves:
        move_data = { "turn": board.fullmove_number, "move_san": board.san(move_object) }
        active_games.setdefault(user_id, []).append(move_data)
        board.push(move_object)
        if board.is_game_over():
            save_game_log()
            return jsonify({'status': 'Game Over', 'result': board.result()})
        ai_move_uci = get_ai_move(board) # Calling the Hybrid AI
        if ai_move_uci:
            move_data = { "turn": board.fullmove_number, "move_san": board.san(chess.Move.from_uci(ai_move_uci)) }
            active_games[user_id].append(move_data)
            board.push(chess.Move.from_uci(ai_move_uci))
        if board.is_game_over():
            save_game_log()
        return jsonify({'status': 'Success', 'ai_move': ai_move_uci})
    return jsonify({'status': 'Error', 'message': 'Illegal move'}), 400

def save_game_log():
    # ... code is unchanged ...
    user_id = session.get('user_id')
    username = session.get('username')
    if not user_id or not username: return
    result = board.result()
    moves_as_json_string = json.dumps(active_games.get(user_id, []))
    new_log = GameLog(user_id=user_id, result=result, moves_json=moves_as_json_string)
    db.session.add(new_log)
    db.session.commit()
    print(f"Game log saved to database for user '{username}'")