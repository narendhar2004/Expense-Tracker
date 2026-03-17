from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import Expense

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def dashboard():
    expenses = Expense.query \
        .filter_by(user_id=current_user.id) \
        .order_by(Expense.date.desc()) \
        .all()

    total   = round(sum(e.amount for e in expenses), 2)
    largest = round(max((e.amount for e in expenses), default=0), 2)

    stats = {
        'total':   total,
        'count':   len(expenses),
        'largest': largest,
    }
    return render_template('dashboard.html', expenses=expenses, stats=stats)


@main_bp.route('/reports')
@login_required
def reports():
    return render_template('reports.html')


@main_bp.route('/login')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('login.html')


@main_bp.route('/register')
def register_page():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('register.html')
