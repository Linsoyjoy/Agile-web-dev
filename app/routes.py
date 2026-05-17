import json
import os
import re
import urllib.request
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from app import db, csrf
from .blueprints import main
from .models import User, Tournament, Match, Friendship, Queries
from .forgot_password import reset_password_email
from .query_reply import send_reply
from datetime import datetime

# Opening lookup — ordered most-specific first so the longest match wins
_OPENINGS = [
    ('e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O', 'Ruy López — Open'),
    ('e4 e5 Nf3 Nc6 Bb5 a6',              'Ruy López — Morphy'),
    ('e4 e5 Nf3 Nc6 Bb5',                 'Ruy López'),
    ('e4 e5 Nf3 Nc6 Bc4 Bc5',            'Italian — Giuoco Piano'),
    ('e4 e5 Nf3 Nc6 Bc4 Nf6',            'Italian — Two Knights'),
    ('e4 e5 Nf3 Nc6 Bc4',                'Italian Game'),
    ('e4 e5 Nf3 Nc6 d4',                 'Scotch Game'),
    ('e4 e5 f4',                          "King's Gambit"),
    ('e4 e5 Nf3 Nf6',                    'Petrov Defence'),
    ('e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 g6', 'Sicilian — Dragon'),
    ('e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6', 'Sicilian — Najdorf'),
    ('e4 c5 Nf3 Nc6 d4 cxd4 Nxd4',      'Sicilian — Classical'),
    ('e4 c5 Nf3 e6',                     'Sicilian — Kan'),
    ('e4 c5',                            'Sicilian Defence'),
    ('e4 e6 d4 d5',                      'French Defence'),
    ('e4 e6',                            'French Defence'),
    ('e4 c6 d4 d5 Nc3 dxe4 Nxe4',       'Caro-Kann — Classical'),
    ('e4 c6',                            'Caro-Kann'),
    ('e4 d5',                            'Scandinavian Defence'),
    ('e4 Nf6',                           "Alekhine's Defence"),
    ('e4 g6',                            'Modern Defence'),
    ('d4 Nf6 c4 g6 Nc3 d5',             'Grünfeld Defence'),
    ('d4 Nf6 c4 g6 Nc3 Bg7 e4',         "King's Indian — Classical"),
    ('d4 Nf6 c4 g6',                     "King's Indian Defence"),
    ('d4 Nf6 c4 e6 Nc3 Bb4',            'Nimzo-Indian Defence'),
    ('d4 Nf6 c4 e6 Nf3 b6',             "Queen's Indian Defence"),
    ('d4 d5 c4 dxc4',                   "Queen's Gambit Accepted"),
    ('d4 d5 c4 c6 Nf3 Nf6',            'Slav — Three Knights'),
    ('d4 d5 c4 c6',                     'Slav Defence'),
    ('d4 d5 c4 e6 Nc3 Nf6 Bg5',        "Queen's Gambit — Orthodox"),
    ('d4 d5 c4 e6',                     "Queen's Gambit Declined"),
    ('d4 d5 c4',                        "Queen's Gambit"),
    ('d4 f5',                           'Dutch Defence'),
    ('d4 d5',                           "Closed Game"),
    ('c4 e5',                           'English — Reversed Sicilian'),
    ('c4',                              'English Opening'),
    ('Nf3 d5 c4',                       'Réti Opening'),
    ('Nf3',                             'Réti / Zukertort'),
    ('d4',                              "Queen's Pawn Game"),
    ('e4',                              "King's Pawn Game"),
]


def _identify_opening(pgn):
    # Strip move numbers (e.g. "1." "12."), annotations, and result markers
    clean = re.sub(r'\d+\.+', '', pgn or '')
    clean = re.sub(r'[+#!?]', '', clean)
    clean = ' '.join(clean.split())
    for moves, name in _OPENINGS:
        if clean.startswith(moves):
            return name
    return 'Other'


def _player_stats(username):
    """Calculate wins/losses/draws/win_rate/elo for a given user."""
    matches = Match.query.filter(
        (Match.player == username) | (Match.opponent == username)
    ).filter(Match.termination != 'upcoming').all()
    wins = losses = draws = 0
    for m in matches:
        r = (m.result or '').lower()
        if r == 'pending':
            continue
        if m.player == username:
            if r == 'win': wins += 1
            elif r == 'loss': losses += 1
            elif r == 'draw': draws += 1
        else:
            if r == 'loss': wins += 1
            elif r == 'win': losses += 1
            elif r == 'draw': draws += 1
    total = wins + losses + draws
    win_rate = round((wins / total * 100) if total > 0 else 0, 1)
    # Simplified ELO: starts at 1200, scales with wins and win rate, penalises losses (floor 100)
    elo = max(100, round(1200 + (wins * 10) - (losses * 5) + (win_rate * 2)))
    return {'wins': wins, 'losses': losses, 'draws': draws, 'win_rate': win_rate, 'elo': elo}


# Inject the logged-in user's profile picture into every template context
@main.context_processor
def inject_profile_pic():
    if 'username' in session:
        user = User.query.filter_by(username=session['username']).first()
        if user:
            return {'profile_pic': user.profile_pic}
    return {'profile_pic': None}


# Handle profile picture uploads — saves the file and updates the user record
@main.route('/upload_profile_pic', methods=['POST'])
def upload_profile_pic():
    if 'username' not in session:
        return redirect(url_for('main.login'))
    if 'profile_pic' not in request.files or request.files['profile_pic'].filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('main.profile'))
    file = request.files['profile_pic']
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in {'png', 'jpg', 'jpeg', 'gif'}:
        flash('Only PNG, JPG and GIF files are allowed', 'error')
        return redirect(url_for('main.profile'))
    filename = secure_filename(session['username'] + '.' + ext)
    upload_dir = os.path.join(os.path.dirname(__file__), 'static', 'images', 'profiles')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, filename))
    user = User.query.filter_by(username=session['username']).first()
    user.profile_pic = filename
    db.session.commit()
    flash('Profile picture updated!', 'success')
    return redirect(url_for('main.profile'))


