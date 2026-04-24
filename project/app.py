import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)
class User(db.Model):
    username = db.Column(db.String(100), unique=True, nullable=False, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

class GameRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    opponent = db.Column(db.String(100), nullable=False)
    result = db.Column(db.String(10), nullable=False)
    colour = db.Column(db.String(10), nullable=False)
    opening = db.Column(db.String(100))
    moves = db.Column(db.Integer)
    date_played = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.Text)


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

@app.route('/login')
def login():
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

if __name__ == '__main__':
    app.run(debug=True)