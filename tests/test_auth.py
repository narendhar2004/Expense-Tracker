class TestRegister:

    def test_register_success(self, client, db):
        res = client.post('/api/auth/register', json={
            'email': 'new@example.com', 'username': 'newuser', 'password': 'strongpass1'
        })
        assert res.status_code == 201
        data = res.get_json()
        assert data['user']['email'] == 'new@example.com'
        assert 'password' not in data['user']

    def test_register_duplicate_email(self, client, db, test_user):
        res = client.post('/api/auth/register', json={
            'email': 'test@example.com', 'username': 'other', 'password': 'password123'
        })
        assert res.status_code == 422
        assert 'email' in res.get_json()['errors']

    def test_register_duplicate_username(self, client, db, test_user):
        res = client.post('/api/auth/register', json={
            'email': 'other@example.com', 'username': 'testuser', 'password': 'password123'
        })
        assert res.status_code == 422
        assert 'username' in res.get_json()['errors']

    def test_register_weak_password(self, client, db):
        res = client.post('/api/auth/register', json={
            'email': 'weak@example.com', 'username': 'weakuser', 'password': 'short'
        })
        assert res.status_code == 422
        assert 'password' in res.get_json()['errors']

    def test_register_invalid_email(self, client, db):
        res = client.post('/api/auth/register', json={
            'email': 'not-an-email', 'username': 'user', 'password': 'password123'
        })
        assert res.status_code == 422

    def test_register_missing_fields(self, client, db):
        res = client.post('/api/auth/register', json={})
        assert res.status_code == 422

    def test_register_no_body(self, client, db):
        res = client.post('/api/auth/register', data='not json',
                          content_type='text/plain')
        assert res.status_code == 400


class TestLogin:

    def test_login_success(self, client, db, test_user):
        res = client.post('/api/auth/login', json={
            'email': 'test@example.com', 'password': 'password123'
        })
        assert res.status_code == 200
        assert res.get_json()['user']['email'] == 'test@example.com'

    def test_login_wrong_password(self, client, db, test_user):
        res = client.post('/api/auth/login', json={
            'email': 'test@example.com', 'password': 'wrongpassword'
        })
        assert res.status_code == 401
        assert 'Invalid email or password' in res.get_json()['error']

    def test_login_unknown_email(self, client, db):
        res = client.post('/api/auth/login', json={
            'email': 'nobody@example.com', 'password': 'password123'
        })
        assert res.status_code == 401
        # Same error as wrong password — no user enumeration
        assert 'Invalid email or password' in res.get_json()['error']

    def test_logout_success(self, auth_client):
        res = auth_client.post('/api/auth/logout')
        assert res.status_code == 200

    def test_logout_requires_auth(self, client):
        res = client.post('/api/auth/logout')
        assert res.status_code == 401

    def test_me_authenticated(self, auth_client, test_user):
        res = auth_client.get('/api/auth/me')
        assert res.status_code == 200
        assert res.get_json()['user']['id'] == test_user.id

    def test_me_unauthenticated(self, client):
        res = client.get('/api/auth/me')
        assert res.status_code == 401
