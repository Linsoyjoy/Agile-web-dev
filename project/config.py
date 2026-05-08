import os

basedir = os.path.abspath(os.path.dirname(__file__))
default_db_path = 'sqlite:///' + os.path.join(basedir,"users.db")

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or default_db_path
    SECRET_KEY = os.urandom(24)