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
        # Flask 3.x returns 415 Unsupported Media Type for non-JSON bodies.
        assert res.status_code in (400, 415)


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

    def test_update_unauthenticated(self, client, sample_expense):
        res = client.put(f'/api/expenses/{sample_expense.id}', json={
            'description': 'No auth', 'amount': 100,
            'category': 'food', 'date': '2026-03-13'
        })
        assert res.status_code == 401

    def test_update_clears_notes(self, auth_client, sample_expense):
        """Sending empty notes should store an empty string."""
        res = auth_client.put(f'/api/expenses/{sample_expense.id}', json={
            'description': 'Lunch',
            'amount':      350.0,
            'category':    'food',
            'date':        '2026-03-13',
            'notes':       '',
        })
        assert res.status_code == 200
        assert res.get_json()['notes'] == ''

    def test_update_category_change(self, auth_client, sample_expense):
        """Category can be changed to any valid value."""
        res = auth_client.put(f'/api/expenses/{sample_expense.id}', json={
            'description': 'Cab ride',
            'amount':      120.0,
            'category':    'transport',
            'date':        '2026-03-13',
        })
        assert res.status_code == 200
        assert res.get_json()['category'] == 'transport'

    def test_update_nonexistent_expense(self, auth_client):
        """Updating a non-existent expense returns 404."""
        res = auth_client.put('/api/expenses/99999', json={
            'description': 'Ghost', 'amount': 1,
            'category': 'food', 'date': '2026-03-13'
        })
        assert res.status_code == 404

    def test_update_description_max_length(self, auth_client, sample_expense):
        """Description exactly at the 200-char limit should be accepted."""
        long_desc = 'A' * 200
        res = auth_client.put(f'/api/expenses/{sample_expense.id}', json={
            'description': long_desc,
            'amount':      350.0,
            'category':    'food',
            'date':        '2026-03-13',
        })
        assert res.status_code == 200
        assert res.get_json()['description'] == long_desc

    def test_update_description_too_long(self, auth_client, sample_expense):
        """Description over 200 chars should be rejected."""
        res = auth_client.put(f'/api/expenses/{sample_expense.id}', json={
            'description': 'B' * 201,
            'amount':      350.0,
            'category':    'food',
            'date':        '2026-03-13',
        })
        assert res.status_code == 422
        assert 'description' in res.get_json()['errors']


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


class TestNumericPrecision:
    """
    Verify that switching from db.Float to db.Numeric(12,2) eliminates
    IEEE-754 floating-point rounding errors in financial calculations.

    The canonical example: 0.10 + 0.20 must equal 0.30 exactly.
    With db.Float this fails because float(0.1) + float(0.2) = 0.30000000000000004.
    """

    def _create(self, client, amount, category='food'):
        return client.post('/api/expenses', json={
            'description': f'Precision test ₹{amount}',
            'amount':      amount,
            'category':    category,
            'date':        '2026-01-01',
        })

    def test_stored_amount_is_exact(self, auth_client):
        """0.10 stored and retrieved must equal 0.10, not 0.1000000000000000055…"""
        res = self._create(auth_client, 0.10)
        assert res.status_code == 201
        data = res.get_json()
        assert data['amount'] == 0.10
        # Stored as NUMERIC(12,2): round-trip must be exact to 2 decimal places
        assert round(data['amount'], 10) == 0.10

    def test_addition_precision(self, auth_client):
        """0.10 + 0.20 must equal 0.30 exactly in the API total."""
        self._create(auth_client, 0.10)
        self._create(auth_client, 0.20)

        res = auth_client.get('/api/expenses')
        data = res.get_json()
        # This assertion fails with db.Float (gives 0.30000000000000004)
        assert data['total'] == 0.30

    def test_summary_total_precision(self, auth_client):
        """Summary endpoint must also return exact totals."""
        self._create(auth_client, 0.10)
        self._create(auth_client, 0.20)

        res = auth_client.get('/api/expenses/summary')
        data = res.get_json()
        assert data['total'] == 0.30

    def test_three_tenths_sum(self, auth_client):
        """Three 0.1 values must sum to exactly 0.30."""
        for _ in range(3):
            self._create(auth_client, 0.10)

        res = auth_client.get('/api/expenses')
        assert res.get_json()['total'] == 0.30

    def test_large_precise_amount(self, auth_client):
        """Amount at the 12-digit precision boundary is accepted and preserved."""
        res = self._create(auth_client, 9999999999.99)
        assert res.status_code == 201
        assert res.get_json()['amount'] == 9999999999.99

    def test_amount_serialised_as_number_not_string(self, auth_client):
        """JSON response must contain a numeric type, not a quoted string."""
        res = self._create(auth_client, 123.45)
        data = res.get_json()
        # If fields.Decimal(as_string=True) were mistakenly used,
        # this would return "123.45" and isinstance check would fail.
        assert isinstance(data['amount'], (int, float))
        assert data['amount'] == 123.45

    def test_update_preserves_precision(self, auth_client, sample_expense):
        """PUT must store the updated amount with full precision."""
        res = auth_client.put(f'/api/expenses/{sample_expense.id}', json={
            'description': 'Precision update',
            'amount':      0.10,
            'category':    'food',
            'date':        '2026-01-01',
        })
        assert res.status_code == 200
        assert res.get_json()['amount'] == 0.10

    def test_csv_export_two_decimal_places(self, auth_client):
        """CSV export must format amounts to exactly 2 decimal places."""
        self._create(auth_client, 0.10)
        res = auth_client.get('/api/expenses/export')
        assert res.status_code == 200
        # Must contain '0.10', NOT '0.1000000000000000055...'
        assert b'0.10' in res.data

