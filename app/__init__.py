from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from config import config

db     = SQLAlchemy()
login  = LoginManager()
bcrypt = Bcrypt()


def create_app(config_name='default'):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config[config_name])

    db.init_app(app)
    login.init_app(app)
    bcrypt.init_app(app)
    CORS(app,
         supports_credentials=True,
         origins=[
             'http://localhost:3000',
             'http://127.0.0.1:3000',
             'http://localhost:5500',
             'http://127.0.0.1:5500',
             'http://localhost:5000',
         ])

    # ✅ FIXED — points to the HTML page, not the API endpoint
    login.login_view = 'main.login_page'
    login.login_message_category = 'info'

    from app.routes import expenses_bp
    from app.auth   import auth_bp
    from app.main   import main_bp
    app.register_blueprint(expenses_bp, url_prefix='/api')
    app.register_blueprint(auth_bp,     url_prefix='/api/auth')
    app.register_blueprint(main_bp)

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Resource not found', 'status': 404}), 404

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({'error': 'Authentication required', 'status': 401}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({'error': 'Access forbidden', 'status': 403}), 403

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return jsonify({'error': 'Internal server error', 'status': 500}), 500

    with app.app_context():
        import os
        os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(os.path.join(app.instance_path, 'uploads'), exist_ok=True)
        db.create_all()

    return app