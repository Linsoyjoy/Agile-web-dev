import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from app import app, db
from app.models import User, Tournament, Match, GameRecord
import datetime

@app.route('/')
def home():
    if 'username' not in session:
        return render_template('landing.html')
    return render_template('home.html', username=session['username'])

@app.route('/friends')
def friends():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('login'))
    return render_template('friends.html', username=session['username'])

@app.route('/profile')
def profile():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('login'))
    
    username = session['username']
    user = User.query.filter_by(username=username).first()
    
    if not user:
        flash('User not found!', 'error')
        return redirect(url_for('login'))
    
    # Calculate real statistics from match data
    user_matches = Match.query.filter(
        (Match.player1 == username) | (Match.player2 == username)
    ).all()
    
    wins = 0
    losses = 0
    draws = 0
    recent_matches = []
    
    for match in user_matches:
        # Determine if user is player1 or player2 and get result
        if match.player1 == username:
            if match.result == 'win':
                wins += 1
                opponent = match.player2
            elif match.result == 'loss':
                losses += 1
                opponent = match.player2
            else:  # draw
                draws += 1
                opponent = match.player2
        else:  # user is player2
            if match.result == 'win':
                losses += 1  # player1 won, so player2 lost
                opponent = match.player1
            elif match.result == 'loss':
                wins += 1  # player1 lost, so player2 won
                opponent = match.player1
            else:  # draw
                draws += 1
                opponent = match.player1
        
        # Add to recent matches (convert result to user's perspective)
        user_result = 'Win' if match.player2 == username and match.result == 'loss' else \
                     'Loss' if match.player2 == username and match.result == 'win' else \
                     match.result.capitalize()
        
        recent_matches.append({
            'opponent': opponent,
            'result': user_result
        })
    
    # Sort recent matches by date (most recent first) and take last 3
    recent_matches = sorted(recent_matches, 
                          key=lambda x: next((m.scheduled_date for m in user_matches), datetime.min), 
                          reverse=True)[:3]
    
    total_games = wins + losses + draws
    win_rate = round((wins / total_games * 100) if total_games > 0 else 0, 1)
    
    # Calculate ranking based on total wins (simple implementation)
    all_users = User.query.all()
    user_rankings = []
    for u in all_users:
        u_matches = Match.query.filter(
            (Match.player1 == u.username) | (Match.player2 == u.username)
        ).all()
        u_wins = 0
        for m in u_matches:
            if m.player1 == u.username:
                if m.result == 'win':
                    u_wins += 1
            else:
                if m.result == 'loss':
                    u_wins += 1
        user_rankings.append((u.username, u_wins))
    
    user_rankings.sort(key=lambda x: x[1], reverse=True)
    user_rank = next((i+1 for i, (u, _) in enumerate(user_rankings) if u == username), len(user_rankings))
    
    user_stats = {
        'wins': wins,
        'losses': losses,
        'draws': draws,
        'win_rate': win_rate,
        'white_win_rate': win_rate,  # Simplified - would need to track piece colors
        'black_win_rate': win_rate,  # Simplified - would need to track piece colors
        'ranking': f'#{user_rank}',
        'recent_matches': recent_matches,
        'weaknesses': 'Takes too long to decide next move.'  # Would need AI analysis
    }
    
    return render_template('profile.html', user=user, stats=user_stats, username=username)

@app.route('/viewstats')
def viewstats():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('login'))
    return render_template('viewstats.html', username=session['username'])

@app.route('/calendar')
def calendar():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('login'))
    try:
        # Get all matches with tournament info (show all for now, will filter by user later)
        matches = db.session.query(Match, Tournament).join(Tournament).order_by(Match.scheduled_date).all()
        
        # Format events for FullCalendar
        events = []
        for match, tournament in matches:
            event_color = '#6c757d'  # default gray for draw
            if match.result == 'pending':
                event_color = '#ffc107'  # yellow for pending
            elif match.result == 'win':
                event_color = '#28a745'  # green for win
            elif match.result == 'loss':
                event_color = '#dc3545'  # red for loss
                
            events.append({
                'title': f"{match.player1} vs {match.player2} - {tournament.name}",
                'start': match.scheduled_date.isoformat(),
                'backgroundColor': event_color,
                'borderColor': event_color
            })
        
        return render_template('calendar.html', matches=matches, events=events, username=session['username'])
    except Exception as e:
        # Handle case where tables don't exist or no data
        return render_template('calendar.html', matches=[], events=[], username=session['username'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['Username']
        password = request.form['Password']
        if not username or not password:
            flash('Please enter both username and password!', 'error')
            return render_template('login.html')
    
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password!', 'error')
    
    return render_template('login.html')

@app.route('/new_record', methods=['GET', 'POST'])
def new_record():
    if request.method == 'POST':
        opponent = request.form['opponent']
        result = request.form['result']
        colour = request.form['colour']
        opening = request.form.get('opening', '')
        moves = request.form.get('moves', None)
        date_played = request.form['date_played']
        notes = request.form.get('notes', '')

        if moves:
            try:
                moves = int(moves)
            except ValueError:
                flash('Number of moves must be a valid number!', 'error')
                return render_template('new_record.html')

        record = GameRecord(
            opponent=opponent,
            result=result,
            colour=colour,
            opening=opening,
            moves=moves,
            date_played=date_played,
            notes=notes
        )
        db.session.add(record)
        db.session.commit()
        flash('Game recorded successfully!', 'success')
        return redirect(url_for('viewstats'))

    return render_template('new_record.html')

@app.route('/faq', methods=['GET', 'POST'])
def faq():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        query = request.form['query']
        # TODO: Store query in database or send email
        flash('Your query has been submitted successfully! We will get back to you soon.', 'success')
        return redirect(url_for('faq'))

    return render_template('faq.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out!', 'success')
    return redirect(url_for('home'))

@app.route('/signup', methods=['GET', 'POST'])
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
        return redirect(url_for('login'))
    
    return render_template('signup.html')