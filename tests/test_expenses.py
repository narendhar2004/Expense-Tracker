from app.models import Expense


class TestGetExpenses:

    def test_get_expenses_authenticated(self, auth_client, sample_expense):
        res = auth_client.get('/api/expenses')
        assert res.status_code == 200
        data = res.get_json()
        assert 'expenses' in data
        assert 'total' in data
        assert 'count' in data
        assert data['count'] == 1
        assert data['expenses'][0]['description'] == 'Test lunch'
        assert data['expenses'][0]['amount'] == 350.0

    def test_get_expenses_unauthenticated(self, client):
        res = client.get('/api/expenses')
        assert res.status_code == 401

    def test_get_expenses_empty(self, auth_client):
        res = auth_client.get('/api/expenses')
        assert res.status_code == 200
        data = res.get_json()
        assert data['count'] == 0
        assert data['total'] == 0
        assert data['expenses'] == []

    def test_filter_by_category(self, auth_client, db, test_user):
        db.session.add(Expense(description='Bus', amount=50,
                               category='transport', date='2026-03-13',
                               user_id=test_user.id))
        db.session.add(Expense(description='Lunch', amount=200,
                               category='food', date='2026-03-13',
                               user_id=test_user.id))
        db.session.commit()
        res = auth_client.get('/api/expenses?category=transport')
        data = res.get_json()
        assert all(e['category'] == 'transport' for e in data['expenses'])
        assert data['count'] == 1

    def test_filter_by_date_range(self, auth_client, db, test_user):
        db.session.add(Expense(description='Jan expense', amount=100,
                               category='food', date='2026-01-15',
                               user_id=test_user.id))
        db.session.add(Expense(description='Mar expense', amount=200,
                               category='food', date='2026-03-10',
                               user_id=test_user.id))
        db.session.commit()
        res = auth_client.get('/api/expenses?start_date=2026-03-01&end_date=2026-03-31')
        data = res.get_json()
        assert all(e['date'] >= '2026-03-01' for e in data['expenses'])

    def test_sort_amount_desc(self, auth_client, db, test_user):
        db.session.add(Expense(description='Cheap', amount=50,
                               category='food', date='2026-03-13',
                               user_id=test_user.id))
        db.session.add(Expense(description='Expensive', amount=5000,
                               category='food', date='2026-03-13',
                               user_id=test_user.id))
        db.session.commit()
        res = auth_client.get('/api/expenses?sort=amount_desc')
        data = res.get_json()
        amounts = [e['amount'] for e in data['expenses']]
        assert amounts == sorted(amounts, reverse=True)

    def test_user_isolation(self, client, db, sample_expense):
        """User cannot see another user's expenses."""
        from app import bcrypt
        from app.models import User
        other = User(email='other@example.com', username='otheruser',
                     password=bcrypt.generate_password_hash('pass1234').decode())
        db.session.add(other)
        db.session.commit()
        client.post('/api/auth/login', json={
            'email': 'other@example.com', 'password': 'pass1234'
        })
        res = client.get('/api/expenses')
        assert res.get_json()['count'] == 0


class TestCreateExpense:

    def test_create_valid_expense(self, auth_client):
        res = auth_client.post('/api/expenses', json={
            'description': 'Coffee',
            'amount':      120.0,
            'category':    'food',
            'date':        '2026-03-13',
        })
        assert res.status_code == 201
        data = res.get_json()
        assert data['description'] == 'Coffee'
        assert data['amount'] == 120.0
        assert 'id' in data
        assert 'created_at' in data

    def test_create_with_notes(self, auth_client):
        res = auth_client.post('/api/expenses', json={
            'description': 'Team lunch',
            'amount':      1500.0,
            'category':    'food',
            'date':        '2026-03-13',
            'notes':       'Work team outing',
        })
        assert res.status_code == 201
        assert res.get_json()['notes'] == 'Work team outing'

    def test_create_unauthenticated(self, client):
        res = client.post('/api/expenses', json={
            'description': 'Test', 'amount': 100,
            'category': 'food', 'date': '2026-03-13'
        })
        assert res.status_code == 401

    def test_create_missing_description(self, auth_client):
        res = auth_client.post('/api/expenses', json={
            'amount': 100, 'category': 'food', 'date': '2026-03-13'
        })
        assert res.status_code == 422
        assert 'description' in res.get_json()['errors']

    def test_create_zero_amount(self, auth_client):
        res = auth_client.post('/api/expenses', json={
            'description': 'Free', 'amount': 0,
            'category': 'food', 'date': '2026-03-13'
        })
        assert res.status_code == 422
        assert 'amount' in res.get_json()['errors']

    def test_create_negative_amount(self, auth_client):
        res = auth_client.post('/api/expenses', json={
            'description': 'Negative', 'amount': -50,
            'category': 'food', 'date': '2026-03-13'
        })
        assert res.status_code == 422
        assert 'amount' in res.get_json()['errors']

    def test_create_invalid_category(self, auth_client):
        res = auth_client.post('/api/expenses', json={
            'description': 'Test', 'amount': 100,
            'category': 'notacategory', 'date': '2026-03-13'
        })
        assert res.status_code == 422
        assert 'category' in res.get_json()['errors']

    def test_create_invalid_date_format(self, auth_client):
        res = auth_client.post('/api/expenses', json={
            'description': 'Test', 'amount': 100,
            'category': 'food', 'date': '13-03-2026'
        })
        assert res.status_code == 422
        assert 'date' in res.get_json()['errors']

    def test_create_no_body(self, auth_client):
        res = auth_client.post('/api/expenses',
                               data='not json', content_type='text/plain')
        assert res.status_code == 400


