from app import create_app,db
from typing import Optional
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User, Match, Queries

app = create_app()

#populate the data
with app.app_context():
    db.create_all()
    # Check if data already exists
    
    # Create sample users
    users = [
        User(username='alice', email='alice@example.com', password_hash=generate_password_hash('password123', method='pbkdf2:sha256'), is_admin=False),
        User(username='bob', email='bob@example.com', password_hash=generate_password_hash('password123', method='pbkdf2:sha256'), is_admin=False),
        User(username='charlie', email='charlie@example.com', password_hash=generate_password_hash('password123', method='pbkdf2:sha256'), is_admin=False),
        User(username='admin', email='admin@example.com', password_hash=generate_password_hash('adminpassword123', method='pbkdf2:sha256'), is_admin=True)
    ]

    
    for user in users:
        if not User.query.filter_by(username=user.username).first():  
            db.session.add(user)
        else:
            print(f"User {user.username} already exists, skipping.")
    
    matches = [
        Match(tournament_id=None, moves="1. e4 e5 2. Nf3 Nc6 3. d4 exd4 4. Nxd4 Nf6 5. Nc3 Bb4 6. Nxc6 bxc6 7. Bd3 d5 8. exd5 cxd5 9. O-O O-O 10. Bg5 c6 11. Qf3 Be7 12. Rfe1 Re8 13. Rad1 Be6 14. h3 Nd7 15. Bxe7 Qxe7 16. Ne2 Ne5 17. Qg3 Nxd3 18. Qxd3 Rab8 19. b3 Qa3 20. Nd4 c5 21. Nxe6 fxe6 22. c4 d4 23. Re2 e5 24. Rde1 Rb6 25. f4 Rbe6 26. fxe5 a5 27. Qf5 a4 28. Rf1 R6e7 29. e6 h6 30. Qxc5 Qxc5 31. Re4 Rxe6 32. Rxe6 Rxe6 33. bxa4 d3+ 34. Kh2 Qxc4 35. Rd1 Re2 36. a5 Qf4+ 37. Kg1 Qf2+ 38. Kh1 Qxg2#", player='alice', opponent='bob', player_colour='black', result='win', termination='checkmate', date_played=datetime(2024, 1, 10)), # Fools mate
        Match(tournament_id=None, moves="1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6 7. Qb3 Qe7 8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5 11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7 14. Rd1 Qe6 15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8#", player='bob', opponent='charlie', player_colour='white', result='win', termination='checkmate', date_played=datetime(2024, 1, 12)),
        Match(tournament_id=None, moves="1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Bg5 e6 7. f4 Qb6 8. Qd2 Qxb2 9. Rb1 Qa3 10. e5 dxe5 11. fxe5 Nfd7 12. Ne4 h6 13. Bh4 g5 14. Bg3 Be7 15. Bc4 Nc6 16. O-O Ndxe5 17. Nxc6 Nxc6 18. Rb3 Qa5 19. Qf2 f5 20. Nd6+ Bxd6 21. Bxd6 b5 22. Bd3 Qd8", player='charlie', opponent='alice', player_colour='black', result='draw', termination='Draw by agreement', date_played=datetime(2025, 1, 14)),
        Match(tournament_id=None, moves="1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8 10. d4 Nbd7 11. c4 Bb7 12. Nc3 b4 13. Nd5 Nxd5 14. cxd5 a5 15. Ba4 Nb6 16. Bc6 Bxc6 17. dxc6 exd4 18. Nxd4 Bf6 19. Nf5 Re8 20. Qg4 g6 21. Nh6+ Kg7 22. Nxf7 Kxf7 23. Bh6 Re5 24. f4 Rc5 25. e5 dxe5 26. fxe5 Rxe5 27. Rxe5 Bxe5 28. Rf1+ Ke8 29. Qe6+ Qe7 30. Rf8#", player='alice', opponent='bob', player_colour='white', result='win', termination='checkmate', date_played=datetime(2024, 1, 15)),
        Match(tournament_id=None, moves="1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d4 exd4 6. cxd4 Bb4+ 7. Nc3 Nxe4 8. O-O Nxc3 9. bxc3 Bxc3 10. Qb3 Bxa1 11. Bxf7+ Kf8 12. Bh5 Qf6 13. Ba3+ d6 14. Re1 g6 15. Rxa1 gxh5 16. Re1 Bg4 17. Qxb7 Bxf3 18. Qxa8+ Kg7 19. Qb7 Qg6 20. Qxc7+ Kh6 21. Bc1#", player='bob', opponent='charlie', player_colour='black', result='loss', termination='resignation', date_played=datetime(2024, 2, 20)),
        Match(tournament_id=None, moves="1. d4 d6 2. Qd2 e5 3. a4 e4 4. Qf4 f5 5. h3 Be7 6. Qh2 Be6 7. Ra3 c5 8. Rg3 Qa5+ 9. Nd2 Bh4 10. f3 Bb3 11. d5 e3 12. c4 f4 1/2-1/2", player='charlie', opponent='alice', player_colour='white', result='draw', termination='stalemate', date_played=datetime(2024, 3, 10))
    ]
    for match in matches:
        if not Match.query.filter_by(moves=match.moves).first():
            db.session.add(match)
        else:
            pass
    
    queries = [
        Queries(email='alice@example.com', title='Issue with login', description='I am unable to log in to my account.', issue_type='bug'),
        Queries(email='bobsfriend@example.com', title='Issue with registration', description='My friend is unable to register for a new account.', issue_type='bug'),
        Queries(email='charlie@example.com', title='Viewing other users profile', description='How do I see other users profile?', issue_type='question'),
        Queries(email='', title='Feature request', description='I would like to see a dark mode option.', issue_type='feature')
    ]
    for query in queries:
        if not Queries.query.filter_by(email=query.email, title=query.title).first():
            db.session.add(query)
        else:
            print(f"Query for {query.email} with title '{query.title}' already exists, skipping.")
    db.session.commit()
    
