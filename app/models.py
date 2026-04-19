from app import db, login
from flask_login import UserMixin
from datetime import datetime, timezone


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id         = db.Column(db.Integer,     primary_key=True)
    email      = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username   = db.Column(db.String(64),  unique=True, nullable=False)
    password   = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime,    default=lambda: datetime.now(timezone.utc))

    expenses = db.relationship(
        'Expense', backref='owner', lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def to_dict(self):
        return {
            'id':         self.id,
            'email':      self.email,
            'username':   self.username,
            'created_at': self.created_at.isoformat(),
        }


class Expense(db.Model):
    __tablename__ = 'expenses'

    id               = db.Column(db.Integer,     primary_key=True)
    description      = db.Column(db.String(200), nullable=False)
    amount           = db.Column(db.Numeric(precision=12, scale=2, asdecimal=True), nullable=False)
    category         = db.Column(db.String(50),  nullable=False)
    date             = db.Column(db.String(10),  nullable=False)
    notes            = db.Column(db.Text,         default='')
    receipt_filename = db.Column(db.String(200),  nullable=True)
    created_at       = db.Column(db.DateTime,     default=lambda: datetime.now(timezone.utc))
    user_id          = db.Column(db.Integer,      db.ForeignKey('users.id'), nullable=False)

    def to_dict(self):
        return {
            'id':               self.id,
            'description':      self.description,
            'amount':           float(self.amount),
            'category':         self.category,
            'date':             self.date,
            'notes':            self.notes,
            'receipt_filename': self.receipt_filename,
            'created_at':       self.created_at.isoformat(),
            'user_id':          self.user_id,
        }


@login.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
