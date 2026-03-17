'use strict';

/* ============================================================
   CONSTANTS
   ============================================================ */
const API = '';   // empty = same origin (Flask serves both frontend + API)

const CATEGORY_LABELS = {
  food:          'Food & Dining',
  transport:     'Transport',
  shopping:      'Shopping',
  health:        'Health',
  entertainment: 'Entertainment',
  utilities:     'Utilities',
  other:         'Other',
};

/* ============================================================
   STATE
   ============================================================ */
let expenses = [];

/* ============================================================
   DOM REFERENCES  (only grabbed when dashboard is present)
   ============================================================ */
const form           = document.getElementById('expense-form');
const descInput      = document.getElementById('expense-description');
const amountInput    = document.getElementById('expense-amount');
const categorySelect = document.getElementById('expense-category');
const dateInput      = document.getElementById('expense-date');
const notesInput     = document.getElementById('expense-notes');
const submitBtn      = document.getElementById('submit-btn');
const resetBtn       = document.getElementById('reset-btn');
const tbody          = document.getElementById('expense-tbody');
const tableTotal     = document.getElementById('table-total');
const statTotal      = document.getElementById('total-spent');
const statCount      = document.getElementById('total-count');
const statLargest    = document.getElementById('largest-expense');
const searchInput    = document.getElementById('search-input');
const filterCategory = document.getElementById('filter-category');

/* ============================================================
   UTILITIES
   ============================================================ */

function formatCurrency(amount) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
  }).format(amount);
}

function formatDate(dateStr) {
  // Append time to avoid timezone shift
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-IN', {
    day:   'numeric',
    month: 'short',
    year:  'numeric',
  });
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

function debounce(fn, delay) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

/* ============================================================
   API LAYER
   ============================================================ */

async function apiFetch(path, options = {}) {
  const defaults = {
    headers:     { 'Content-Type': 'application/json' },
    credentials: 'include',
  };

  const response = await fetch(API + path, { ...defaults, ...options });

  if (response.status === 401) {
    window.location.href = '/login';
    return;
  }

  const data = await response.json();

  if (!response.ok) {
    const err = new Error(data.error || 'Request failed');
    err.status = response.status;
    err.errors = data.errors || null;
    throw err;
  }

  return data;
}

async function fetchExpenses() {
  return await apiFetch('/api/expenses');
}

async function createExpense(payload) {
  return await apiFetch('/api/expenses', {
    method: 'POST',
    body:   JSON.stringify(payload),
  });
}

async function deleteExpenseAPI(id) {
  return await apiFetch(`/api/expenses/${id}`, { method: 'DELETE' });
}

/* ============================================================
   VALIDATION
   ============================================================ */

function validateForm() {
  clearErrors();
  let valid = true;

  if (!descInput.value.trim()) {
    showError('description-error', 'Description is required.');
    valid = false;
  }

  const amount = parseFloat(amountInput.value);
  if (isNaN(amount) || amount <= 0) {
    showError('amount-error', 'Enter a valid amount greater than zero.');
    valid = false;
  }

  if (!categorySelect.value) {
    showError('category-error', 'Please select a category.');
    valid = false;
  }

  if (!dateInput.value) {
    showError('date-error', 'Please select a date.');
    valid = false;
  }

  return valid;
}

function showError(id, message) {
  const el = document.getElementById(id);
  if (el) el.textContent = message;
}

function clearErrors() {
  ['description-error', 'amount-error', 'category-error', 'date-error']
    .forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = '';
    });
}

function handleApiError(err) {
  if (err.errors) {
    Object.entries(err.errors).forEach(([field, messages]) => {
      const msg = Array.isArray(messages) ? messages[0] : messages;
      showError(`${field}-error`, msg);
    });
  } else {
    showToast(err.message || 'Something went wrong.', 'error');
  }
}

/* ============================================================
   FORM SUBMIT
   ============================================================ */

async function handleSubmit(event) {
  event.preventDefault();
  if (!validateForm()) return;

  const payload = {
    description: descInput.value.trim(),
    amount:      parseFloat(amountInput.value),
    category:    categorySelect.value,
    date:        dateInput.value,
    notes:       notesInput ? notesInput.value.trim() : '',
  };

  setLoading(true);

  try {
    const created = await createExpense(payload);
    expenses.unshift(created);
    prependRow(created);
    updateStats();
    resetForm();
    showToast('Expense added');
  } catch (err) {
    handleApiError(err);
  } finally {
    setLoading(false);
  }
}

function setLoading(loading) {
  if (!submitBtn) return;
  submitBtn.disabled    = loading;
  submitBtn.textContent = loading ? 'Adding...' : 'Add expense';
}

function resetForm() {
  if (form) form.reset();
  if (dateInput) dateInput.valueAsDate = new Date();
  if (descInput) descInput.focus();
}

/* ============================================================
   RENDERING
   ============================================================ */

