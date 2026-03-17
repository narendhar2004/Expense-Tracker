import pytest
from app import create_app, db as _db
from app.models import User, Expense


@pytest.fixture(scope='session')
def app():
    app = create_app('testing')
    yield app


@pytest.fixture(scope='session')
def _database(app):
    with app.app_context():
        _db.create_all()
        yield _db
        _db.drop_all()


@pytest.fixture(scope='function')
def db(app, _database):
    with app.app_context():
        connection  = _database.engine.connect()
        transaction = connection.begin()
        _database.session.bind = connection
        yield _database
        _database.session.remove()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def test_user(db):
    from app import bcrypt
    user = User(
        email    = 'test@example.com',
        username = 'testuser',
        password = bcrypt.generate_password_hash('password123').decode('utf-8'),
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def auth_client(client, test_user):
    client.post('/api/auth/login', json={
        'email':    'test@example.com',
        'password': 'password123',
    })
    return client


@pytest.fixture
def sample_expense(db, test_user):
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
    return expense
