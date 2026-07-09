"""
Builds the POS-style "New Manual Invoice" screen: a single self-contained
HTML page (inline CSS + vanilla JS, no build step) with type-to-search
product lookup, a live cart, a percentage discount box, and a Save button
that POSTs straight to ManualInvoice/ManualInvoiceItem via orders/admin.py's
pos_save_view.

Placeholders are swapped with .replace() rather than .format()/f-string,
since the JS below is full of literal { } that would otherwise collide
with Python string formatting.
"""

POS_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>New Manual Invoice - PokeBulk SA</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: Arial, sans-serif; background: #12121A; color: #eee; height: 100vh; overflow: hidden; }
  .pos-wrap { display: flex; height: 100vh; }
  .pos-left { flex: 1.4; display: flex; flex-direction: column; padding: 16px; overflow: hidden; }
  .pos-right { flex: 1; min-width: 340px; max-width: 420px; background: #1a1a24; padding: 16px; display: flex; flex-direction: column; border-left: 2px solid #ff6b35; overflow: hidden; }
  .pos-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .pos-header h1 { font-size: 18px; color: #ff6b35; }
  .pos-header a { color: #999; text-decoration: none; font-size: 13px; }
  .pos-header a:hover { color: #ff6b35; }
  #search-input { width: 100%; padding: 14px; font-size: 16px; border-radius: 8px; border: 2px solid #333; background: #1a1a24; color: #fff; margin-bottom: 12px; }
  #search-input:focus { outline: none; border-color: #ff6b35; }
  #search-results { flex: 1; overflow-y: auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; align-content: start; }
  .result-card { background: #1a1a24; border: 1px solid #333; border-radius: 8px; padding: 10px; }
  .result-name { font-weight: bold; font-size: 13px; margin-bottom: 4px; }
  .result-meta { font-size: 11px; color: #999; margin-bottom: 8px; }
  .result-price-row { display: flex; align-items: center; gap: 6px; }
  .result-price-label { color: #888; font-size: 12px; }
  .result-price-input { width: 70px; padding: 6px; border-radius: 5px; border: 1px solid #444; background: #12121A; color: #ff6b35; font-weight: bold; font-size: 13px; }
  .result-price-input:focus { outline: none; border-color: #ff6b35; }
  .result-add-btn { flex: 1; background: #ff6b35; color: #fff; border: none; border-radius: 5px; padding: 7px 10px; font-size: 12px; font-weight: bold; cursor: pointer; }
  .result-add-btn:hover { background: #e85a28; }
  .no-results, .searching, .search-error { color: #888; padding: 20px; text-align: center; grid-column: 1 / -1; font-size: 13px; }
  .custom-item-box { margin-top: 10px; border-top: 1px solid #2a2a35; padding-top: 10px; }
  .custom-item-box-label { font-size: 11px; color: #888; text-transform: uppercase; margin-bottom: 6px; }
  .custom-item-row { display: flex; gap: 6px; }
  .custom-item-row input { padding: 8px; border-radius: 6px; border: 1px solid #333; background: #1a1a24; color: #fff; font-size: 13px; }
  #custom-desc { flex: 2; }
  #custom-price { flex: 1; }
  #custom-qty { flex: 0.6; }
  #add-custom-btn { background: #333; color: #fff; border: none; border-radius: 6px; padding: 8px 14px; cursor: pointer; font-size: 13px; }
  #add-custom-btn:hover { background: #444; }
  .cart-header { font-size: 14px; font-weight: bold; margin-bottom: 8px; display: flex; justify-content: space-between; color: #ccc; }
  #cart-items { flex: 1; overflow-y: auto; margin-bottom: 10px; min-height: 60px; }
  .cart-empty { color: #888; padding: 20px 4px; text-align: center; font-size: 12px; }
  .cart-line { display: grid; grid-template-columns: 1fr 46px 62px 60px 22px; gap: 6px; align-items: center; padding: 8px 0; border-bottom: 1px solid #2a2a35; }
  .cart-line-name { font-size: 12px; font-weight: bold; }
  .cart-line-meta { font-size: 10px; color: #888; }
  .cart-qty, .cart-price { width: 100%; padding: 5px; border-radius: 4px; border: 1px solid #333; background: #12121A; color: #fff; font-size: 11px; }
  .cart-price { color: #ff6b35; font-weight: bold; border-color: #444; }
  .cart-line-total { font-size: 12px; font-weight: bold; color: #ff6b35; text-align: right; }
  .cart-remove { background: none; border: none; color: #ff5555; font-size: 18px; cursor: pointer; line-height: 1; }
  .customer-fields { border-top: 1px solid #2a2a35; padding-top: 10px; margin-top: 6px; }
  .customer-fields input, .customer-fields textarea { width: 100%; padding: 8px; margin-bottom: 6px; border-radius: 6px; border: 1px solid #333; background: #12121A; color: #fff; font-size: 12px; font-family: inherit; }
  .customer-fields label { font-size: 10px; color: #999; text-transform: uppercase; display: block; margin-bottom: 2px; }
  .totals-row { display: flex; justify-content: space-between; align-items: center; font-size: 13px; padding: 3px 0; color: #ccc; }
  .totals-row.discount { color: #2e7d32; }
  .totals-row.grand { font-size: 18px; font-weight: bold; color: #ff6b35; border-top: 2px solid #ff6b35; margin-top: 6px; padding-top: 8px; }
  .eft-row { display: flex; align-items: center; gap: 8px; margin: 10px 0; font-size: 12px; color: #ccc; }
  #save-btn { background: #ff6b35; color: #fff; border: none; border-radius: 8px; padding: 16px; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 4px; }
  #save-btn:hover { background: #e85a28; }
  #save-btn:disabled { opacity: 0.6; cursor: not-allowed; }
  #shipping-cost, #discount-percent { width: 70px; padding: 4px; border-radius: 4px; border: 1px solid #333; background: #12121A; color: #fff; text-align: right; }
  #discount-percent { color: #2e7d32; }
  #save-error { color: #ff5555; font-size: 12px; margin-top: 6px; min-height: 14px; }
</style>
</head><body>
<div class="pos-wrap">
  <div class="pos-left">
    <div class="pos-header">
      <h1>New Manual Invoice</h1>
      <a href="__CANCEL_URL__">Cancel &amp; back to list</a>
    </div>
    <input type="text" id="search-input" placeholder="Search cards by name or set... (2+ characters)" autofocus>
    <div id="search-results"><div class="no-results">Start typing to search the catalog.</div></div>
    <div class="custom-item-box">
      <div class="custom-item-box-label">Off-site stock (not in catalog)</div>
      <div class="custom-item-row">
        <input type="text" id="custom-desc" placeholder="Item name">
        <input type="number" id="custom-price" placeholder="Price" step="0.01">
        <input type="number" id="custom-qty" placeholder="Qty" value="1" min="1">
        <button id="add-custom-btn">+ Add</button>
      </div>
    </div>
  </div>
  <div class="pos-right">
    <div class="cart-header"><span>Cart</span><span><span id="item-count">0</span> items</span></div>
    <div id="cart-items"><div class="cart-empty">No items yet — search and click Add, or add an off-site item.</div></div>
    <div class="totals-row"><span>Subtotal</span><span id="subtotal-value">R 0.00</span></div>
    <div class="totals-row discount"><span>Discount %</span><input type="number" id="discount-percent" value="0" step="0.5" min="0" max="100"></div>
    <div class="totals-row discount"><span>Discount amount</span><span id="discount-amount-value">-R 0.00</span></div>
    <div class="totals-row"><span>Shipping</span><input type="number" id="shipping-cost" value="0" step="0.01"></div>
    <div class="totals-row grand"><span>TOTAL</span><span id="total-value">R 0.00</span></div>
    <div class="customer-fields">
      <label>Customer name *</label>
      <input type="text" id="customer-name" placeholder="Required">
      <label>Email</label>
      <input type="email" id="customer-email">
      <label>Phone</label>
      <input type="text" id="customer-phone">
      <label>Delivery / collection note</label>
      <textarea id="delivery-note" rows="2"></textarea>
    </div>
    <div class="eft-row">
      <input type="checkbox" id="eft-confirmed">
      <label for="eft-confirmed">EFT payment already confirmed</label>
    </div>
    <button id="save-btn">Save Invoice</button>
    <div id="save-error"></div>
  </div>
</div>
<script>
const SEARCH_URL = "__SEARCH_URL__";
const SAVE_URL = "__SAVE_URL__";
const CSRF_TOKEN = "__CSRF_TOKEN__";

let cart = [];
let searchTimeout = null;
let lastResults = [];

const searchInput = document.getElementById('search-input');
const resultsEl = document.getElementById('search-results');
const cartEl = document.getElementById('cart-items');
const subtotalEl = document.getElementById('subtotal-value');
const discountAmountEl = document.getElementById('discount-amount-value');
const totalEl = document.getElementById('total-value');
const shippingInput = document.getElementById('shipping-cost');
const discountInput = document.getElementById('discount-percent');
const itemCountEl = document.getElementById('item-count');
const saveErrorEl = document.getElementById('save-error');

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

searchInput.addEventListener('input', () => {
  clearTimeout(searchTimeout);
  const term = searchInput.value.trim();
  if (term.length < 2) {
    resultsEl.innerHTML = '<div class="no-results">Start typing to search the catalog.</div>';
    return;
  }
  searchTimeout = setTimeout(() => doSearch(term), 300);
});

async function doSearch(term) {
  resultsEl.innerHTML = '<div class="searching">Searching...</div>';
  try {
    const res = await fetch(SEARCH_URL + '?term=' + encodeURIComponent(term));
    const data = await res.json();
    lastResults = data.results || [];
    renderResults(lastResults);
  } catch (e) {
    resultsEl.innerHTML = '<div class="search-error">Search failed — check your connection.</div>';
  }
}

function renderResults(results) {
  if (!results.length) {
    resultsEl.innerHTML = '<div class="no-results">No matches.</div>';
    return;
  }
  resultsEl.innerHTML = results.map(r => {
    const meta = [
      r.set_name || '',
      r.set_code ? '[' + r.set_code + ']' : '',
      r.card_number ? '#' + r.card_number : '',
      r.variant ? '(' + r.variant + ')' : ''
    ].filter(Boolean).join(' ');
    return '<div class="result-card">' +
      '<div class="result-name">' + escapeHtml(r.name) + '</div>' +
      '<div class="result-meta">' + escapeHtml(meta) + '</div>' +
      '<div class="result-price-row">' +
        '<span class="result-price-label">R</span>' +
        '<input type="number" class="result-price-input" step="0.01" value="' + Number(r.price).toFixed(2) + '" data-id="' + r.id + '">' +
        '<button class="result-add-btn" data-id="' + r.id + '">Add</button>' +
      '</div>' +
    '</div>';
  }).join('');

  resultsEl.querySelectorAll('.result-add-btn').forEach(btn => {
    btn.addEventListener('click', () => addFromSearch(btn.getAttribute('data-id')));
  });
  resultsEl.querySelectorAll('.result-price-input').forEach(input => {
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        e.preventDefault();
        addFromSearch(input.getAttribute('data-id'));
      }
    });
  });
}

function addFromSearch(id) {
  const r = lastResults.find(x => String(x.id) === String(id));
  if (!r) return;
  const priceInput = resultsEl.querySelector('.result-price-input[data-id="' + id + '"]');
  const price = parseFloat(priceInput.value);
  addToCart(Object.assign({}, r, { price: isNaN(price) ? r.price : price }));
}

function addToCart(r) {
  const existing = cart.find(c => c.product_id === r.id);
  if (existing) {
    existing.quantity += 1;
    // Keep whatever price is already in the cart line for repeat adds --
    // only a fresh add sets the price from the (possibly edited) search box.
  } else {
    cart.push({
      product_id: r.id,
      description: r.name,
      set_name: r.set_name,
      card_number: r.card_number,
      variant: r.variant,
      quantity: 1,
      unit_price: r.price
    });
  }
  renderCart();
}

document.getElementById('add-custom-btn').addEventListener('click', () => {
  const desc = document.getElementById('custom-desc').value.trim();
  const price = parseFloat(document.getElementById('custom-price').value);
  const qty = parseInt(document.getElementById('custom-qty').value) || 1;
  if (!desc || isNaN(price)) {
    alert('Enter a name and price for the off-site item.');
    return;
  }
  cart.push({ product_id: null, description: desc, set_name: '', card_number: '', variant: '', quantity: qty, unit_price: price });
  document.getElementById('custom-desc').value = '';
  document.getElementById('custom-price').value = '';
  document.getElementById('custom-qty').value = '1';
  renderCart();
});

function renderCart() {
  if (!cart.length) {
    cartEl.innerHTML = '<div class="cart-empty">No items yet — search and click Add, or add an off-site item.</div>';
  } else {
    cartEl.innerHTML = cart.map((item, i) => {
      const meta = [item.set_name || '', item.card_number ? '#' + item.card_number : '', item.variant ? '(' + item.variant + ')' : ''].filter(Boolean).join(' ');
      return '<div class="cart-line">' +
        '<div><div class="cart-line-name">' + escapeHtml(item.description) + '</div><div class="cart-line-meta">' + escapeHtml(meta) + '</div></div>' +
        '<input type="number" min="1" value="' + item.quantity + '" class="cart-qty" data-index="' + i + '" data-field="quantity">' +
        '<input type="number" step="0.01" value="' + Number(item.unit_price).toFixed(2) + '" class="cart-price" data-index="' + i + '" data-field="unit_price" title="Adjust price for this invoice">' +
        '<div class="cart-line-total">R ' + (item.quantity * item.unit_price).toFixed(2) + '</div>' +
        '<button class="cart-remove" data-index="' + i + '">&times;</button>' +
      '</div>';
    }).join('');
    cartEl.querySelectorAll('.cart-qty, .cart-price').forEach(el => {
      el.addEventListener('input', e => {
        const idx = parseInt(e.target.getAttribute('data-index'));
        const field = e.target.getAttribute('data-field');
        const val = field === 'quantity' ? (parseInt(e.target.value) || 1) : (parseFloat(e.target.value) || 0);
        cart[idx][field] = val;
        updateTotals();
        const totalCell = e.target.closest('.cart-line').querySelector('.cart-line-total');
        totalCell.textContent = 'R ' + (cart[idx].quantity * cart[idx].unit_price).toFixed(2);
      });
    });
    cartEl.querySelectorAll('.cart-remove').forEach(el => {
      el.addEventListener('click', e => {
        cart.splice(parseInt(e.target.getAttribute('data-index')), 1);
        renderCart();
      });
    });
  }
  updateTotals();
}

function updateTotals() {
  const subtotal = cart.reduce((sum, i) => sum + i.quantity * i.unit_price, 0);
  const discountPct = Math.max(0, Math.min(100, parseFloat(discountInput.value) || 0));
  const discountAmount = subtotal * discountPct / 100;
  const shipping = parseFloat(shippingInput.value) || 0;
  const total = subtotal - discountAmount + shipping;
  const itemCount = cart.reduce((sum, i) => sum + i.quantity, 0);
  subtotalEl.textContent = 'R ' + subtotal.toFixed(2);
  discountAmountEl.textContent = '-R ' + discountAmount.toFixed(2);
  totalEl.textContent = 'R ' + total.toFixed(2);
  itemCountEl.textContent = itemCount;
}

shippingInput.addEventListener('input', updateTotals);
discountInput.addEventListener('input', updateTotals);

document.getElementById('save-btn').addEventListener('click', async () => {
  saveErrorEl.textContent = '';
  const customerName = document.getElementById('customer-name').value.trim();
  if (!customerName) { saveErrorEl.textContent = 'Customer name is required.'; return; }
  if (!cart.length) { saveErrorEl.textContent = 'Add at least one item before saving.'; return; }

  const payload = {
    customer_name: customerName,
    customer_email: document.getElementById('customer-email').value.trim(),
    customer_phone: document.getElementById('customer-phone').value.trim(),
    delivery_note: document.getElementById('delivery-note').value.trim(),
    shipping_cost: parseFloat(shippingInput.value) || 0,
    discount_percent: Math.max(0, Math.min(100, parseFloat(discountInput.value) || 0)),
    eft_confirmed: document.getElementById('eft-confirmed').checked,
    items: cart
  };

  const saveBtn = document.getElementById('save-btn');
  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving...';

  try {
    const res = await fetch(SAVE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      window.location = data.redirect_url;
    } else {
      saveErrorEl.textContent = data.error || 'Could not save invoice.';
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save Invoice';
    }
  } catch (e) {
    saveErrorEl.textContent = 'Network error saving invoice.';
    saveBtn.disabled = false;
    saveBtn.textContent = 'Save Invoice';
  }
});

renderCart();
</script>
</body></html>"""


def build_pos_html(csrf_token, search_url, save_url, cancel_url):
    html = POS_HTML
    html = html.replace("__CSRF_TOKEN__", csrf_token)
    html = html.replace("__SEARCH_URL__", search_url)
    html = html.replace("__SAVE_URL__", save_url)
    html = html.replace("__CANCEL_URL__", cancel_url)
    return html
