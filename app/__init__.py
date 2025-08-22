# app/__init__.py
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Initialize the database object. We don't connect it to the app yet.
db = SQLAlchemy()

def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    
    # --- Configuration ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_default_secret_key_for_development')
    # Read the database URL from the environment variable we set on Render
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///dev.db').replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Connect the database object to our Flask app
    db.init_app(app)

    with app.app_context():
        # Import the models so that SQLAlchemy knows about them
        from . import models
        # Create the database tables if they don't already exist
        db.create_all()
        print("--- Database tables checked/created successfully. ---")
        
        # Import and register the routes
        from . import routes
        app.register_blueprint(routes.bp)

        return app