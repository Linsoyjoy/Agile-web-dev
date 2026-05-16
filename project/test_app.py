import unittest
from app import create_app, db
from app.models import User, Tournament, Match
from werkzeug.security import generate_password_hash, check_password_hash

class ChessMateUnitTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('config.DevelopmentConfig')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_signup(self):
        # Post to signup route fake user data
        signup_response = self.app.test_client().post('/signup', data={
            'username': 'testuser',
            'email': 'testuser@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        # Confirm correct response
        self.assertEqual(signup_response.status_code, 302)
        # Confirm correct user data in database
        user = User.query.filter_by(username='testuser').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'testuser@example.com')
        self.assertTrue(check_password_hash(user.password_hash, 'password123'))

    def test_signup_existing_username(self):
        # Create existing user
        existing_user = User(username='existinguser', email='unique.email@example.com', password_hash=generate_password_hash('password123', method='pbkdf2:sha256'))
        db.session.add(existing_user)
        db.session.commit()
        # Post to signup route with same username but different email
        signup_response = self.app.test_client().post('/signup', data={
            'username': 'existinguser',
            'email': 'secondunique.email@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        # Confirm correct error message and no user created
        self.assertIn(b'Username already taken, please choose another!', signup_response.data)
        nonexistent_user = User.query.filter_by(email='secondunique.email@example.com').first()
        self.assertIsNone(nonexistent_user)

    def test_signup_existing_email(self):
        # Create existing user
        existing_user = User(username='uniqueusername', email='existingemail@example.com', password_hash=generate_password_hash('password123', method='pbkdf2:sha256'))
        db.session.add(existing_user)
        db.session.commit()
        # Post to signup route with same email but different username
        signup_response = self.app.test_client().post('/signup', data={
            'username': 'seconduniqueusername',
            'email': 'existingemail@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        # Confirm correct error message and no user created
        self.assertIn(b'Email already registered!', signup_response.data)
        nonexistent_user = User.query.filter_by(username='seconduniqueusername').first()
        self.assertIsNone(nonexistent_user)

    def test_signup_password_mismatch(self):
        # Post to signup route with mismatched passwords
        signup_response = self.app.test_client().post('/signup', data={
            'username': 'testuser',
            'email': 'testuser@example.com',
            'password': 'password123',
            'confirm_password': 'differentpassword'
        })
        # Confirm correct error message and no user created
        self.assertIn(b'Passwords do not match!', signup_response.data)
        nonexistent_user = User.query.filter_by(username='testuser').first()
        self.assertIsNone(nonexistent_user)
    
    def test_login(self):
        # Create user to log in
        client =  self.app.test_client()
        user = User(username='testuser', email='testuser@example.com', password_hash=generate_password_hash('password123', method='pbkdf2:sha256'))
        db.session.add(user)
        db.session.commit()
        # Post to login route with correct credentials
        login_response = client.post('/login', data={
            'username': 'testuser',
            'password': 'password123'
        })
        # Confirm actually logged in
        self.assertEqual(login_response.status_code, 302)
        with client.session_transaction() as session:
            self.assertEqual(session['username'], 'testuser')

    def test_login_nonexistent_user(self):
        # Post to login route with non-existent username
        client = self.app.test_client()
        login_response = client.post('/login', data={
            'username': 'nonexistentuser',
            'password': 'password123'
        })
        # Confirm correct error message and not logged in
        self.assertIn(b'Invalid username or password!', login_response.data)
        with client.session_transaction() as session:
            self.assertNotIn('username', session)
    
    def test_login_wrong_password(self):
        # Create user to log in
        client = self.app.test_client()
        user = User(username='testuser', email='testuser@example.com', password_hash=generate_password_hash('password123', method='pbkdf2:sha256'))
        db.session.add(user)
        db.session.commit()
        # Post to login route with wrong password
        login_response = client.post('/login', data={
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        # Confirm correct error message and not logged in
        self.assertIn(b'Invalid username or password!', login_response.data)
        with client.session_transaction() as session:
            self.assertNotIn('username', session)

    def test_login_empty_fields(self):
        # Post to login route with empty username and password
        client = self.app.test_client()
        login_response = client.post('/login', data={
            'username': '',
            'password': ''
        })
        # Confirm correct error message and not logged in
        self.assertIn(b'Please enter both username and password!', login_response.data)
        with client.session_transaction() as session:
            self.assertNotIn('username', session)
    
    def test_logout(self):
        # Create user and log in
        client = self.app.test_client()
        user = User(username='testuser', email='testuser@example.com', password_hash=generate_password_hash('password123', method='pbkdf2:sha256'))
        db.session.add(user)
        db.session.commit()
        # Log in
        client.post('/login', data={
            'username': 'testuser',
            'password': 'password123'
        })
        # Post to logout route
        logout_response = client.get('/logout')
        # Confirm actually logged out
        self.assertEqual(logout_response.status_code, 302)
        with client.session_transaction() as session:
            self.assertNotIn('username', session)

    def test_not_logged_in_access(self):
        # Attempt to access protected route without logging in
        client = self.app.test_client()
        response = client.get('/profile')
        # Confirm redirected to login page
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])
    
    def test_adding_new_record(self):
        # Create new user
        client = self.app.test_client()
        user = User(username='testuser', email='testuser@example.com', password_hash=generate_password_hash('password123', method='pbkdf2:sha256'))
        db.session.add(user)
        db.session.commit()
        
        client.post('/login', data={
            'username': 'testuser',
            'password': 'password123'
        })

        # Access new record page
        client.get('/newrecord', follow_redirects=True)

        # Submit a single Match record
        newrecord_response = client.post('/new_record', data={
            'game_record': '1. e4 e5 2. Nf3 Nc6 3. Bb5 a6',
            'opponent': 'opponentuser',
            'colour': 'White',
            'result': 'Win',
            'termination': 'Checkmate',
            'date_played': '2024-01-01'
        }, follow_redirects=True)
        # Confirm correct response
        self.assertEqual(newrecord_response.status_code, 200)
        # Confirm match data in database
        match = Match.query.filter_by(player='testuser').first()
        self.assertIsNotNone(match)
        self.assertEqual(match.moves, '1. e4 e5 2. Nf3 Nc6 3. Bb5 a6')
        self.assertEqual(match.opponent, 'opponentuser')
        self.assertEqual(match.player_colour, 'White')
        self.assertEqual(match.result, 'Win')
        self.assertEqual(match.termination, 'Checkmate')

if __name__ == '__main__':
    unittest.main()