function makeRow(expense, isNew = false) {
  const tr = document.createElement('tr');
  tr.dataset.id = expense.id;
  if (isNew) tr.classList.add('expense-row-new');

  tr.innerHTML = `
    <td>${escapeHtml(formatDate(expense.date))}</td>
    <td>
      <div class="expense-desc">${escapeHtml(expense.description)}</div>
      ${expense.notes
          ? `<div class="expense-notes">${escapeHtml(expense.notes)}</div>`
          : ''}
    </td>
    <td>
      <span class="category-badge ${escapeHtml(expense.category)}">
        ${escapeHtml(CATEGORY_LABELS[expense.category] || expense.category)}
      </span>
    </td>
    <td class="amount-col">${escapeHtml(formatCurrency(expense.amount))}</td>
    <td>
      <button class="delete-btn" data-action="delete"
              aria-label="Delete ${escapeHtml(expense.description)}">
        Remove
      </button>
    </td>
  `;
  return tr;
}

function prependRow(expense) {
  if (!tbody) return;
  removeEmptyRow();
  tbody.insertBefore(makeRow(expense, true), tbody.firstChild);
}

function renderAllRows(list) {
  if (!tbody) return;
  tbody.innerHTML = '';

  if (list.length === 0) {
    showEmptyRow();
    return;
  }

  const fragment = document.createDocumentFragment();
  list.forEach(e => fragment.appendChild(makeRow(e)));
  tbody.appendChild(fragment);
}

function showEmptyRow() {
  if (!tbody) return;
  tbody.innerHTML = `
    <tr class="empty-row" id="empty-row">
      <td colspan="5">No expenses yet. Add your first one above.</td>
    </tr>`;
}

function removeEmptyRow() {
  const row = tbody && tbody.querySelector('.empty-row');
  if (row) row.remove();
}

/* ============================================================
   STATS
   ============================================================ */

function updateStats() {
  const total   = expenses.reduce((s, e) => s + e.amount, 0);
  const largest = expenses.length
    ? Math.max(...expenses.map(e => e.amount))
    : 0;

  if (statTotal)   statTotal.textContent   = formatCurrency(total);
  if (statCount)   statCount.textContent   = expenses.length;
  if (statLargest) statLargest.textContent = formatCurrency(largest);
  if (tableTotal)  tableTotal.textContent  = formatCurrency(total);
}

/* ============================================================
   DELETE
   ============================================================ */

async function deleteExpense(id) {
  try {
    await deleteExpenseAPI(id);

    expenses = expenses.filter(e => String(e.id) !== String(id));

    const row = tbody && tbody.querySelector(`tr[data-id="${id}"]`);
    if (row) row.remove();

    if (expenses.length === 0) showEmptyRow();
    updateStats();
    showToast('Expense removed');
  } catch (err) {
    showToast('Failed to delete expense.', 'error');
  }
}

/* ============================================================
   EVENT DELEGATION (table)
   ============================================================ */

function handleTableClick(event) {
  const btn = event.target.closest('[data-action="delete"]');
  if (btn) {
    const row = btn.closest('tr');
    if (row && row.dataset.id) {
      deleteExpense(row.dataset.id);
    }
  }
}

/* ============================================================
   SEARCH & FILTER
   ============================================================ */

function applyFilters() {
  const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
  const cat   = filterCategory ? filterCategory.value : '';

  let filtered = expenses;
  if (query) {
    filtered = filtered.filter(e =>
      e.description.toLowerCase().includes(query) ||
      (CATEGORY_LABELS[e.category] || e.category).toLowerCase().includes(query)
    );
  }
  if (cat) {
    filtered = filtered.filter(e => e.category === cat);
  }
  renderAllRows(filtered);
}

const debouncedFilter = debounce(applyFilters, 280);

/* ============================================================
   TOAST NOTIFICATIONS
   ============================================================ */

function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toast.setAttribute('role', 'status');
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('removing');
    setTimeout(() => toast.remove(), 220);
  }, 2600);
}

/* ============================================================
   AUTH HELPERS
   ============================================================ */

async function logoutUser() {
  try {
    await apiFetch('/api/auth/logout', { method: 'POST' });
  } finally {
    window.location.href = '/login';
  }
}

/* ============================================================
   INIT
   ============================================================ */

async function init() {
  // Only run dashboard logic when the form exists
  if (!form) return;

  // Set today's date default
  if (dateInput) dateInput.valueAsDate = new Date();

  // Wire up form
  form.addEventListener('submit', handleSubmit);

  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      form.reset();
      if (dateInput) dateInput.valueAsDate = new Date();
      clearErrors();
    });
  }

  // Wire up table delegation
  if (tbody) tbody.addEventListener('click', handleTableClick);

  // Wire up search + filter
  if (searchInput)    searchInput.addEventListener('input',  debouncedFilter);
  if (filterCategory) filterCategory.addEventListener('change', applyFilters);

  // Load initial data from API
  // The page already has SSR-rendered rows, but we sync JS state
  try {
    const data = await fetchExpenses();
    expenses = data.expenses;
    updateStats();
    // Re-render to ensure JS state matches DOM
    renderAllRows(expenses);
  } catch (err) {
    // SSR rows still visible — app is usable, just show a soft warning
    showToast('Could not sync latest data.', 'error');
  }
}

document.addEventListener('DOMContentLoaded', init);
