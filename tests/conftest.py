import pytest
from flask import jsonify
from app import create_app, db as _db, login as login_manager
from app.models import User, Expense


# ── App fixture ─────────────────────────────────────────────
@pytest.fixture(scope='session')
def app():
    application = create_app('testing')

    # Make Flask-Login return 401 JSON rather than redirect (302) to the
    # login page, so unauthenticated API tests can assert status_code == 401.
    @login_manager.unauthorized_handler
    def _unauthorized():
        return jsonify({'error': 'Authentication required', 'status': 401}), 401

    yield application


# ── Database fixtures ────────────────────────────────────────
@pytest.fixture(scope='function')
def db(app):
    """
    Create all tables before each test, drop them after.
    Using an in-memory SQLite DB (TestingConfig) makes this instant
    and avoids the SQLAlchemy 2.x incompatibility with session.bind.
    """
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


# ── Client / user / expense fixtures ────────────────────────
@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def test_user(db, app):
    from app import bcrypt
    with app.app_context():
        user = User(
            email    = 'test@example.com',
            username = 'testuser',
            password = bcrypt.generate_password_hash('password123').decode('utf-8'),
        )
        db.session.add(user)
        db.session.commit()
        # Expunge so the object stays usable after the commit expiry
        db.session.refresh(user)
        db.session.expunge(user)
        return user


@pytest.fixture
def auth_client(client, test_user):
    client.post('/api/auth/login', json={
        'email':    'test@example.com',
        'password': 'password123',
    })
    return client


@pytest.fixture
def sample_expense(db, test_user, app):
    with app.app_context():
        expense = Expense(
            description = 'Test lunch',
            amount      = 350.0,
            category    = 'food',
            date        = '2026-03-13',
            notes       = 'Test note',
            user_id     = test_user.id,
        )
        db.session.add(expense)
        db.session.commit()
        db.session.refresh(expense)
        db.session.expunge(expense)
        return expense

