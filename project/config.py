import os

basedir = os.path.abspath(os.path.dirname(__file__))
default_db_path = 'sqlite:///' + os.path.join(basedir,"database","users.db")

class Config: #Shared between Deployment & Development configs
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY') or 'chessmate-dev-secret-key-please-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or default_db_path

class DeploymentConfig(Config): # Used in real deployment
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or default_db_path

class DevelopmentConfig(Config): # Used during testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    TESTING = True