@main.route('/')
def home():
    if 'username' not in session:
        return render_template('landing.html')

    username = session['username']
    privilege = User.query.get(username)

    # Get user's latest match (could be completed or upcoming)
    latest_match = Match.query.filter(
        (Match.player == username) | (Match.opponent == username)
    ).order_by(Match.date_played.desc()).first()

    # Get all upcoming matches in date order
    upcoming_matches = Match.query.filter(
        (Match.player == username) | (Match.opponent == username),
        Match.result == 'pending'
    ).order_by(Match.date_played.asc()).all()

    # Get user's overall stats
    user_matches = Match.query.filter(
        (Match.player == username) | (Match.opponent == username)
    ).all()

    # Count wins/losses/draws from the user's perspective (they may be player or opponent)
    wins = losses = draws = 0
    for match in user_matches:
        r = (match.result or '').lower()
        if match.player == username:
            if r == 'win':
                wins += 1
            elif r == 'loss':
                losses += 1
            elif r == 'draw':
                draws += 1
            elif r == 'pending':
                # Skip upcoming matches from stats calculation
                continue
        else:
            if r == 'loss':
                wins += 1
            elif r == 'win':
                losses += 1
            elif r == 'draw':
                draws += 1
            elif r == 'pending':
                # Skip upcoming matches from stats calculation
                continue

    total_games = wins + losses + draws
    win_rate = round((wins / total_games * 100) if total_games > 0 else 0, 1)

    # Get recent activity (last 3 completed matches)
    recent_matches = Match.query.filter(
        (Match.player == username) | (Match.opponent == username),
        Match.result != 'pending'
    ).order_by(Match.date_played.desc()).limit(3).all()

    return render_template('home.html', 
                         username=username, 
                         latest_match=latest_match,
                         upcoming_matches=upcoming_matches,
                         stats={'wins': wins, 'losses': losses, 'draws': draws, 'win_rate': win_rate},
                         recent_matches=recent_matches, user=privilege)


# Friends page — shows accepted friends, a friends-only leaderboard, and pending requests
@main.route('/friends')
def friends():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))

    current_user = session['username']
    privilege = User.query.get(current_user)

    # Get all users and calculate their rankings
    all_users = User.query.all()
    players = []

    for u in all_users:
        s = _player_stats(u.username)
        players.append({
            'username': u.username,
            'wins': s['wins'],
            'losses': s['losses'],
            'draws': s['draws'],
            'win_rate': s['win_rate'],
            'elo': s['elo'],
            'is_current_user': u.username == current_user
        })

    # Sort by ELO (descending) and assign ranks
    players.sort(key=lambda x: x['elo'], reverse=True)
    for i, player in enumerate(players):
        player['rank'] = i + 1

    # Get pending friend requests
    pending_requests = Friendship.query.filter_by(addressee_id=current_user, status='pending').all()

    # Get current friends
    current_friends = []
    friendships = Friendship.query.filter(
        ((Friendship.requester_id == current_user) | (Friendship.addressee_id == current_user)) &
        (Friendship.status == 'accepted')
    ).all()

    for friendship in friendships:
        if friendship.requester_id == current_user:
            friend_username = friendship.addressee_id
        else:
            friend_username = friendship.requester_id

        # Get friend's stats
        friend_user = User.query.filter_by(username=friend_username).first()
        if friend_user:
            s = _player_stats(friend_username)
            current_friends.append({
                'username': friend_username,
                'wins': s['wins'],
                'losses': s['losses'],
                'draws': s['draws'],
                'win_rate': s['win_rate'],
                'elo': s['elo']
            })

    # Build friends-only leaderboard — includes current user so they can see where they rank
    friend_usernames = {f['username'] for f in current_friends}
    friend_usernames.add(current_user)
    friends_leaderboard = [p for p in players if p['username'] in friend_usernames]
    for i, p in enumerate(friends_leaderboard):
        p['friends_rank'] = i + 1

    return render_template('friends.html', username=current_user, players=players,
                           pending_requests=pending_requests, current_friends=current_friends,
                           friends_leaderboard=friends_leaderboard, user=privilege)


