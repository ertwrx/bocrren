# app/__init__.py

from flask import Flask
from flask_cors import CORS

def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, static_folder='static')
    CORS(app)

    # All of our configuration is in a separate file
    app.config.from_pyfile('../config.py')

    with app.app_context():
        # Import and register the routes (our API endpoints)
        from . import routes
        app.register_blueprint(routes.main_bp)

    return app
