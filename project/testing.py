from app import app,db
from typing import Optional
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User

#populate the data
"""Add sample users and data for testing"""
with app.app_context():
    # Check if data already exists
    if User.query.filter_by(username='alice').first():
        print("Sample data already exists")
        pass
    
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