# AJAX — search for a user by username and redirect to their profile
@csrf.exempt
@main.route('/add_friend', methods=['POST'])
def add_friend():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Please log in to access this page!'})

    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Invalid request data!'})

        friend_username = data.get('friend_username', '').strip()
        current_user = session['username']

        if not friend_username:
            return jsonify({'success': False, 'message': 'Please enter a username!'})

        # Check if user exists
        friend_user = User.query.filter_by(username=friend_username).first()
        if not friend_user:
            return jsonify({'success': False, 'message': 'User not found!'})

        # Check if trying to add self
        if friend_username == current_user:
            return jsonify({'success': False, 'message': 'You cannot add yourself as a friend!'})

        # For now, just return success and redirect to view user profile
        # In a real implementation, you would add friend relationships to database
        return jsonify({
            'success': True,
            'message': f'Successfully found user: {friend_username}! Redirecting to their profile...',
            'redirect': f'/view_user/{friend_username}'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': 'An error occurred. Please try again.'})


# AJAX — create a new friend request between the current user and a target user
@csrf.exempt
@main.route('/send_friend_request', methods=['POST'])
def send_friend_request():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Please log in to access this page!'})

    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Invalid request data!'})

        target_username = data.get('target_username', '').strip()
        current_user = session['username']

        if not target_username:
            return jsonify({'success': False, 'message': 'Invalid target user!'})

        if target_username == current_user:
            return jsonify({'success': False, 'message': 'You cannot send a friend request to yourself!'})

        # Check if target user exists
        target_user = User.query.filter_by(username=target_username).first()
        if not target_user:
            return jsonify({'success': False, 'message': 'User not found!'})

        # Check if friendship already exists
        existing_friendship = Friendship.query.filter(
            ((Friendship.requester_id == current_user) & (Friendship.addressee_id == target_username)) |
            ((Friendship.requester_id == target_username) & (Friendship.addressee_id == current_user))
        ).first()

        if existing_friendship:
            if existing_friendship.status == 'accepted':
                return jsonify({'success': False, 'message': 'You are already friends!'})
            elif existing_friendship.status == 'pending':
                if existing_friendship.requester_id == current_user:
                    return jsonify({'success': False, 'message': 'Friend request already sent!'})
                else:
                    return jsonify({'success': False, 'message': 'You have a pending friend request from this user!'})
            elif existing_friendship.status == 'declined':
                # Update declined request to pending
                existing_friendship.status = 'pending'
                existing_friendship.requester_id = current_user
                existing_friendship.addressee_id = target_username
                existing_friendship.updated_at = datetime.utcnow()
                db.session.commit()
                return jsonify({'success': True, 'message': 'Friend request sent successfully!'})

        # Create new friend request
        new_friendship = Friendship(
            requester_id=current_user,
            addressee_id=target_username,
            status='pending'
        )
        db.session.add(new_friendship)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Friend request sent successfully!'})

    except Exception as e:
        return jsonify({'success': False, 'message': 'An error occurred. Please try again.'})


# AJAX — accept or decline a pending friend request
@csrf.exempt
@main.route('/respond_friend_request', methods=['POST'])
def respond_friend_request():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Please log in to access this page!'})

    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Invalid request data!'})

        friendship_id = data.get('friendship_id')
        action = data.get('action')  # 'accept' or 'decline'
        current_user = session['username']

        if not friendship_id or action not in ['accept', 'decline']:
            return jsonify({'success': False, 'message': 'Invalid request parameters!'})

        friendship = Friendship.query.get(friendship_id)
        if not friendship:
            return jsonify({'success': False, 'message': 'Friend request not found!'})

        if friendship.addressee_id != current_user:
            return jsonify({'success': False, 'message': 'You cannot respond to this friend request!'})

        friendship.status = 'accepted' if action == 'accept' else 'declined'
        friendship.updated_at = datetime.utcnow()
        db.session.commit()

        action_text = 'accepted' if action == 'accept' else 'declined'
        return jsonify({'success': True, 'message': f'Friend request {action_text}!'})

    except Exception as e:
        return jsonify({'success': False, 'message': 'An error occurred. Please try again.'})


# AJAX — remove an accepted friendship between the current user and a target user
@csrf.exempt
@main.route('/remove_friend', methods=['POST'])
def remove_friend():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Please log in to access this page!'})

    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Invalid request data!'})

        target_username = data.get('target_username', '').strip()
        current_user = session['username']

        if not target_username:
            return jsonify({'success': False, 'message': 'Invalid target user!'})

        # Find and remove friendship
        friendship = Friendship.query.filter(
            ((Friendship.requester_id == current_user) & (Friendship.addressee_id == target_username)) |
            ((Friendship.requester_id == target_username) & (Friendship.addressee_id == current_user))
        ).filter_by(status='accepted').first()

        if not friendship:
            return jsonify({'success': False, 'message': 'You are not friends with this user!'})

        db.session.delete(friendship)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Friend removed successfully!'})

    except Exception as e:
        return jsonify({'success': False, 'message': 'An error occurred. Please try again.'})


# View another user's public profile — shows their stats and friendship status
@main.route('/view_user/<username>')
def view_user(username):
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))

    user = User.query.filter_by(username=username).first()
    if not user:
        flash('User not found!', 'error')
        return redirect(url_for('main.friends'))

    current_user = session['username']

    # Check friendship status
    friendship_status = None
    friendship = None

    if current_user != username:
        # Check if there's any friendship between these users
        friendship = Friendship.query.filter(
            ((Friendship.requester_id == current_user) & (Friendship.addressee_id == username)) |
            ((Friendship.requester_id == username) & (Friendship.addressee_id == current_user))
        ).first()

        if friendship:
            if friendship.status == 'accepted':
                friendship_status = 'friends'
            elif friendship.status == 'pending':
                if friendship.requester_id == current_user:
                    friendship_status = 'request_sent'
                else:
                    friendship_status = 'request_received'
            elif friendship.status == 'declined':
                if friendship.requester_id == current_user:
                    friendship_status = 'request_declined'
                else:
                    friendship_status = 'not_friends'
        else:
            friendship_status = 'not_friends'

    s = _player_stats(username)

    # Build recent match list for display (completed matches only)
    user_matches = Match.query.filter(
        (Match.player == username) | (Match.opponent == username)
    ).all()
    recent_matches = []
    for match in user_matches:
        r = (match.result or '').lower()
        if r == 'pending':
            continue
        if match.player == username:
            opponent = match.opponent
            user_result = r.capitalize()
        else:
            opponent = match.player
            user_result = 'Win' if r == 'loss' else ('Loss' if r == 'win' else 'Draw')
        recent_matches.append({
            'opponent': opponent,
            'result': user_result,
            'date': match.date_played,
            'colour': match.player_colour if match.player == username else ('black' if match.player_colour == 'white' else 'white')
        })

    # Rank by ELO across all users
    all_users = User.query.all()
    rankings = sorted([(_player_stats(u.username)['elo'], u.username) for u in all_users], reverse=True)
    user_rank = next((i + 1 for i, (_, u) in enumerate(rankings) if u == username), len(rankings))

    user_stats = {
        'wins': s['wins'],
        'losses': s['losses'],
        'draws': s['draws'],
        'win_rate': s['win_rate'],
        'elo': s['elo'],
        'ranking': f'#{user_rank}',
        'recent_matches': sorted(recent_matches, key=lambda x: x['date'], reverse=True)[:5]
    }

    return render_template('view_user.html', user=user, stats=user_stats, current_user=current_user, 
                         friendship_status=friendship_status, friendship=friendship)


