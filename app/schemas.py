from marshmallow import Schema, fields, validate, validates, ValidationError
from datetime import date as date_type


VALID_CATEGORIES = [
    'food', 'transport', 'shopping', 'health',
    'entertainment', 'utilities', 'other'
]


class ExpenseSchema(Schema):
    description = fields.Str(
        required=True,
        validate=validate.Length(
            min=1, max=200,
            error='Description must be between 1 and 200 characters.'
        )
    )
    amount = fields.Float(
        required=True,
        validate=validate.Range(
            min=0.01,
            error='Amount must be greater than zero.'
        )
    )
    category = fields.Str(
        required=True,
        validate=validate.OneOf(
            VALID_CATEGORIES,
            error='Invalid category. Choose from: ' + ', '.join(VALID_CATEGORIES)
        )
    )
    date = fields.Str(required=True)
    notes = fields.Str(load_default='', validate=validate.Length(max=500))

    @validates('date')
    def validate_date(self, value, **kwargs):
        try:
            date_type.fromisoformat(value)
        except ValueError:
            raise ValidationError('Date must be in YYYY-MM-DD format.')


class RegisterSchema(Schema):
    email    = fields.Email(required=True, error_messages={'required': 'Email is required.'})
    username = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=64,
                                 error='Username must be 2–64 characters.')
    )
    password = fields.Str(
        required=True,
        validate=validate.Length(min=8,
                                 error='Password must be at least 8 characters.')
    )


class LoginSchema(Schema):
    email    = fields.Str(required=True)
    password = fields.Str(required=True)
    remember = fields.Bool(load_default=False)