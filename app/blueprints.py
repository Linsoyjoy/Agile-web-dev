from flask import Blueprint

# Main blueprint — all app routes are registered under this
main = Blueprint('main', __name__)

# Import models and routes so they are registered with the blueprint
from app import models, routes