# Profile page — shows the logged-in user's own stats, recent matches and weaknesses
@main.route('/profile')
def profile():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))

    username = session['username']
    user = User.query.filter_by(username=username).first()

    if not user:
        flash('User not found!', 'error')
        return redirect(url_for('main.login'))

    # Calculate real statistics from match data
    user_matches = Match.query.filter(
        (Match.player == username) | (Match.opponent == username)
    ).all()

    wins = 0
    losses = 0
    draws = 0
    recent_matches = []

    for match in user_matches:
        # Determine if user is player1 or player2 and get result
        r = (match.result or '').lower()
        if match.player == username:
            if r == 'win':
                wins += 1
                opponent = match.opponent
                user_result = 'Win'
            elif r == 'loss':
                losses += 1
                opponent = match.opponent
                user_result = 'Loss'
            elif r == 'draw':
                draws += 1
                opponent = match.opponent
                user_result = 'Draw'
            elif r == 'pending':
                # Skip upcoming matches from stats calculation
                continue
        else:
            if r == 'loss':
                wins += 1
                opponent = match.player
                user_result = 'Win'
            elif r == 'win':
                losses += 1
                opponent = match.player
                user_result = 'Loss'
            elif r == 'draw':
                draws += 1
                opponent = match.player
                user_result = 'Draw'
            elif r == 'pending':
                # Skip upcoming matches from stats calculation
                continue

        colour = match.player_colour if match.player == username else ('black' if match.player_colour.lower() == 'white' else 'white')

        # Add to recent matches
        recent_matches.append({
            'opponent': opponent,
            'result': user_result,
            'date': match.date_played,
            'colour': colour.capitalize()
        })

    # Sort recent matches by date (most recent first) and take last 3
    recent_matches = sorted(recent_matches, 
                          key=lambda x: x['date'],
                          reverse=True)[:3]

    total_games = wins + losses + draws
    win_rate = round((wins / total_games * 100) if total_games > 0 else 0, 1)

    # Calculate ranking based on total wins (simple implementation)
    all_users = User.query.all()
    user_rankings = []
    for u in all_users:
        u_matches = Match.query.filter(
            (Match.player == u.username) | (Match.opponent == u.username)
        ).all()
        u_wins = 0
        for m in u_matches:
            if m.player == u.username:
                if (m.result or '').lower() == 'win':
                    u_wins += 1
            else:
                if (m.result or '').lower() == 'loss':
                    u_wins += 1
        user_rankings.append((u.username, u_wins))

    user_rankings.sort(key=lambda x: x[1], reverse=True)
    user_rank = next((i+1 for i, (u, _) in enumerate(user_rankings) if u == username), len(user_rankings))

    # Calculate colour-specific stats from the user's perspective
    white_wins = white_losses = white_draws = 0
    black_wins = black_losses = black_draws = 0

    for match in user_matches:
        r = (match.result or '').lower()
        if r == 'pending':
            continue

        if match.player == username:
            colour = match.player_colour.lower()
            result = r
        else:
            # Reverse colour and result when user is the opponent
            colour = 'black' if match.player_colour.lower() == 'white' else 'white'
            if r == 'win':
                result = 'loss'
            elif r == 'loss':
                result = 'win'
            else:
                result = 'draw'

        if colour == 'white':
            if result == 'win': white_wins += 1
            elif result == 'loss': white_losses += 1
            elif result == 'draw': white_draws += 1
        else:
            if result == 'win': black_wins += 1
            elif result == 'loss': black_losses += 1
            elif result == 'draw': black_draws += 1

    white_total = white_wins + white_losses + white_draws
    black_total = black_wins + black_losses + black_draws
    white_win_rate = round((white_wins / white_total * 100) if white_total > 0 else 0, 1)
    black_win_rate = round((black_wins / black_total * 100) if black_total > 0 else 0, 1)

    user_stats = {
        'wins': wins,
        'losses': losses,
        'draws': draws,
        'win_rate': win_rate,
        'white_wins': white_wins,
        'white_losses': white_losses,
        'white_draws': white_draws,
        'white_win_rate': white_win_rate,
        'black_wins': black_wins,
        'black_losses': black_losses,
        'black_draws': black_draws,
        'black_win_rate': black_win_rate,
        'ranking': f'#{user_rank}',
        'recent_matches': recent_matches,
        'weaknesses': user.weaknesses or ''
    }

    return render_template('profile.html', user=user, stats=user_stats, username=username)


# Save the user's self-entered weaknesses text to the database
@main.route('/save_weaknesses', methods=['POST'])
def save_weaknesses():
    if 'username' not in session:
        return redirect(url_for('main.login'))
    user = User.query.filter_by(username=session['username']).first()
    user.weaknesses = request.form.get('weaknesses', '').strip()
    db.session.commit()
    flash('Notes saved!', 'success')
    return redirect(url_for('main.profile'))


# Save the user's linked external chess platform usernames
@main.route('/save_platforms', methods=['POST'])
def save_platforms():
    if 'username' not in session:
        return redirect(url_for('main.login'))
    user = User.query.filter_by(username=session['username']).first()
    user.chesscom_username = request.form.get('chesscom_username', '').strip() or None
    user.lichess_username = request.form.get('lichess_username', '').strip() or None
    user.fide_id = request.form.get('fide_id', '').strip() or None
    db.session.commit()
    flash('Platform accounts updated!', 'success')
    return redirect(url_for('main.profile'))