class TestGetSingleExpense:

    def test_get_own_expense(self, auth_client, sample_expense):
        res = auth_client.get(f'/api/expenses/{sample_expense.id}')
        assert res.status_code == 200
        assert res.get_json()['id'] == sample_expense.id

    def test_get_nonexistent(self, auth_client):
        res = auth_client.get('/api/expenses/99999')
        assert res.status_code == 404

    def test_cannot_get_other_users_expense(self, client, db, sample_expense):
        from app import bcrypt
        from app.models import User
        attacker = User(email='a@example.com', username='attacker',
                        password=bcrypt.generate_password_hash('pass1234').decode())
        db.session.add(attacker)
        db.session.commit()
        client.post('/api/auth/login', json={
            'email': 'a@example.com', 'password': 'pass1234'
        })
        res = client.get(f'/api/expenses/{sample_expense.id}')
        assert res.status_code == 404


class TestUpdateExpense:

    def test_update_own_expense(self, auth_client, sample_expense):
        res = auth_client.put(f'/api/expenses/{sample_expense.id}', json={
            'description': 'Updated lunch',
            'amount':      400.0,
            'category':    'food',
            'date':        '2026-03-13',
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data['description'] == 'Updated lunch'
        assert data['amount'] == 400.0

    def test_update_invalid_data(self, auth_client, sample_expense):
        res = auth_client.put(f'/api/expenses/{sample_expense.id}', json={
            'description': '', 'amount': -10,
            'category': 'food', 'date': '2026-03-13'
        })
        assert res.status_code == 422

    def test_cannot_update_other_users_expense(self, client, db, sample_expense):
        from app import bcrypt
        from app.models import User
        attacker = User(email='b@example.com', username='bttacker',
                        password=bcrypt.generate_password_hash('pass1234').decode())
        db.session.add(attacker)
        db.session.commit()
        client.post('/api/auth/login', json={
            'email': 'b@example.com', 'password': 'pass1234'
        })
        res = client.put(f'/api/expenses/{sample_expense.id}', json={
            'description': 'Hacked', 'amount': 1,
            'category': 'food', 'date': '2026-03-13'
        })
        assert res.status_code == 404


class TestDeleteExpense:

    def test_delete_own_expense(self, auth_client, sample_expense):
        res = auth_client.delete(f'/api/expenses/{sample_expense.id}')
        assert res.status_code == 200
        assert res.get_json()['id'] == sample_expense.id

    def test_delete_nonexistent(self, auth_client):
        res = auth_client.delete('/api/expenses/99999')
        assert res.status_code == 404

    def test_cannot_delete_other_users_expense(self, client, db, sample_expense):
        """Critical authorization test."""
        from app import bcrypt
        from app.models import User
        attacker = User(email='c@example.com', username='cattacker',
                        password=bcrypt.generate_password_hash('pass1234').decode())
        db.session.add(attacker)
        db.session.commit()
        client.post('/api/auth/login', json={
            'email': 'c@example.com', 'password': 'pass1234'
        })
        res = client.delete(f'/api/expenses/{sample_expense.id}')
        assert res.status_code == 404

    def test_delete_unauthenticated(self, client, sample_expense):
        res = client.delete(f'/api/expenses/{sample_expense.id}')
        assert res.status_code == 401


class TestSummary:

    def test_summary_empty(self, auth_client):
        res = auth_client.get('/api/expenses/summary')
        assert res.status_code == 200
        data = res.get_json()
        assert data['total'] == 0
        assert data['count'] == 0
        assert data['by_category'] == {}
        assert data['by_month'] == {}

    def test_summary_with_data(self, auth_client, sample_expense):
        res = auth_client.get('/api/expenses/summary')
        assert res.status_code == 200
        data = res.get_json()
        assert data['total'] == 350.0
        assert data['count'] == 1
        assert data['largest'] == 350.0
        assert 'food' in data['by_category']
        assert '2026-03' in data['by_month']

    def test_summary_unauthenticated(self, client):
        res = client.get('/api/expenses/summary')
        assert res.status_code == 401


class TestCsvExport:

    def test_export_returns_csv(self, auth_client, sample_expense):
        res = auth_client.get('/api/expenses/export')
        assert res.status_code == 200
        assert 'text/csv' in res.content_type
        assert b'Test lunch' in res.data
        assert b'350.00' in res.data

    def test_export_unauthenticated(self, client):
        res = client.get('/api/expenses/export')
        assert res.status_code == 401
