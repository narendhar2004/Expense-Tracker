from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from marshmallow import ValidationError
from app import db, bcrypt
from app.models import User
from app.schemas import RegisterSchema, LoginSchema

auth_bp = Blueprint('auth', __name__)

register_schema = RegisterSchema()
login_schema    = LoginSchema()


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    try:
        validated = register_schema.load(data)
    except ValidationError as err:
        return jsonify({'errors': err.messages}), 422

    errors = {}
    email    = validated['email'].strip().lower()
    username = validated['username'].strip()
    password = validated['password']

    if User.query.filter_by(email=email).first():
        errors['email'] = 'An account with this email already exists.'
    if User.query.filter_by(username=username).first():
        errors['username'] = 'This username is already taken.'
    if errors:
        return jsonify({'errors': errors}), 422

    hashed = bcrypt.generate_password_hash(password).decode('utf-8')
    user   = User(email=email, username=username, password=hashed)
    db.session.add(user)
    db.session.commit()

    login_user(user, remember=True)
    return jsonify({'message': 'Account created successfully', 'user': user.to_dict()}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    if current_user.is_authenticated:
        return jsonify({'message': 'Already logged in', 'user': current_user.to_dict()}), 200

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    try:
        validated = login_schema.load(data)
    except ValidationError as err:
        return jsonify({'errors': err.messages}), 422

    email    = validated['email'].strip().lower()
    password = validated['password']
    remember = validated.get('remember', False)

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({'error': 'Invalid email or password'}), 401

    login_user(user, remember=remember)
    return jsonify({'message': 'Logged in successfully', 'user': user.to_dict()}), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    return jsonify({'user': current_user.to_dict()}), 200