# AJAX — fetch live ratings from chess.com and lichess for the logged-in user
@main.route('/fetch_ratings')
@csrf.exempt
def fetch_ratings():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    user = User.query.filter_by(username=session['username']).first()
    ratings = {}

    if user.chesscom_username:
        try:
            url = f'https://api.chess.com/pub/player/{user.chesscom_username}/stats'
            req = urllib.request.Request(url, headers={'User-Agent': 'ChessMate/1.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            ratings['chesscom'] = {
                'username': user.chesscom_username,
                'rapid': data.get('chess_rapid', {}).get('last', {}).get('rating'),
                'blitz': data.get('chess_blitz', {}).get('last', {}).get('rating'),
                'bullet': data.get('chess_bullet', {}).get('last', {}).get('rating'),
            }
        except Exception:
            ratings['chesscom'] = {'username': user.chesscom_username, 'error': True}

    if user.lichess_username:
        try:
            url = f'https://lichess.org/api/user/{user.lichess_username}'
            req = urllib.request.Request(url, headers={'User-Agent': 'ChessMate/1.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            perfs = data.get('perfs', {})
            ratings['lichess'] = {
                'username': user.lichess_username,
                'rapid': perfs.get('rapid', {}).get('rating'),
                'blitz': perfs.get('blitz', {}).get('rating'),
                'bullet': perfs.get('bullet', {}).get('rating'),
            }
        except Exception:
            ratings['lichess'] = {'username': user.lichess_username, 'error': True}

    if user.fide_id:
        ratings['fide'] = {'id': user.fide_id}

    return jsonify(ratings)


# AJAX — exact username lookup used by the new record form to check if an opponent is on ChessMate
@main.route('/lookup_user')
def lookup_user():
    username = request.args.get('username', '').strip()
    if not username:
        return jsonify({'found': False})
    user = User.query.filter_by(username=username).first()
    return jsonify({'found': bool(user)})


# AJAX — partial username search used by the friends search dropdown
@main.route('/search_users')
def search_users():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    # Case-insensitive starts-with match, exclude self if logged in, limit to 8 results
    query = User.query.filter(User.username.ilike(f'{q}%'))
    if 'username' in session:
        current_user = session['username']
        query = query.filter(User.username != current_user)
    results = query.limit(8).all()
    return jsonify([u.username for u in results])


# Stats page — shows the user's overall stats, ELO, ranking and full match history
@main.route('/viewstats')
def viewstats():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))

    username = session['username']
    user = User.query.filter_by(username=username).first()

    s = _player_stats(username)
    wins, losses, draws = s['wins'], s['losses'], s['draws']
    win_rate = s['win_rate']

    # Compute ranking based on ELO across all users
    all_users = User.query.all()
    rankings = sorted(
        [(_player_stats(u.username)['elo'], u.username) for u in all_users],
        reverse=True
    )
    user_rank = next((i + 1 for i, (_, u) in enumerate(rankings) if u == username), len(rankings) or 1)

    # All matches including upcoming (for display in match history table)
    user_matches = Match.query.filter(
        (Match.player == username) | (Match.opponent == username)
    ).all()

    stats = {
        'wins': wins,
        'losses': losses,
        'draws': draws,
        'win_rate': win_rate,
        'ranking': f'#{user_rank}',
        'ELO': s['elo'],
    }

    # Build ELO history — one data point per completed match in chronological order for the graph
    sorted_matches = sorted(
        [m for m in user_matches if (m.result or '').lower() in ('win', 'loss', 'draw')],
        key=lambda m: m.date_played
    )
    c_wins = c_losses = c_draws = 0
    elo_history = []
    for m in sorted_matches:
        r = (m.result or '').lower()
        if m.player == username:
            if r == 'win': c_wins += 1
            elif r == 'loss': c_losses += 1
            elif r == 'draw': c_draws += 1
        else:
            if r == 'loss': c_wins += 1
            elif r == 'win': c_losses += 1
            elif r == 'draw': c_draws += 1
        # Recalculate ELO after each match to capture the rating at that point in time
        c_total = c_wins + c_losses + c_draws
        c_win_rate = (c_wins / c_total * 100) if c_total > 0 else 0
        elo_history.append({
            'date': m.date_played.strftime('%Y-%m-%d'),
            'elo': max(100, round(1200 + (c_wins * 10) - (c_losses * 5) + (c_win_rate * 2)))
        })

    my_matches = Match.query.filter(
        (Match.player == username) | (Match.opponent == username)
    ).order_by(Match.date_played.desc()).all()

    # White vs black performance split
    colour_stats = {'white': {'win': 0, 'loss': 0, 'draw': 0},
                    'black': {'win': 0, 'loss': 0, 'draw': 0}}
    for m in user_matches:
        r = (m.result or '').lower()
        if r not in ('win', 'loss', 'draw'):
            continue
        if m.player == username:
            col = (m.player_colour or '').lower()
            res = r
        else:
            col = 'black' if (m.player_colour or '').lower() == 'white' else 'white'
            res = 'win' if r == 'loss' else ('loss' if r == 'win' else 'draw')
        if col in colour_stats:
            colour_stats[col][res] += 1

    # Top termination types
    term_counts = {}
    for m in user_matches:
        t = (m.termination or '').strip().lower()
        if t and t != 'upcoming':
            term_counts[t] = term_counts.get(t, 0) + 1
    top_terminations = sorted(term_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    # Current streak and best win streak
    current_streak = 0
    streak_type = None
    best_win_streak = 0
    temp_win_streak = 0
    for m in reversed(sorted_matches):
        r = (m.result or '').lower()
        actual = r if m.player == username else ('win' if r == 'loss' else ('loss' if r == 'win' else 'draw'))
        if streak_type is None:
            streak_type = actual
            current_streak = 1
        elif actual == streak_type:
            current_streak += 1
        else:
            break
        if actual == 'win':
            temp_win_streak += 1
            best_win_streak = max(best_win_streak, temp_win_streak)
        else:
            temp_win_streak = 0

    # Opening performance table
    opening_map = {}
    for m in user_matches:
        r = (m.result or '').lower()
        if r not in ('win', 'loss', 'draw'):
            continue
        name = _identify_opening(m.moves)
        actual = r if m.player == username else ('win' if r == 'loss' else ('loss' if r == 'win' else 'draw'))
        if name not in opening_map:
            opening_map[name] = {'win': 0, 'loss': 0, 'draw': 0}
        opening_map[name][actual] += 1
    opening_list = []
    for name, counts in sorted(opening_map.items(), key=lambda x: sum(x[1].values()), reverse=True)[:8]:
        total = counts['win'] + counts['loss'] + counts['draw']
        opening_list.append({
            'name': name,
            'win': counts['win'],
            'loss': counts['loss'],
            'draw': counts['draw'],
            'total': total,
            'win_rate': round(counts['win'] / total * 100) if total else 0
        })

    return render_template('viewstats.html', username=username, user=user, stats=stats,
                           matches=my_matches, elo_history=elo_history,
                           colour_stats=colour_stats,
                           top_terminations=top_terminations,
                           current_streak=current_streak,
                           streak_type=streak_type,
                           best_win_streak=best_win_streak,
                           opening_list=opening_list)


# Calendar page — displays all the user's matches as FullCalendar events, colour-coded by result
@main.route('/calendar')
def calendar():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))
    try:
        username = session['username']
        privilege = User.query.get(username)
        # Only show the current user's matches in the calendar
        all_matches = Match.query.filter(
            (Match.player == username) | (Match.opponent == username)
        ).order_by(Match.date_played.desc()).all()

        # Build display list with tournament info for the sidebar
        match_entries = []
        events = []
        for match in all_matches:
            result_lower = (match.result or '').lower()

            # Reverse result when user is the opponent, not the recording player
            if match.opponent == username and result_lower == 'win':
                user_result = 'loss'
            elif match.opponent == username and result_lower == 'loss':
                user_result = 'win'
            else:
                user_result = result_lower

            event_colour = '#6c757d'  # default gray for draw
            if user_result == 'pending':
                event_colour = '#ffc107'  # yellow for pending/upcoming
            elif user_result == 'win':
                event_colour = '#28a745'  # green for win
            elif user_result == 'loss':
                event_colour = '#dc3545'  # red for loss

            tournament = None
            tournament_name = ""
            if match.tournament_id:
                tournament = Tournament.query.get(match.tournament_id)
                if tournament:
                    tournament_name = f" - {tournament.name}"

            match_entries.append((match, tournament))

            if match.player == username:
                title = f"{match.player} vs {match.opponent}{tournament_name}"
            else:
                title = f"{match.opponent} vs {match.player}{tournament_name}"

            events.append({
                'title': title,
                'start': match.date_played.isoformat(),
                'backgroundColor': event_colour,
                'borderColor': event_colour,
                'extendedProps': {
                    'status': 'Upcoming' if user_result == 'pending' else 'Completed',
                    'result': user_result.capitalize() or 'Unknown',
                    'colour': (match.player_colour or '').capitalize()
                }
            })

        return render_template('calendar.html', matches=match_entries, events=events, username=username, user=privilege)
    except Exception:
        # Handle case where tables don't exist or no data
        return render_template('calendar.html', matches=[], events=[], username=session['username'], user=privilege)


