import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from app import db, csrf
from .blueprints import main
from .models import User, Tournament, Match, Friendship, Query
from .forgot_password import reset_password_email
from datetime import date, datetime

@main.context_processor
def inject_profile_pic():
    if 'username' in session:
        user = User.query.filter_by(username=session['username']).first()
        if user:
            return {'profile_pic': user.profile_pic}
    return {'profile_pic': None}

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
                         recent_matches=recent_matches)

@main.route('/friends')
def friends():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))
    
    current_user = session['username']
    
    # Get all users and calculate their rankings
    all_users = User.query.all()
    players = []
    
    for u in all_users:
        matches = Match.query.filter(
            (Match.player == u.username) | (Match.opponent == u.username)
        ).all()
        
        wins = losses = draws = 0
        for m in matches:
            r = (m.result or '').lower()
            if m.player == u.username:
                if r == 'win': 
                    wins += 1
                elif r == 'loss': 
                    losses += 1
                elif r == 'draw': 
                    draws += 1
            else:
                if r == 'loss': 
                    wins += 1
                elif r == 'win': 
                    losses += 1
                elif r == 'draw': 
                    draws += 1
        
        total = wins + losses + draws
        win_rate = round((wins / total * 100) if total > 0 else 0, 1)
        
        # Simple ELO calculation based on wins and win rate
        elo = 1200 + (wins * 10) + (win_rate * 2)
        
        players.append({
            'username': u.username,
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'win_rate': win_rate,
            'elo': round(elo),
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
            friend_matches = Match.query.filter(
                (Match.player == friend_username) | (Match.opponent == friend_username)
            ).all()
            
            wins = losses = draws = 0
            for m in friend_matches:
                r = (m.result or '').lower()
                if m.player == friend_username:
                    if r == 'win': wins += 1
                    elif r == 'loss': losses += 1
                    elif r == 'draw': draws += 1
                else:
                    if r == 'loss': wins += 1
                    elif r == 'win': losses += 1
                    elif r == 'draw': draws += 1
            
            total = wins + losses + draws
            win_rate = round((wins / total * 100) if total > 0 else 0, 1)
            elo = 1200 + (wins * 10) + (win_rate * 2)
            
            current_friends.append({
                'username': friend_username,
                'wins': wins,
                'losses': losses,
                'draws': draws,
                'win_rate': win_rate,
                'elo': round(elo)
            })
    
    # Build friends-only leaderboard (current user + accepted friends)
    friend_usernames = {f['username'] for f in current_friends}
    friend_usernames.add(current_user)
    friends_leaderboard = [p for p in players if p['username'] in friend_usernames]
    for i, p in enumerate(friends_leaderboard):
        p['friends_rank'] = i + 1

    return render_template('friends.html', username=current_user, players=players,
                         pending_requests=pending_requests, current_friends=current_friends,
                         friends_leaderboard=friends_leaderboard)

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
    
    # Get user's match statistics
    user_matches = Match.query.filter(
        (Match.player == username) | (Match.opponent == username)
    ).all()
    
    wins = losses = draws = 0
    recent_matches = []
    
    for match in user_matches:
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
                continue
        
        recent_matches.append({
            'opponent': opponent,
            'result': user_result,
            'date': match.date_played,
            'colour': match.player_colour if match.player == username else ('black' if match.player_colour == 'white' else 'white')
        })
    
    total_games = wins + losses + draws
    win_rate = round((wins / total_games * 100) if total_games > 0 else 0, 1)
    
    # Calculate ranking
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
    
    # Calculate ELO
    elo = 1200 + (wins * 10) + (win_rate * 2)
    
    user_stats = {
        'wins': wins,
        'losses': losses,
        'draws': draws,
        'win_rate': win_rate,
        'elo': round(elo),
        'ranking': f'#{user_rank}',
        'recent_matches': sorted(recent_matches, key=lambda x: x['date'], reverse=True)[:5]
    }
    
    return render_template('view_user.html', user=user, stats=user_stats, current_user=current_user, 
                         friendship_status=friendship_status, friendship=friendship)

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

@main.route('/save_weaknesses', methods=['POST'])
def save_weaknesses():
    if 'username' not in session:
        return redirect(url_for('main.login'))
    user = User.query.filter_by(username=session['username']).first()
    user.weaknesses = request.form.get('weaknesses', '').strip()
    db.session.commit()
    flash('Weaknesses saved!', 'success')
    return redirect(url_for('main.profile'))

@main.route('/lookup_user')
def lookup_user():
    username = request.args.get('username', '').strip()
    if not username:
        return jsonify({'found': False})
    user = User.query.filter_by(username=username).first()
    return jsonify({'found': bool(user)})

@main.route('/viewstats')
def viewstats():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))

    username = session['username']
    user = User.query.filter_by(username=username).first()

    user_matches = Match.query.filter(
        (Match.player == username) | (Match.opponent == username)
    ).all()

    wins = losses = draws = 0
    for m in user_matches:
        r = (m.result or '').lower()
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

    # Compute simple ranking based on wins across all users
    all_users = User.query.all()
    rankings = []
    for u in all_users:
        u_matches = Match.query.filter(
            (Match.player == u.username) | (Match.opponent == u.username)
        ).all()
        u_wins = 0
        for m in u_matches:
            r = (m.result or '').lower()
            if m.player == u.username and r == 'win':
                u_wins += 1
            elif m.opponent == u.username and r == 'loss':
                u_wins += 1
        rankings.append((u.username, u_wins))
    rankings.sort(key=lambda x: x[1], reverse=True)
    user_rank = next((i + 1 for i, (u, _) in enumerate(rankings) if u == username), len(rankings) or 1)

    stats = {
        'wins': wins,
        'losses': losses,
        'draws': draws,
        'win_rate': win_rate,
        'ranking': f'#{user_rank}',
        'ELO': 1200 + (wins * 10),
    }

    my_matches = Match.query.filter(
        (Match.player == username) | (Match.opponent == username)
    ).order_by(Match.date_played.desc()).all()
    return render_template('viewstats.html', username=username, user=user, stats=stats, matches=my_matches)

