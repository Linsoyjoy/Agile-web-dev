from flask import Flask, render_template

app = Flask(__name__)


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

if __name__ == '__main__':
    app.run(debug=True)