# Login — accepts either username or email combined with password
@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            flash('Please enter both username and password!', 'error')
            return render_template('login.html')

        #Check if a valid username was entered
        user = User.query.filter_by(username=username).first()
        if user:
            if check_password_hash(user.password_hash, password):
                session['username'] = username
                flash('Login successful!', 'success')
                return redirect(url_for('main.home'))
            else:
                #The username was valid but password incorrect
                flash('Invalid username or password!', 'error')

        #Username was not valid, check if it's an email instead
        else:
            user = User.query.filter_by(email=username).first()
            if user and check_password_hash(user.password_hash, password):
                session['username'] = user.username
                flash('Login successful!', 'success')
                return redirect(url_for('main.home'))
            else:
                #Either password was incorrect or email not to valid user
                flash('Invalid username or password!', 'error')

    return render_template('login.html')


# New record — form for logging a past match or scheduling an upcoming one
@main.route('/new_record', methods=['GET', 'POST'])
def new_record():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))

    username = session['username']
    privilege = User.query.get(username)

    if request.method == 'POST':
        try:
            # Get form data with proper error handling
            username = session['username']
            privilege = User.query.get(username)
            match_type = request.form.get('match_type', 'past')
            opponent = request.form.get('opponent', '').strip()
            result = request.form.get('result', '').strip()
            colour = request.form.get('colour', '').strip()
            date_played_str = request.form.get('date_played', '').strip()

            # Validate required fields
            if not opponent or not result or not colour or not date_played_str:
                flash('Please fill in all required fields!', 'error')
                return render_template('new_record.html')

            # Parse date
            date_played = datetime.strptime(date_played_str, '%Y-%m-%d').date()

            # Handle optional fields based on match type
            game_record = request.form.get('game_record', '').strip()
            termination = request.form.get('termination', '').strip()
            time_played = request.form.get('time_played', '').strip()
            opening = request.form.get('opening', '').strip()

            # For upcoming matches, set default values
            if match_type == 'upcoming':
                termination = 'upcoming'
                game_record = ''

            date_created = datetime.now()

            # Combine date and time if time is provided
            if time_played:
                try:
                    time_obj = datetime.strptime(time_played, '%H:%M').time()
                    date_played = datetime.combine(date_played, time_obj)
                except ValueError:
                    date_played = datetime.combine(date_played, datetime.min.time())
            else:
                date_played = datetime.combine(date_played, datetime.min.time())

        except ValueError as e:
            flash(f'Invalid date format: {str(e)}', 'error')
            return render_template('new_record.html')
        except Exception as e:
            flash(f'Error processing form: {str(e)}', 'error')
            return render_template('new_record.html')

        record = Match(
            moves=game_record,
            player=session['username'],
            opponent=opponent,
            result=result,
            player_colour=colour,
            date_played=date_played,
            termination=termination,
            created_at=date_created
        )
        db.session.add(record)
        db.session.commit()

        if match_type == 'upcoming':
            flash('Match scheduled successfully!', 'success')
        else:
            flash('Game recorded successfully!', 'success')
        return redirect(url_for('main.home'))

    return render_template('new_record.html', user=privilege)


# Edit match — only the user who originally recorded the match can edit it
@main.route('/match/<int:match_id>/edit', methods=['GET', 'POST'])
def edit_match(match_id):
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))

    username = session['username']
    privilege = User.query.get(username)
    match = Match.query.get_or_404(match_id)

    if match.player != session['username']:
        flash('You can only edit your own matches.', 'error')
        return redirect(url_for('main.viewstats'))

    if request.method == 'POST':
        opponent = request.form.get('opponent', '').strip()
        result = request.form.get('result', '').strip()
        colour = request.form.get('colour', '').strip()
        date_played_str = request.form.get('date_played', '').strip()
        termination = request.form.get('termination', '').strip()
        game_record = request.form.get('game_record', '').strip()

        if not opponent or not result or not colour or not date_played_str:
            flash('Please fill in all required fields!', 'error')
            return render_template('edit_match.html', match=match)

        try:
            date_played = datetime.strptime(date_played_str, '%Y-%m-%d')
        except ValueError:
            flash('Invalid date format.', 'error')
            return render_template('edit_match.html', match=match)

        match.opponent = opponent
        match.result = result
        match.player_colour = colour
        match.date_played = date_played
        match.termination = termination
        match.moves = game_record
        db.session.commit()
        flash('Match updated successfully!', 'success')
        return redirect(url_for('main.viewstats'))

    return render_template('edit_match.html', match=match, user=privilege)


# Delete match — only the user who recorded it can delete it
@main.route('/match/<int:match_id>/delete', methods=['POST'])
def delete_match(match_id):
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))

    match = Match.query.get_or_404(match_id)
    if match.player != session['username']:
        flash('You can only delete your own matches.', 'error')
        return redirect(url_for('main.viewstats'))

    db.session.delete(match)
    db.session.commit()
    flash('Match deleted.', 'success')
    return redirect(url_for('main.viewstats'))


