import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)
class User(db.Model):
    username = db.Column(db.String(100), unique=True, nullable=False, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

class Tournament(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(200))
    created_by = db.Column(db.String(100), db.ForeignKey('user.username'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=False)
    player1 = db.Column(db.String(100), db.ForeignKey('user.username'), nullable=False)
    player2 = db.Column(db.String(100), db.ForeignKey('user.username'), nullable=False)
    scheduled_date = db.Column(db.DateTime, nullable=False)
    result = db.Column(db.String(20))  # 'win', 'loss', 'draw', or 'pending'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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
    return render_template('profile.html', username=session['username'])

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

def add_sample_data():
    """Add sample users and data for testing"""
    with app.app_context():
        # Check if data already exists
        if User.query.filter_by(username='alice').first():
            print("Sample data already exists")
            return
        
        # Create sample users
        users = [
            User(username='alice', email='alice@example.com', password_hash=generate_password_hash('password123')),
            User(username='bob', email='bob@example.com', password_hash=generate_password_hash('password123')),
            User(username='charlie', email='charlie@example.com', password_hash=generate_password_hash('password123')),
        ]
        
        for user in users:
            db.session.add(user)
        
        db.session.commit()
        print("Sample users created: alice, bob, charlie (password: password123)")

# Create database tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)