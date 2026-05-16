import os
from dotenv import load_dotenv
import logging

load_dotenv()
basedir = os.path.abspath(os.path.dirname(__file__))
default_db_path = 'sqlite:///' + os.path.join(basedir,"database","users.db")

class Config: #Shared between Deployment & Development configs
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Secret key must be set in .env — never hardcoded to prevent security vulnerabilities
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY is not set. Add it to your .env file.")
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or default_db_path

class DeploymentConfig(Config): # Used in real deployment
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or default_db_path

class DevelopmentConfig(Config): # Used during testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    TESTING = True