# Query/support page — lets users submit an issue report which is saved to the database
@main.route('/query', methods=['GET', 'POST'])
def query():
    #For users that are not logged in
    if 'username' not in session:
        if request.method == 'POST':
            try:
                email = request.form.get('email', '')
                issue_type = request.form['issue_type']
                title = request.form['title']
                description = request.form['description']
                timestamp = datetime.today()

                #Create a new query and store in database
                new_query = Queries(email=email, issue_type=issue_type, title=title, description=description, created_at=timestamp)
                db.session.add(new_query)
                db.session.commit()
                flash(f'Issue "{title}" has been submitted successfully! We will review it and get back to you soon.', 'success')
                return redirect(url_for('main.query'))
            except:
                flash('something went wrong!','error')
                return redirect(url_for('main.query'))
        
        return render_template('query.html')

    username = session['username']
    privilege = User.query.get(username)

    if request.method == 'POST':
        try:
            email = request.form.get('email', '')
            issue_type = request.form['issue_type']
            title = request.form['title']
            description = request.form['description']
            timestamp = datetime.today()

            #Create a new query and store in database
            new_query = Queries(email=email, issue_type=issue_type, title=title, description=description, created_at=timestamp)
            db.session.add(new_query)
            db.session.commit()
            flash(f'Issue "{title}" has been submitted successfully! We will review it and get back to you soon.', 'success')
            return redirect(url_for('main.query'))
        except:
            flash('something went wrong!','error')
            return redirect(url_for('main.query'))

    return render_template('query.html', username=username, user=privilege)


# FAQ page — static page, passes user object for nav bar if logged in
@main.route('/faq', methods=['GET', 'POST'])
def faq():
    if 'username' in session:
        username = session['username']
        privilege = User.query.get(username)
        return render_template('faq.html', user=privilege)
    return render_template('faq.html')


# Leaderboard — ranks all ChessMate users by ELO, excludes pending matches from calculations
@main.route('/leaderboard')
def leaderboard():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))

    username = session['username']
    privilege = User.query.get(username)
    all_users = User.query.all()
    players = []
    for u in all_users:
        s = _player_stats(u.username)
        players.append({
            'username': u.username,
            'wins': s['wins'],
            'losses': s['losses'],
            'draws': s['draws'],
            'win_rate': s['win_rate'],
            'elo': s['elo']
        })

    players.sort(key=lambda x: x['elo'], reverse=True)
    return render_template('leaderboard.html', players=players, username=username, user=privilege)


# Daily puzzle — fetches today's puzzle from the lichess API and renders an interactive board
@main.route('/puzzle')
def daily_puzzle():
    if 'username' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('main.login'))

    username = session['username']
    privilege = User.query.get(username)

    try:
        req = urllib.request.Request(
            'https://lichess.org/api/puzzle/daily',
            headers={'User-Agent': 'ChessMate/1.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        puzzle = data['puzzle']
        game = data['game']
    except Exception:
        flash('Could not load the daily puzzle. Try again later.', 'danger')
        return redirect(url_for('main.home'))

    side_to_move = puzzle['fen'].split()[1]  # 'w' or 'b'
    return render_template('puzzle.html',
        user=privilege,
        username=username,
        fen=puzzle['fen'],
        solution=puzzle['solution'],
        themes=puzzle['themes'],
        rating=puzzle['rating'],
        puzzle_id=puzzle['id'],
        last_move=puzzle.get('lastMove', ''),
        side_to_move=side_to_move,
        players=game.get('players', []),
    )


# Head-to-head — shows win/loss/draw breakdown and match history between two specific users
@main.route('/h2h')
def h2h():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))

    me = session['username']
    privilege = User.query.get(me)
    opponent_name = request.args.get('opponent', '').strip()
    all_users = [u.username for u in User.query.filter(User.username != me).all()]

    stats = None
    matches_display = []

    if opponent_name:
        # Matches recorded by me against them, and by them against me
        my_matches = Match.query.filter_by(player=me, opponent=opponent_name).order_by(Match.date_played.desc()).all()
        their_matches = Match.query.filter_by(player=opponent_name, opponent=me).order_by(Match.date_played.desc()).all()

        my_wins = my_losses = my_draws = 0

        for m in my_matches:
            r = (m.result or '').lower()
            if r == 'pending':
                continue
            if r == 'win':
                my_wins += 1
            elif r == 'loss':
                my_losses += 1
            else:
                my_draws += 1
            matches_display.append({
                'date': m.date_played.strftime('%Y-%m-%d') if m.date_played else '—',
                'player_result': m.result or 'Unknown',
                'colour': m.player_colour,
                'termination': m.termination or '—',
            })

        for m in their_matches:
            r = (m.result or '').lower()
            if r == 'pending':
                continue
            # Their win = my loss, their loss = my win
            if r == 'win':
                my_losses += 1
                my_result = 'Loss'
            elif r == 'loss':
                my_wins += 1
                my_result = 'Win'
            else:
                my_draws += 1
                my_result = 'Draw'
            opp_colour = 'black' if m.player_colour == 'white' else 'white'
            matches_display.append({
                'date': m.date_played.strftime('%Y-%m-%d') if m.date_played else '—',
                'player_result': my_result,
                'colour': opp_colour,
                'termination': m.termination or '—',
            })

        matches_display.sort(key=lambda x: x['date'], reverse=True)
        total = my_wins + my_losses + my_draws
        stats = {
            'my_wins': my_wins,
            'my_losses': my_losses,
            'my_draws': my_draws,
            'opp_wins': my_losses,
            'opp_losses': my_wins,
            'opp_draws': my_draws,
            'total': total,
        }

    return render_template('h2h.html', username=me, opponent=opponent_name,
                           all_users=all_users, stats=stats, matches=matches_display, user=privilege)


# Logout — clears the session and redirects to the landing page
@main.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out!', 'success')
    return redirect(url_for('main.home'))


# Signup — validates the new account details and creates a user record
@main.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('signup.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long!', 'error')
            return render_template('signup.html')

        if User.query.filter_by(username=username).first():
            flash('Username already taken, please choose another!', 'error')
            return render_template('signup.html')

        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'error')
            return render_template('signup.html')

        password_hash = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=password_hash)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('main.login'))

    return render_template('signup.html')


