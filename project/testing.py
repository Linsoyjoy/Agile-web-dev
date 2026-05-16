from app import create_app,db
from typing import Optional
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User

app = create_app()

#populate the data
"""Add sample users and data for testing"""
with app.app_context():
    db.create_all()
    # Check if data already exists
    
    # Create sample users
    users = [
        User(username='alice', email='alice@example.com', password_hash=generate_password_hash('password123'), is_admin=False),
        User(username='bob', email='bob@example.com', password_hash=generate_password_hash('password123'), is_admin=False),
        User(username='charlie', email='charlie@example.com', password_hash=generate_password_hash('password123'), is_admin=False),
        User(username='admin', email='admin@example.com', password_hash=generate_password_hash('adminpassword123'), is_admin=True)
    ]
    
    for user in users:
        if not User.query.filter_by(username=user.username).first():  
            db.session.add(user)
        else:
            print(f"User {user.username} already exists, skipping.")
    
    db.session.commit()
    print("Sample users created: alice, bob, charlie (password: password123) and admin (password: adminpassword123)")