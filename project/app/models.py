from app import app, db
from datetime import datetime

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
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournament.id'), nullable=True)
    moves = db.Column(db.String(8000), nullable=False)  # Store moves in PGN format
    player = db.Column(db.String(100), db.ForeignKey('user.username'), nullable=False)
    opponent = db.Column(db.String(100), nullable=False)
    player_colour = db.Column(db.String(5), nullable=False)  # 'white' or 'black'
    result = db.Column(db.String(20))  # 'win', 'loss', 'draw', or 'pending'
    termination = db.Column(db.String(50))  # reason game ended (e.g. 'checkmate', 'resignation', 'timeout', etc.)
    date_played = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Create database tables
with app.app_context():
    db.create_all()