# Forgot password — three-step flow: enter email, verify code, set new password
@main.route('/forgotpassword', methods=['GET', 'POST'])
def forgotpassword():
    if 'resetstep' not in session:
        session['resetstep'] = 1

    if request.method == 'POST':
        if session['resetstep'] == 1:
            if request.form.get('Email'):
                session['resetemail'] = request.form.get('Email')
                user = User.query.filter_by(email=session['resetemail']).first()
                if user:
                    code = os.urandom(6)
                    readablecode = ""
                    for i in code:
                        readablecode += str((int(i)%10))
                    session['resetcode'] = readablecode
                    reset_password_email(user.username, session['resetemail'], readablecode)
                    print("Email matched to user, sending reset code")
                else:
                    print("Email does not match to user")
                flash('If your account is valid, a verification code has been sent to your email', 'success')
                session['resetstep'] = 2
                return redirect(url_for('main.forgotpassword'))
        elif session['resetstep'] == 2:
            if request.form.get('Code'):
                inputcode = request.form.get('Code')
                if session['resetcode'] and inputcode == session['resetcode']:
                    flash('Verification successful! Please enter your new password.', 'success')
                    session['resetstep'] = 3
                    return redirect(url_for('main.forgotpassword'))
                else:
                    session['resetstep'] = 1
                    session.pop('resetcode', None)
                    flash('Invalid verification code! Please try again.', 'error')
                    return redirect(url_for('main.forgotpassword'))

        elif session['resetstep'] == 3:
            if request.form.get('Password') and request.form.get('Confirm_Password'):
                password = request.form.get('Password')
                confirm_password = request.form.get('Confirm_Password')
                if password != confirm_password:
                    flash('Passwords do not match! Please try again.', 'error')
                    return redirect(url_for('main.forgotpassword'))
                elif len(password) < 6:
                    flash('Password must be at least 6 characters long! Please try again.', 'error')
                    return redirect(url_for('main.forgotpassword'))
                else:
                    # Update user's password
                    user = User.query.filter_by(email=session.get('resetemail')).first()
                    if user:
                        user.password_hash = generate_password_hash(password)
                        try:
                            db.session.commit()
                        except Exception as e:
                            db.session.rollback()
                            print("DB Error:", str(e))
                        flash('Your password has been reset successfully! Please log in with your new password.', 'success')
                        session.pop('resetcode', None)
                        session.pop('resetstep', None)
                        return redirect(url_for('main.login'))
                    else:
                        flash('An error occurred while resetting your password. Please try again.', 'error')
                        session['resetstep'] = 1
                        return redirect(url_for('main.forgotpassword'))
            else:
                flash('Please fill in all required fields!', 'error')
                return redirect(url_for('main.forgotpassword'))
    else:
        return render_template('forgotpassword.html', resetstep = session['resetstep'])


# Admin dashboard — only accessible to users with is_admin flag set to True
@main.route('/Dashboard')
def admin_dashboard():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))

    username = session['username']
    privilege = User.query.get(username)

    #Get 10 of the latest queries
    latest_query = Queries.query.order_by(Queries.created_at.desc()).limit(10)

    #Get new queries based on type
    new_query_count = Queries.query.filter_by(status='new').count()
    bug = Queries.query.filter_by(status='new', issue_type='bug').count()
    feature = Queries.query.filter_by(status='new', issue_type='feature').count()
    question = Queries.query.filter_by(status='new', issue_type='question').count()
    other = Queries.query.filter_by(status='new', issue_type='other').count()

    #Get current count of queries based on status
    new = Queries.query.filter_by(status='new').count()
    in_progress = Queries.query.filter_by(status='in progress').count()
    completed = Queries.query.filter_by(status='completed').count()

    #Check if the current account is an admin account, otherwise deny access to page
    if privilege.is_admin:
        return render_template('home_admin.html', username=username, new_count=new_query_count,
                               latest=latest_query, new=new,
                               in_progress=in_progress, completed=completed,
                               user=privilege, bug=bug, feature=feature,
                               question=question, other=other)
    else:
        flash("sorry, you must be an admin to access this page!",'error')
        return redirect(url_for('main.home'))


# View queries — admin-only page showing all submitted support queries grouped by type
@main.route('/Viewqueries')
def view_queries():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))

    username = session['username']
    privilege = User.query.get(username)

    #Get latest queries and number of queries received today
    queries = Queries.query.order_by(Queries.created_at.desc()).all()
    new = Queries.query.filter_by(status ='new').count()
    in_progress = Queries.query.filter_by(status = 'in progress').count()
    completed = Queries.query.filter_by(status = 'completed').count()

    #Check if the current account is an admin account, otherwise deny access to page
    if privilege.is_admin:
        return render_template('view_queries.html', username=username, 
                               query=queries, user=privilege,
                               new=new, in_progress=in_progress,
                               completed=completed)
    else:
        flash("sorry, you must be an admin to access this page!",'error')
        return redirect(url_for('main.home'))

@main.route('/current_query/<id>')
def current_query(id):
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))
    
    username = session['username']
    privilege = User.query.get(username)
    current_query=Queries.query.get_or_404(id)

    #Check if the current account is an admin account, otherwise deny access to page
    if privilege.is_admin:
        return render_template('current_query.html', username=username, 
                                user=privilege, query=current_query)
    else:
        flash("sorry, you must be an admin to access this page!",'error')
        return redirect(url_for('main.home'))

@main.route('/update_query/<id>', methods=['GET', 'POST'])
def update_query(id):
    current_query=Queries.query.get_or_404(id)

    if request.method == 'POST':
        current_query.status = request.form['issue_status']
        current_query.notes = request.form.get('notes', '')
        email_subject = request.form.get('subject', '')
        email_body = request.form.get('body','')
        
        #Create a new query and store in database
        try:
            if email_body and current_query.email:
                send_reply(email_subject,current_query.email,email_body)
                flash('Email sent!', 'success')
            db.session.commit()
            flash('Changes to query has been made.', 'success')
            return redirect(url_for('main.view_queries'))
        except:
            flash('Error! changes to query were not saved', 'error')
            return redirect(url_for('main.view_queries'))
    else:
        return redirect(url_for('main.current_query'))

@main.route('/delete_query/<id>', methods=['GET','POST'])
def delete_query(id):
    chosen_query=Queries.query.get_or_404(id)
    
    #Check if the given query can be deleted
    try:
        db.session.delete(chosen_query)
        db.session.commit()
        flash('Query deleted!','success')
        return redirect(url_for('main.view_queries'))
    except:
        flash('Failed to delete query','success')
        return redirect(url_for('main.view_queries'))
