import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from app import app, db
from app.models import User, Tournament, Match
from app.forgot_password import reset_password_email
from datetime import date
import datetime

@app.context_processor
def inject_profile_pic():
    if 'username' in session:
        user = User.query.filter_by(username=session['username']).first()
        if user:
            return {'profile_pic': user.profile_pic}
    return {'profile_pic': None}

@app.route('/upload_profile_pic', methods=['POST'])
def upload_profile_pic():
    if 'username' not in session:
        return redirect(url_for('login'))
    if 'profile_pic' not in request.files or request.files['profile_pic'].filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('profile'))
    file = request.files['profile_pic']
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in {'png', 'jpg', 'jpeg', 'gif'}:
        flash('Only PNG, JPG and GIF files are allowed', 'error')
        return redirect(url_for('profile'))
    filename = secure_filename(session['username'] + '.' + ext)
    upload_dir = os.path.join(app.static_folder, 'images', 'profiles')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, filename))
    user = User.query.filter_by(username=session['username']).first()
    user.profile_pic = filename
    db.session.commit()
    flash('Profile picture updated!', 'success')
    return redirect(url_for('profile'))

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
        (Match.player == username)
    ).all()
    
    wins = 0
    losses = 0
    draws = 0
    recent_matches = []
    
    for match in user_matches:
        # Determine if user is player1 or player2 and get result
        if match.result == 'Win':
            wins += 1
            opponent = match.opponent
        elif match.result == 'Loss':
            losses += 1
            opponent = match.opponent
        else:  # draw
            draws += 1
            opponent = match.opponent
        
        # Add to recent matches (convert result to user's perspective)
        user_result = 'Win' if match.opponent == username and match.result == 'Loss' else \
                     'Loss' if match.opponent == username and match.result == 'Win' else \
                     match.result.capitalize()
        
        recent_matches.append({
            'opponent': opponent,
            'result': user_result
        })
    
    # Sort recent matches by date (most recent first) and take last 3
    recent_matches = sorted(recent_matches, 
                          key=lambda x: next((m.date_played for m in user_matches), datetime.datetime.min), 
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
        'white_win_rate': win_rate,  # Simplified - would need to track piece colours
        'black_win_rate': win_rate,  # Simplified - would need to track piece colours
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
        matches = db.session.query(Match, Tournament).join(Tournament).order_by(Match.date_played).all()
        
        # Format events for FullCalendar
        events = []
        for match, tournament in matches:
            event_colour = '#6c757d'  # default gray for draw
            if match.result == 'pending':
                event_colour = '#ffc107'  # yellow for pending
            elif match.result == 'win':
                event_colour = '#28a745'  # green for win
            elif match.result == 'loss':
                event_colour = '#dc3545'  # red for loss
                
            events.append({
                'title': f"{match.player} vs {match.opponent} - {tournament.name}",
                'start': match.date_played.isoformat(),
                'backgroundcolour': event_colour,
                'bordercolour': event_colour
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
    
        #Check if a valid username was entered
        user = User.query.filter_by(username=username).first()
        if user:
            if check_password_hash(user.password_hash, password):
                session['username'] = username
                flash('Login successful!', 'success')
                return redirect(url_for('home'))
            else:
                #The username was valid but password incorrect
                flash('Invalid username or password!', 'error')


        #Username was not valid, check if it's an email instead 
        else:
            user = User.query.filter_by(email=username).first()
            if user and check_password_hash(user.password_hash, password):
                session['username'] = user.username
                flash('Login successful!', 'success')
                return redirect(url_for('home'))
            else:
                #Either password was incorrect or email not to valid user
                flash('Invalid username or password!', 'error')
    
    return render_template('login.html')

@app.route('/new_record', methods=['GET', 'POST'])
def new_record():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            opponent = request.form['opponent']
            result = request.form['result']
            colour = request.form['colour']
            termination = request.form['termination']
            date_played = date.fromisoformat(request.form['date_played'])
            game_record = request.form.get('game_record', '')
            date_created = date.today()
        except Exception as e:
            flash('Please fill in all required fields correctly!', 'error')
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
        flash('Game recorded successfully!', 'success')
        return redirect(url_for('viewstats'))

    return render_template('new_record.html')

@app.route('/query', methods=['GET', 'POST'])
def query():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        issue_type = request.form['issue_type']
        title = request.form['title']
        description = request.form['description']
        priority = request.form['priority']
        email = request.form.get('email', '')
        
        # TODO: Store issue in database or send email
        # For now, just show success message
        flash(f'Issue "{title}" has been submitted successfully! We will review it and get back to you soon.', 'success')
        return redirect(url_for('query'))

    return render_template('query.html', username=session['username'])

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

@app.route('/leaderboard')
def leaderboard():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('login'))

    all_users = User.query.all()
    players = []
    for u in all_users:
        matches = Match.query.filter(
            (Match.player == u.username) | (Match.opponent == u.username)
        ).all()
        wins = losses = draws = 0
        for m in matches:
            if m.player == u.username:
                if m.result == 'win': wins += 1
                elif m.result == 'loss': losses += 1
                else: draws += 1
            else:
                if m.result == 'loss': wins += 1
                elif m.result == 'win': losses += 1
                else: draws += 1
        total = wins + losses + draws
        players.append({
            'username': u.username,
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'win_rate': round((wins / total * 100) if total > 0 else 0, 1)
        })

    players.sort(key=lambda x: (x['wins'], x['win_rate']), reverse=True)
    return render_template('leaderboard.html', players=players, username=session['username'])

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

@app.route('/forgotpassword', methods=['GET', 'POST'])
def forgotpassword():
    if 'resetstep' not in session:
        session['resetstep'] = 1

    if request.method == 'POST':
        if session['resetstep'] != 2 and session['resetstep'] != 3:
            length = len(request.form)
            if request.form.get('Email') and length == 1:
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
                return render_template('forgotpassword.html', resetstep = 2)
        elif session['resetstep'] == 2:
            length = len(request.form)
            if request.form.get('Code') and length == 1:
                inputcode = request.form.get('Code')
                if inputcode == session['resetcode']:
                    flash('Verification successful! Please enter your new password.', 'success')
                    session['resetstep'] = 3
                    return render_template('forgotpassword.html', resetstep = 3)
                else:
                    session['resetstep'] = 1
                    session.pop('resetcode', None)
                    flash('Invalid verification code! Please try again.', 'error')

                    return render_template('forgotpassword.html', resetstep = 1)
        elif session['resetstep'] == 3:
            length = len(request.form)
            if request.form.get('Password') and request.form.get('Confirm_Password') and length == 2:
                password = request.form.get('Password')
                confirm_password = request.form.get('Confirm_Password')
                if password != confirm_password:
                    flash('Passwords do not match! Please try again.', 'error')
                    return render_template('forgotpassword.html', resetstep = 3)
                elif len(password) < 6:
                    flash('Password must be at least 6 characters long! Please try again.', 'error')
                    return render_template('forgotpassword.html', resetstep = 3)
                else:
                    # Update user's password
                    user = User.query.filter_by(email=session.get('resetemail')).first()
                    if user:
                        user.password_hash = generate_password_hash(password)
                        db.session.commit()
                        flash('Your password has been reset successfully! Please log in with your new password.', 'success')
                        session.pop('resetcode', None)
                        session['resetstep'] = 1
                        return redirect(url_for('login'))
                    else:
                        flash('An error occurred while resetting your password. Please try again.', 'error')
                        session['resetstep'] = 1
                        return render_template('forgotpassword.html', resetstep = 1)
    return render_template('forgotpassword.html', resetstep = 1)