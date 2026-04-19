import os
import csv
import io
from flask import Blueprint, request, jsonify, Response, current_app
from flask_login import login_required, current_user
from marshmallow import ValidationError
from werkzeug.utils import secure_filename
from app import db
from app.models import Expense
from app.schemas import ExpenseSchema

expenses_bp    = Blueprint('expenses', __name__)
expense_schema = ExpenseSchema()

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'pdf'}


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ── GET /api/expenses ─────────────────────────────────────

@expenses_bp.route('/expenses', methods=['GET'])
@login_required
def get_expenses():
    query = Expense.query.filter_by(user_id=current_user.id)

    category   = request.args.get('category')
    start_date = request.args.get('start_date')
    end_date   = request.args.get('end_date')
    sort       = request.args.get('sort', 'date_desc')

    if category:
        query = query.filter_by(category=category)
    if start_date:
        query = query.filter(Expense.date >= start_date)
    if end_date:
        query = query.filter(Expense.date <= end_date)

    sort_map = {
        'date_desc':   Expense.date.desc(),
        'date_asc':    Expense.date.asc(),
        'amount_desc': Expense.amount.desc(),
        'amount_asc':  Expense.amount.asc(),
    }
    query = query.order_by(sort_map.get(sort, Expense.date.desc()))

    expenses = query.all()
    return jsonify({
        'expenses': [e.to_dict() for e in expenses],
        'total':    round(sum(e.amount for e in expenses), 2),
        'count':    len(expenses),
    }), 200


# ── POST /api/expenses ────────────────────────────────────

@expenses_bp.route('/expenses', methods=['POST'])
@login_required
def create_expense():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'error': 'Request body must be JSON'}), 400

    try:
        validated = expense_schema.load(data)
    except ValidationError as err:
        return jsonify({'errors': err.messages}), 422

    expense = Expense(user_id=current_user.id, **validated)
    db.session.add(expense)
    db.session.commit()
    return jsonify(expense.to_dict()), 201


# ── GET /api/expenses/summary ─────────────────────────────
# NOTE: this route must come BEFORE /expenses/<int:id>

@expenses_bp.route('/expenses/summary', methods=['GET'])
@login_required
def get_summary():
    expenses = Expense.query.filter_by(user_id=current_user.id).all()

    if not expenses:
        return jsonify({'total': 0, 'count': 0, 'largest': 0,
                        'by_category': {}, 'by_month': {}}), 200

    total = sum(e.amount for e in expenses)

    by_category = {}
    for e in expenses:
        by_category[e.category] = round(
            by_category.get(e.category, 0) + e.amount, 2
        )

    by_month = {}
    for e in expenses:
        month = e.date[:7]
        by_month[month] = round(by_month.get(month, 0) + e.amount, 2)

    return jsonify({
        'total':       round(total, 2),
        'count':       len(expenses),
        'largest':     round(max(e.amount for e in expenses), 2),
        'by_category': by_category,
        'by_month':    dict(sorted(by_month.items())),
    }), 200


# ── GET /api/expenses/export ──────────────────────────────

@expenses_bp.route('/expenses/export', methods=['GET'])
@login_required
def export_csv():
    expenses = Expense.query \
        .filter_by(user_id=current_user.id) \
        .order_by(Expense.date.desc()) \
        .all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Description', 'Category', 'Amount (INR)', 'Notes'])
    for e in expenses:
        writer.writerow([e.date, e.description, e.category,
                         f'{e.amount:.2f}', e.notes or ''])
    writer.writerow(['', '', 'TOTAL',
                     f'{sum(e.amount for e in expenses):.2f}', ''])
    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition':
                f'attachment; filename=expenses_{current_user.username}.csv'
        }
    )


# ── GET /api/expenses/<id> ────────────────────────────────

@expenses_bp.route('/expenses/<int:expense_id>', methods=['GET'])
@login_required
def get_expense(expense_id):
    expense = Expense.query.filter_by(
        id=expense_id, user_id=current_user.id
    ).first_or_404()
    return jsonify(expense.to_dict()), 200


# ── PUT /api/expenses/<id> ────────────────────────────────

@expenses_bp.route('/expenses/<int:expense_id>', methods=['PUT'])
@login_required
def update_expense(expense_id):
    expense = Expense.query.filter_by(
        id=expense_id, user_id=current_user.id
    ).first_or_404()

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'error': 'Request body must be JSON'}), 400

    try:
        validated = expense_schema.load(data)
    except ValidationError as err:
        return jsonify({'errors': err.messages}), 422

    for key, value in validated.items():
        setattr(expense, key, value)

    db.session.commit()
    return jsonify(expense.to_dict()), 200


# ── DELETE /api/expenses/<id> ─────────────────────────────

@expenses_bp.route('/expenses/<int:expense_id>', methods=['DELETE'])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.filter_by(
        id=expense_id, user_id=current_user.id
    ).first_or_404()
    db.session.delete(expense)
    db.session.commit()
    return jsonify({'message': 'Expense deleted', 'id': expense_id}), 200


# ── POST /api/expenses/<id>/receipt ──────────────────────

@expenses_bp.route('/expenses/<int:expense_id>/receipt', methods=['POST'])
@login_required
def upload_receipt(expense_id):
    expense = Expense.query.filter_by(
        id=expense_id, user_id=current_user.id
    ).first_or_404()

    if 'receipt' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['receipt']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed. Use jpg, png, webp, or pdf.'}), 422

    filename  = secure_filename(file.filename)
    unique    = f"{current_user.id}_{expense_id}_{filename}"
    upload_dir = os.path.join(current_app.instance_path, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, unique))

    expense.receipt_filename = unique
    db.session.commit()
    return jsonify({'message': 'Receipt uploaded', 'filename': unique}), 200
