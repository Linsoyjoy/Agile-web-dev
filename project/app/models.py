from app import db
from datetime import datetime

class User(db.Model):
    username = db.Column(db.String(100), unique=True, nullable=False, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    profile_pic = db.Column(db.String(200), nullable=True)
    weaknesses = db.Column(db.Text, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    lichess_username = db.Column(db.String(100), nullable=True)
    chesscom_username = db.Column(db.String(100), nullable=True)
    lichess_rating = db.Column(db.Integer, nullable=True)
    chesscom_rating = db.Column(db.Integer, nullable=True)
    ratings_last_updated = db.Column(db.DateTime, nullable=True)

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

class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.String(100), db.ForeignKey('user.username'), nullable=False)
    addressee_id = db.Column(db.String(100), db.ForeignKey('user.username'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # 'pending', 'accepted', 'declined'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Ensure no duplicate friendships and prevent self-friendship
    __table_args__ = (db.UniqueConstraint('requester_id', 'addressee_id', name='unique_friendship'),)

class Queries(db.Model):
    id = db.Column(db.Integer, primary_key=True, unique=True)
    email = db.Column(db.String(100), nullable = True)
    issue_type = db.Column(db.String(20), nullable=False, default='other')
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(1000), nullable=True)
    priority = db.Column(db.String(20), nullable=False, default='none')
    status = db.Column(db.String(20), nullable=False, default ='in progress') #in progress, completed, unresolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)