import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
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
    return render_template('home.html')

@app.route('/friends')
def friends():
    return render_template('friends.html')

@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route('/viewstats')
def viewstats():
    return render_template('viewstats.html')

@app.route('/calendar')
def calendar():
    try:
        # Get all matches with tournament info
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
        
        return render_template('calendar.html', matches=matches, events=events)
    except Exception as e:
        # Handle case where tables don't exist or no data
        return render_template('calendar.html', matches=[], events=[])

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
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password!', 'error')
    
    return render_template('login.html')

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

# Create database tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)