@main.route('/calendar')
def calendar():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))
    try:
        username = session['username']
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

        return render_template('calendar.html', matches=match_entries, events=events, username=username)
    except Exception:
        # Handle case where tables don't exist or no data
        return render_template('calendar.html', matches=[], events=[], username=session['username'])

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

@main.route('/new_record', methods=['GET', 'POST'])
def new_record():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))
    if request.method == 'POST':
        try:
            # Get form data with proper error handling
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
            location = request.form.get('location', '').strip()
            notes = request.form.get('notes', '').strip()
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

    return render_template('new_record.html')

@main.route('/match/<int:match_id>/edit', methods=['GET', 'POST'])
def edit_match(match_id):
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))

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

    return render_template('edit_match.html', match=match)


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

@main.route('/query', methods=['GET', 'POST'])
def query():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))
    
    if request.method == 'POST':
        issue_type = request.form['issue_type']
        title = request.form['title']
        description = request.form['description']
        email = request.form.get('email', '')
        
        # TODO: Store issue in database or send email
        # For now, just show success message
        flash(f'Issue "{title}" has been submitted successfully! We will review it and get back to you soon.', 'success')
        return redirect(url_for('main.query'))

    return render_template('query.html', username=session['username'])

@main.route('/faq', methods=['GET', 'POST'])
def faq():
    return render_template('faq.html')

@main.route('/leaderboard')
def leaderboard():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))

    all_users = User.query.all()
    players = []
    for u in all_users:
        matches = Match.query.filter(
            (Match.player == u.username) | (Match.opponent == u.username)
        ).all()
        wins = losses = draws = 0
        for m in matches:
            r = (m.result or '').lower()
            if m.player == u.username:
                if r == 'win': wins += 1
                elif r == 'loss': losses += 1
                elif r == 'draw': draws += 1
            else:
                if r == 'loss': wins += 1
                elif r == 'win': losses += 1
                elif r == 'draw': draws += 1
        total = wins + losses + draws
        win_rate = round((wins / total * 100) if total > 0 else 0, 1)
        elo = 1200 + (wins * 10) + (win_rate * 2)
        players.append({
            'username': u.username,
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'win_rate': win_rate,
            'elo': round(elo)
        })

    players.sort(key=lambda x: x['elo'], reverse=True)
    return render_template('leaderboard.html', players=players, username=session['username'])

@main.route('/h2h')
def h2h():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))

    me = session['username']
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
                           all_users=all_users, stats=stats, matches=matches_display)

@main.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out!', 'success')
    return redirect(url_for('main.home'))

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