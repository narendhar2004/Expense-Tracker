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
   THEME MANAGER
   ============================================================ */

const THEME_KEY = 'expense-tracker-theme';

function getStoredTheme() {
  return localStorage.getItem(THEME_KEY) || 'light';
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(THEME_KEY, theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next    = current === 'light' ? 'dark' : 'light';
  applyTheme(next);
}

function initTheme() {
  // Apply stored theme immediately — before page renders
  // to avoid flash of wrong theme
  applyTheme(getStoredTheme());

  const btn = document.getElementById('theme-toggle');
  if (btn) btn.addEventListener('click', toggleTheme);
}

/* ============================================================
   PRELOADER MANAGER
   ============================================================ */

function initPreloader() {
  const preloader = document.getElementById('preloader');
  if (!preloader) return;

  // Add loading class to body to hide content until ready
  document.body.classList.add('loading');

  // Hide preloader when everything is fully loaded
  window.addEventListener('load', () => {
    // Small delay so users actually see the preloader
    setTimeout(() => {
      preloader.classList.add('hidden');
      document.body.classList.remove('loading');
    }, 800);
  });

  // Safety net — always hide after 3 seconds even if load event is slow
  setTimeout(() => {
    preloader.classList.add('hidden');
    document.body.classList.remove('loading');
  }, 3000);
}

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

async function updateExpenseAPI(id, payload) {
  return await apiFetch(`/api/expenses/${id}`, {
    method: 'PUT',
    body:   JSON.stringify(payload),
  });
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
      <button class="edit-btn" data-action="edit"
              aria-label="Edit ${escapeHtml(expense.description)}">
        Edit
      </button>
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
  const btn = event.target.closest('[data-action]');
  if (!btn) return;
  const row = btn.closest('tr');
  if (!row || !row.dataset.id) return;
  const id = row.dataset.id;

  if (btn.dataset.action === 'delete') {
    deleteExpense(id);
  } else if (btn.dataset.action === 'edit') {
    const expense = expenses.find(e => String(e.id) === String(id));
    if (expense) openEditModal(expense);
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
   EDIT MODAL
   ============================================================ */

let editingExpenseId = null;

function openEditModal(expense) {
  editingExpenseId = expense.id;

  // Pre-fill all fields with existing data
  document.getElementById('edit-description').value = expense.description;
  document.getElementById('edit-amount').value      = expense.amount;
  document.getElementById('edit-category').value    = expense.category;
  document.getElementById('edit-date').value        = expense.date;       // already YYYY-MM-DD
  document.getElementById('edit-notes').value       = expense.notes || '';

  clearEditErrors();
  document.getElementById('edit-modal').showModal();
  document.getElementById('edit-description').focus();
}

function validateEditForm() {
  clearEditErrors();
  let valid = true;

  const desc   = document.getElementById('edit-description').value.trim();
  const amount = parseFloat(document.getElementById('edit-amount').value);
  const cat    = document.getElementById('edit-category').value;
  const date   = document.getElementById('edit-date').value;

  if (!desc) {
    showEditError('edit-description-error', 'Description is required.');
    valid = false;
  }
  if (isNaN(amount) || amount <= 0) {
    showEditError('edit-amount-error', 'Enter a valid amount greater than zero.');
    valid = false;
  }
  if (!cat) {
    showEditError('edit-category-error', 'Please select a category.');
    valid = false;
  }
  if (!date) {
    showEditError('edit-date-error', 'Please select a date.');
    valid = false;
  }
  return valid;
}

function showEditError(id, message) {
  const el = document.getElementById(id);
  if (el) el.textContent = message;
}

function clearEditErrors() {
  ['edit-description-error', 'edit-amount-error',
   'edit-category-error',    'edit-date-error'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = '';
  });
}

function handleEditApiError(err) {
  if (err.errors) {
    Object.entries(err.errors).forEach(([field, messages]) => {
      const msg = Array.isArray(messages) ? messages[0] : messages;
      showEditError(`edit-${field}-error`, msg);
    });
  } else {
    showToast(err.message || 'Could not save changes.', 'error');
  }
}

async function handleEditSubmit(event) {
  event.preventDefault();
  if (!validateEditForm()) return;

  const payload = {
    description: document.getElementById('edit-description').value.trim(),
    amount:      parseFloat(document.getElementById('edit-amount').value),
    category:    document.getElementById('edit-category').value,
    date:        document.getElementById('edit-date').value,
    notes:       document.getElementById('edit-notes').value.trim(),
  };

  const btn = document.getElementById('edit-submit-btn');
  btn.disabled    = true;
  btn.textContent = 'Saving...';

  try {
    const updated = await updateExpenseAPI(editingExpenseId, payload);

    // Update in-memory state
    const idx = expenses.findIndex(e => String(e.id) === String(editingExpenseId));
    if (idx !== -1) expenses[idx] = updated;

    // Replace the existing table row in-place
    const oldRow = tbody && tbody.querySelector(`tr[data-id="${editingExpenseId}"]`);
    if (oldRow) oldRow.replaceWith(makeRow(updated));

    updateStats();
    document.getElementById('edit-modal').close();
    showToast('Expense updated');
  } catch (err) {
    handleEditApiError(err);
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Save changes';
  }
}

function initEditModal() {
  const modal      = document.getElementById('edit-modal');
  const editForm   = document.getElementById('edit-expense-form');
  const cancelBtn  = document.getElementById('edit-cancel-btn');
  const closeBtn   = document.getElementById('edit-modal-close');

  if (!modal) return;   // not on dashboard page

  editForm.addEventListener('submit', handleEditSubmit);

  // Cancel / close-X buttons
  const closeModal = () => modal.close();
  cancelBtn.addEventListener('click', closeModal);
  closeBtn.addEventListener('click', closeModal);

  // Click outside dialog content closes it
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.close();
  });

  // Clear errors when modal is closed (ESC or programmatic)
  modal.addEventListener('close', clearEditErrors);
}

/* ============================================================
   INIT
   ============================================================ */

async function init() {
  // ── Theme and preloader run on every page ──────────────
  initTheme();
  initPreloader();

  // ── Dashboard-only logic ───────────────────────────────
  if (!form) return;

  if (dateInput) dateInput.valueAsDate = new Date();

  form.addEventListener('submit', handleSubmit);

  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      form.reset();
      if (dateInput) dateInput.valueAsDate = new Date();
      clearErrors();
    });
  }

  if (tbody) tbody.addEventListener('click', handleTableClick);

  if (searchInput)    searchInput.addEventListener('input',  debouncedFilter);
  if (filterCategory) filterCategory.addEventListener('change', applyFilters);

  // ── Edit modal ─────────────────────────────────────────
  initEditModal();

  try {
    const data = await fetchExpenses();
    expenses = data.expenses;
    updateStats();
    renderAllRows(expenses);
  } catch (err) {
    showToast('Could not sync latest data.', 'error');
  }
}

document.addEventListener('DOMContentLoaded', init);