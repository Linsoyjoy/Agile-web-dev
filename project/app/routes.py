import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from app import db
from .blueprints import main
from .models import User, Tournament, Match
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
    upload_dir = os.path.join(main.static_folder, 'images', 'profiles')
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
    
    # Get recent activity (last 5 completed matches)
    recent_matches = Match.query.filter(
        (Match.player == username) | (Match.opponent == username),
        Match.result != 'pending'
    ).order_by(Match.date_played.desc()).limit(5).all()
    
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
    return render_template('friends.html', username=session['username'])

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
        
        # Add to recent matches
        recent_matches.append({
            'opponent': opponent,
            'result': user_result,
            'date': match.date_played
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
                if m.result == 'win':
                    u_wins += 1
            else:
                if m.result == 'loss':
                    u_wins += 1
        user_rankings.append((u.username, u_wins))
    
    user_rankings.sort(key=lambda x: x[1], reverse=True)
    user_rank = next((i+1 for i, (u, _) in enumerate(user_rankings) if u == username), len(user_rankings))
    
    # Calculate color-specific win rates
    white_wins = white_losses = white_draws = 0
    black_wins = black_losses = black_draws = 0
    
    for match in user_matches:
        if match.player_colour.lower() == 'white':
            if match.result.lower() == 'win':
                white_wins += 1
            elif match.result.lower() == 'loss':
                white_losses += 1
            else:
                white_draws += 1
        else:  # black
            if match.result.lower() == 'win':
                black_wins += 1
            elif match.result.lower() == 'loss':
                black_losses += 1
            else:
                black_draws += 1
    
    white_total = white_wins + white_losses + white_draws
    black_total = black_wins + black_losses + black_draws
    white_win_rate = round((white_wins / white_total * 100) if white_total > 0 else 0, 1)
    black_win_rate = round((black_wins / black_total * 100) if black_total > 0 else 0, 1)
    
    # Analyze weaknesses based on performance data
    weaknesses = []
    if losses > wins * 1.5:
        weaknesses.append("High loss rate - focus on defensive strategies")
    if black_win_rate < white_win_rate - 10:
        weaknesses.append("Struggles playing as black - study black opening strategies")
    if white_win_rate < black_win_rate - 10:
        weaknesses.append("Struggles playing as white - improve opening repertoire")
    if total_games < 10:
        weaknesses.append("Limited experience - play more games to improve")
    
    # Analyze termination patterns
    timeouts = sum(1 for match in user_matches if match.termination and 'timeout' in match.termination.lower())
    resignations = sum(1 for match in user_matches if match.termination and 'resign' in match.termination.lower())
    
    if timeouts > total_games * 0.3:
        weaknesses.append("Frequent timeouts - improve time management")
    if resignations > total_games * 0.4:
        weaknesses.append("Early resignations - develop endgame skills")
    
    weaknesses_text = "; ".join(weaknesses) if weaknesses else "Keep practicing to identify areas for improvement!"
    
    user_stats = {
        'wins': wins,
        'losses': losses,
        'draws': draws,
        'win_rate': win_rate,
        'white_win_rate': white_win_rate,
        'black_win_rate': black_win_rate,
        'ranking': f'#{user_rank}',
        'recent_matches': recent_matches,
        'weaknesses': weaknesses_text
    }
    
    return render_template('profile.html', user=user, stats=user_stats, username=username)

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
    }
    return render_template('viewstats.html', username=username, user=user, stats=stats)

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
            event_colour = '#6c757d'  # default gray for draw
            if result_lower == 'pending':
                event_colour = '#ffc107'  # yellow for pending/upcoming
            elif result_lower == 'win':
                event_colour = '#28a745'  # green for win
            elif result_lower == 'loss':
                event_colour = '#dc3545'  # red for loss

            tournament = None
            tournament_name = ""
            if match.tournament_id:
                tournament = Tournament.query.get(match.tournament_id)
                if tournament:
                    tournament_name = f" - {tournament.name}"

            match_entries.append((match, tournament))

            events.append({
                'title': f"{match.player} vs {match.opponent}{tournament_name}",
                'start': match.date_played.isoformat(),
                'backgroundColor': event_colour,
                'borderColor': event_colour,
                'extendedProps': {
                    'status': 'Upcoming' if result_lower == 'pending' else 'Completed',
                    'result': (match.result or '').capitalize() or 'Unknown',
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

@main.route('/query', methods=['GET', 'POST'])
def query():
    if 'username' not in session:
        flash('Please log in to access this page!', 'error')
        return redirect(url_for('main.login'))
    
    if request.method == 'POST':
        issue_type = request.form['issue_type']
        title = request.form['title']
        description = request.form['description']
        priority = request.form['priority']
        email = request.form.get('email', '')
        
        # TODO: Store issue in database or send email
        # For now, just show success message
        flash(f'Issue "{title}" has been submitted successfully! We will review it and get back to you soon.', 'success')
        return redirect(url_for('main.query'))

    return render_template('query.html', username=session['username'])

@main.route('/faq', methods=['GET', 'POST'])
def faq():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        query = request.form['query']
        # TODO: Store query in database or send email
        flash('Your query has been submitted successfully! We will get back to you soon.', 'success')
        return redirect(url_for('main.faq'))

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
                        return redirect(url_for('main.login'))
                    else:
                        flash('An error occurred while resetting your password. Please try again.', 'error')
                        session['resetstep'] = 1
                        return render_template('forgotpassword.html', resetstep = 1)
    return render_template('forgotpassword.html', resetstep = 1)