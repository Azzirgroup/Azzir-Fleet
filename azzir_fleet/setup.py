# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""App setup — installs the Item Codes child table on Item."""

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


CUSTOM_FIELDS = {
	"Item": [
		# Placed directly after `uoms` so it lands in the Details tab, under the
		# Units of Measure section. (A custom Section Break here would be pushed
		# into the Inventory tab by Frappe's sort_fields, which walks past Tab
		# Breaks when positioning section breaks.)
		{
			"fieldname": "azzir_alias_codes",
			"label": "Item Codes (Primary + Old Codes)",
			"fieldtype": "Table",
			"options": "Item Code Entry",
			"insert_after": "uoms",
			"description": "Tick Primary to make a code the live item code (saving renames the item). "
			"Other rows are old codes that resolve back to this item everywhere.",
		},
		# Purchasing ceiling — opposite of Minimum Order Qty.
		{
			"fieldname": "max_order_qty",
			"label": "Maximum Order Qty",
			"fieldtype": "Float",
			"insert_after": "min_order_qty",
			"description": "You cannot order/request more than this quantity per item row "
			"in buying documents. 0 = no limit.",
		},
		# Selling ceiling.
		{
			"fieldname": "max_sale_qty",
			"label": "Maximum Sales Qty",
			"fieldtype": "Float",
			"insert_after": "sales_uom",
			"description": "You cannot sell more than this quantity per item row in selling "
			"documents. 0 = no limit.",
		},
	],
	# Stock Entry row detail (NOT in grid): total stock + a button for the tree dialog.
	"Stock Entry Detail": [
		{
			"fieldname": "azzir_all_stock",
			"label": "All Warehouses Stock",
			"fieldtype": "Float",
			"insert_after": "actual_qty",
			"read_only": 1,
			"no_copy": 1,
			"description": "Total stock of this item across all warehouses.",
		},
		{
			"fieldname": "azzir_view_stock",
			"label": "View Stock by Warehouse",
			"fieldtype": "Button",
			"insert_after": "azzir_all_stock",
		},
	],
	# Bundle components (Packed Items): a button to pick the component's warehouse
	# from those that actually hold it.
	"Packed Item": [
		{
			"fieldname": "azzir_view_stock",
			"label": "See Stock",
			"fieldtype": "Button",
			"insert_after": "warehouse",
			"in_list_view": 1,
		},
	],
	# Default quotation validity per party — used to auto-set Quotation "Valid Till".
	"Customer": [
		{
			"fieldname": "azzir_quotation_validity_days",
			"label": "Default Quotation Validity (Days)",
			"fieldtype": "Int",
			"insert_after": "default_currency",
			"description": "Quotations for this customer expire this many days after the "
			"quotation date (auto-filled if Valid Till is empty). 0 = ignore.",
		}
	],
	"Supplier": [
		{
			"fieldname": "azzir_quotation_validity_days",
			"label": "Default Quotation Validity (Days)",
			"fieldtype": "Int",
			"insert_after": "default_currency",
			"description": "Quotations for this supplier expire this many days after the "
			"quotation date (auto-filled if Valid Till is empty). 0 = ignore.",
		}
	],
}

# "Apply VAT" toggle (default on) — unchecking removes VAT on that document.
_APPLY_VAT_FIELD = {
	"fieldname": "azzir_apply_vat",
	"label": "Apply VAT",
	"fieldtype": "Check",
	"default": "1",
	"insert_after": "taxes_and_charges",
	"description": "Uncheck to remove VAT from this document.",
}
for _dt in ("Sales Invoice", "Sales Order", "Quotation", "Delivery Note"):
	CUSTOM_FIELDS.setdefault(_dt, []).append(dict(_APPLY_VAT_FIELD))

# Marks a Quotation that was generated FROM a Sales Invoice (reverse re-quote
# flow). When set, the "Create > Sales Invoice" button is hidden so you don't
# loop invoice -> quotation -> invoice.
CUSTOM_FIELDS.setdefault("Quotation", []).append(
	{
		"fieldname": "azzir_source_sales_invoice",
		"label": "Source Sales Invoice",
		"fieldtype": "Link",
		"options": "Sales Invoice",
		"insert_after": "order_type",
		"read_only": 1,
		"no_copy": 1,
		"print_hide": 1,
		"description": "Set automatically when this quotation was created from a Sales Invoice.",
	}
)

# Set when a Sales Invoice generated from this quotation is submitted (cleared on
# cancel). Drives hiding the "Create > Sales Invoice" button once invoiced.
CUSTOM_FIELDS.setdefault("Quotation", []).append(
	{
		"fieldname": "azzir_invoiced",
		"label": "Invoiced",
		"fieldtype": "Check",
		"insert_after": "azzir_source_sales_invoice",
		"read_only": 1,
		"no_copy": 1,
		"print_hide": 1,
		"description": "Set when a Sales Invoice created from this quotation is submitted.",
	}
)

# Doc-level toggle to hide the Part Number column on the proforma printout.
CUSTOM_FIELDS.setdefault("Quotation", []).append(
	{
		"fieldname": "azzir_hide_part_no",
		"label": "Hide Part Numbers on Print",
		"fieldtype": "Check",
		"insert_after": "azzir_invoiced",
		"description": "Tick to hide BOTH the Part Number column AND the alternative/previous part number (in the Description) on this quotation's printout, so the table starts at Description.",
	}
)

# Records which Quotation a Sales Invoice was generated from (reverse flow), so the
# quotation's "Create > Sales Invoice" button hides once it has been invoiced.
CUSTOM_FIELDS.setdefault("Sales Invoice", []).append(
	{
		"fieldname": "azzir_source_quotation",
		"label": "Source Quotation",
		"fieldtype": "Link",
		"options": "Quotation",
		"insert_after": "customer",
		"read_only": 1,
		"no_copy": 1,
		"print_hide": 1,
		"description": "Set automatically when this invoice was created from a Quotation.",
	}
)

# Stores the specific old code the user typed to find this item (captured
# client-side). On every transaction item row so the print shows that exact code.
_OLD_CODE_FIELD = {
	"fieldname": "azzir_old_code",
	"label": "Old Code (entered)",
	"fieldtype": "Data",
	"insert_after": "item_code",
	"read_only": 1,
	"hidden": 1,
	"no_copy": 1,
}
for _dt in (
	"Sales Invoice Item",
	"Sales Order Item",
	"Quotation Item",
	"Delivery Note Item",
	"Purchase Order Item",
	"Purchase Receipt Item",
	"Purchase Invoice Item",
	"Supplier Quotation Item",
):
	CUSTOM_FIELDS.setdefault(_dt, []).append(dict(_OLD_CODE_FIELD))

# Live stock columns (read-only, filled client-side) — Quotation + Sales Invoice grids.
_STOCK_GRID_FIELDS = [
	{
		"fieldname": "azzir_wh_stock",
		"label": "Stock (This WH)",
		"fieldtype": "Float",
		"insert_after": "warehouse",
		"read_only": 1,
		"in_list_view": 1,
		"no_copy": 1,
		"description": "Current stock of this item in the row's warehouse.",
	},
	{
		"fieldname": "azzir_all_stock",
		"label": "Stock (All WH)",
		"fieldtype": "Float",
		"insert_after": "azzir_wh_stock",
		"read_only": 1,
		"in_list_view": 1,
		"no_copy": 1,
		"description": "Total stock across all warehouses. Click to see the per-warehouse breakdown.",
	},
]
_VIEW_STOCK_BUTTON = {
	"fieldname": "azzir_view_stock",
	"label": "See All Stock on Warehouse",
	"fieldtype": "Button",
	"insert_after": "item_name",
}
for _dt in ("Quotation Item", "Sales Invoice Item"):
	for _f in _STOCK_GRID_FIELDS:
		CUSTOM_FIELDS.setdefault(_dt, []).append(dict(_f))
	CUSTOM_FIELDS[_dt].append(dict(_VIEW_STOCK_BUTTON))

OVERRIDE_ROLE = "Azzir Stock Override"


def after_migrate():
	# Each step runs independently — a failure in one must not stop the others
	# (that's why the Customer Statement report, being last, could go missing).
	steps = [
		("custom_fields", lambda: create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)),
		(
			"uom_section",
			lambda: make_property_setter(
				"Item", "unit_of_measure_conversion", "collapsible", 0, "Check",
				validate_fields_for_doctype=False,
			),
		),
		("print_formats", setup_print_formats),
		("lock_print_formats", _lock_print_formats),
		("packed_items_position", _position_packed_items),
		("packed_item_grid", _configure_packed_item_grid),
		(
			"item_code_label",
			lambda: make_property_setter(
				"Item", "item_code", "label", "Part Number", "Data",
				validate_fields_for_doctype=False,
			),
		),
		("override_role", _setup_override_role),
		("session_limit", _enforce_session_limit),
		("multicurrency", _enable_multicurrency),
	]
	for label, fn in steps:
		try:
			fn()
		except Exception:
			frappe.log_error(title=f"azzir_fleet after_migrate failed: {label}")


def _setup_override_role():
	"""Role whose holders bypass the min/max/stock qty limits."""
	if not frappe.db.exists("Role", OVERRIDE_ROLE):
		frappe.get_doc(
			{"doctype": "Role", "role_name": OVERRIDE_ROLE, "desk_access": 1}
		).insert(ignore_permissions=True)


def _enforce_session_limit():
	"""Allow MAX_SESSIONS logins per user (e.g. phone + desktop), not just one.

	deny_multiple_sessions must stay OFF: it calls clear_sessions(force=True),
	which ignores simultaneous_sessions and kills every other session, so users
	were bounced the moment they signed in on a second device and their open tab
	then failed with "Method Not Allowed" on search_link. The cap is enforced on
	login instead — see azzir_fleet.session.enforce_session_limit.
	"""
	from azzir_fleet.session import MAX_SESSIONS

	frappe.db.set_single_value("System Settings", "deny_multiple_sessions", 0)
	make_property_setter(
		"User", "simultaneous_sessions", "default", MAX_SESSIONS, "Data",
		validate_fields_for_doctype=False,
	)
	for user in frappe.get_all(
		"User",
		filters={"enabled": 1, "name": ["not in", ("Administrator", "Guest")]},
		pluck="name",
	):
		if frappe.db.get_value("User", user, "simultaneous_sessions") != MAX_SESSIONS:
			frappe.db.set_value(
				"User", user, "simultaneous_sessions", MAX_SESSIONS, update_modified=False
			)


def _enable_multicurrency():
	"""Multi-currency is native; allow multi-currency invoices on a single party account."""
	try:
		frappe.db.set_single_value(
			"Accounts Settings",
			"allow_multi_currency_invoices_against_single_party_account",
			1,
		)
	except Exception:
		pass


PRINT_FORMATS = [
	# (print format name, doctype, title, party, show_prices)
	("Sales Invoice with Old Code", "Sales Invoice", "SALES INVOICE", "customer", True),
	("Quotation (Azzir)", "Quotation", "PROFORMA INVOICE", "customer", True),
	("Sales Order (Azzir)", "Sales Order", "SALES ORDER", "customer", True),
	# Delivery Note = goods slip: quantities only, no prices/taxes/totals.
	("Delivery Note (Azzir)", "Delivery Note", "DELIVERY NOTE", "customer", False),
	("Purchase Order (Azzir)", "Purchase Order", "PURCHASE ORDER", "supplier", True),
	("Purchase Receipt (Azzir)", "Purchase Receipt", "PURCHASE RECEIPT", "supplier", True),
	("Purchase Invoice (Azzir)", "Purchase Invoice", "PURCHASE INVOICE", "supplier", True),
	("Supplier Quotation (Azzir)", "Supplier Quotation", "SUPPLIER QUOTATION", "supplier", True),
]


def setup_print_formats():
	"""Create/refresh proforma-style print formats for all transaction doctypes
	and set each as its doctype's default."""
	for name, dt, title, party, show_prices in PRINT_FORMATS:
		html = _proforma_html(title, party, show_prices)
		if frappe.db.exists("Print Format", name):
			pf = frappe.get_doc("Print Format", name)
			pf.html = html
			pf.custom_format = 1
			pf.print_format_type = "Jinja"
			pf.doc_type = dt
			pf.flags.ignore_permissions = True
			pf.save(ignore_permissions=True)
		else:
			frappe.get_doc(
				{
					"doctype": "Print Format",
					"name": name,
					"doc_type": dt,
					"module": "Azzir Fleet",
					"print_format_type": "Jinja",
					"custom_format": 1,
					"standard": "No",
					"html": html,
				}
			).insert(ignore_permissions=True)
		make_property_setter(
			dt, None, "default_print_format", name, "Data",
			for_doctype=True, validate_fields_for_doctype=False,
		)

	# Pickup Slip (Sales Invoice) — NOT set as default.
	_upsert_print_format("Pickup Slip", "Sales Invoice", PICKUP_SLIP_HTML)

	# Expense Entry voucher — set as its default print format.
	_upsert_print_format("Expense Entry (Azzir)", "Expense Entry", EXPENSE_ENTRY_HTML)
	make_property_setter(
		"Expense Entry", None, "default_print_format", "Expense Entry (Azzir)", "Data",
		for_doctype=True, validate_fields_for_doctype=False,
	)


def _position_packed_items():
	"""Move the Packing List (bundle components) section to sit right under the
	Items table so it shows without scrolling. Standard fields reorder only via a
	DocType 'field_order' property setter (insert_after works for custom fields
	only). Idempotent."""
	meta = frappe.get_meta("Sales Invoice")
	order = [df.fieldname for df in meta.fields if not getattr(df, "is_custom_field", False)]
	move = ["packing_list", "packed_items", "product_bundle_help"]
	if "items" not in order or not all(f in order for f in move):
		return
	for f in move:
		order.remove(f)
	pos = order.index("items") + 1
	order[pos:pos] = move
	make_property_setter(
		"Sales Invoice", None, "field_order", json.dumps(order), "Text",
		for_doctype=True, validate_fields_for_doctype=False,
	)
	# Drop the earlier (ineffective) insert_after property setter if present.
	frappe.db.delete(
		"Property Setter",
		{"doc_type": "Sales Invoice", "field_name": "packing_list", "property": "insert_after"},
	)


def _configure_packed_item_grid():
	"""Packed Items grid shows only: Parent Item, Item Code, Qty, Warehouse and the
	See-Stock button. Everything else is hidden from the compact grid view."""
	for field in ("parent_item", "item_code", "qty", "warehouse"):
		make_property_setter(
			"Packed Item", field, "in_list_view", 1, "Check", validate_fields_for_doctype=False
		)
	for field in ("description", "rate"):
		make_property_setter(
			"Packed Item", field, "in_list_view", 0, "Check", validate_fields_for_doctype=False
		)
	# Grid columns render in field order — put Qty right after Item Code so the row
	# reads: Parent Item | Item Code | Qty | Warehouse | See Stock.
	meta = frappe.get_meta("Packed Item")
	order = [df.fieldname for df in meta.fields if not getattr(df, "is_custom_field", False)]
	if "qty" in order and "item_code" in order:
		order.remove("qty")
		order.insert(order.index("item_code") + 1, "qty")
		make_property_setter(
			"Packed Item", None, "field_order", json.dumps(order), "Text",
			for_doctype=True, validate_fields_for_doctype=False,
		)


def _lock_print_formats():
	"""Make the Azzir formats the ONLY print formats for their doctypes: disable
	every other Print Format (standard ones included). Re-runs each migrate so any
	standard format re-synced from files gets disabled again.

	Note: the built-in auto "Standard" print (not a Print Format record) can't be
	removed; our format is set as each doctype's default so it's never the fallback.
	"""
	keep = {name for (name, *_rest) in PRINT_FORMATS}
	keep.add("Pickup Slip")
	doctypes = {dt for (_n, dt, *_rest) in PRINT_FORMATS}
	for dt in doctypes:
		for pf in frappe.get_all(
			"Print Format",
			filters={"doc_type": dt, "name": ["not in", list(keep)], "disabled": 0},
			pluck="name",
		):
			frappe.db.set_value("Print Format", pf, "disabled", 1, update_modified=False)


def _upsert_print_format(name, dt, html):
	if frappe.db.exists("Print Format", name):
		pf = frappe.get_doc("Print Format", name)
		pf.html = html
		pf.custom_format = 1
		pf.print_format_type = "Jinja"
		pf.doc_type = dt
		pf.flags.ignore_permissions = True
		pf.save(ignore_permissions=True)
	else:
		frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": name,
				"doc_type": dt,
				"module": "Azzir Fleet",
				"print_format_type": "Jinja",
				"custom_format": 1,
				"standard": "No",
				"html": html,
			}
		).insert(ignore_permissions=True)


def _proforma_html(title, party, show_prices=True):
	party_label = "Customer" if party == "customer" else "Supplier"
	party_value = (
		"{{ doc.customer_name or doc.customer }}"
		if party == "customer"
		else "{{ doc.supplier_name or doc.supplier }}"
	)
	return (
		_PROFORMA_TEMPLATE.replace("__TITLE__", title)
		.replace("__PARTY_LABEL__", party_label)
		.replace("__PARTY_VALUE__", party_value)
		.replace("__PRICES_FLAG__", "True" if show_prices else "False")
	)


def after_install():
	after_migrate()


EXPENSE_ENTRY_HTML = """
<div class="azzir-doc" style="font-size:12px; color:#000;">
	{%- set cur = frappe.db.get_value("Company", doc.company, "default_currency") -%}

	{% if not no_letterhead and letter_head %}<div class="letter-head">{{ letter_head }}</div>{% endif %}

	<div style="text-align:right; margin-bottom:8px;">
		<span style="font-size:28px; font-weight:bold; letter-spacing:1px;">EXPENSE ENTRY</span>
	</div>

	<table style="width:100%; margin-bottom:12px;">
		<tr>
			<td style="vertical-align:top; width:58%;">
				<b>Company:</b> {{ doc.company }}<br>
				<b>Paid From:</b> {{ doc.cash_account or "" }}
				{% if doc.journal_entry %}<br><b>Journal Entry:</b> {{ doc.journal_entry }}{% endif %}
			</td>
			<td style="vertical-align:top; padding-left:15px;">
				<table style="width:100%; border-collapse:collapse;">
					<tr><td style="text-align:right; padding:2px 6px;"><b>Ref :</b></td>
						<td style="border:1px solid #999; padding:2px 6px; text-align:center;">{{ doc.name }}</td></tr>
					<tr><td style="text-align:right; padding:2px 6px;"><b>Date :</b></td>
						<td style="border:1px solid #999; padding:2px 6px; text-align:center;">{{ frappe.utils.formatdate(doc.posting_date) }}</td></tr>
				</table>
			</td>
		</tr>
	</table>

	<table style="width:100%; border-collapse:collapse;">
		<thead>
			<tr style="border-top:2px solid #000; border-bottom:1px solid #000;">
				<th style="padding:5px; text-align:left;">#</th>
				<th style="padding:5px; text-align:left;">Account</th>
				<th style="padding:5px; text-align:left;">Remark</th>
				<th style="padding:5px; text-align:left;">Cost Center</th>
				<th style="padding:5px; text-align:right;">Amount</th>
			</tr>
		</thead>
		<tbody>
			{% for row in doc.accounts %}
			<tr style="border-bottom:1px solid #ddd;">
				<td style="padding:5px;">{{ loop.index }}</td>
				<td style="padding:5px;">{{ row.account }}</td>
				<td style="padding:5px;">{{ row.remark or "" }}</td>
				<td style="padding:5px;">{{ row.cost_center or "" }}</td>
				<td style="padding:5px; text-align:right;">{{ frappe.utils.fmt_money(row.amount, currency=cur) }}</td>
			</tr>
			{% endfor %}
		</tbody>
		<tfoot>
			<tr style="border-top:2px solid #000; font-weight:bold;">
				<td colspan="4" style="padding:6px; text-align:right;">TOTAL :</td>
				<td style="padding:6px; text-align:right;">{{ frappe.utils.fmt_money(doc.total_amount, currency=cur) }}</td>
			</tr>
		</tfoot>
	</table>

	<div style="margin-top:8px;"><b>In Words:</b> {{ frappe.utils.money_in_words(doc.total_amount, cur) }}</div>

	<table style="width:100%; margin-top:45px;">
		<tr>
			<td style="width:33%;"><b>Prepared By:</b> ______________<br>
				<span style="font-size:11px;">{{ frappe.db.get_value("User", doc.owner, "full_name") or doc.owner }}</span></td>
			<td style="width:33%;"><b>Approved By:</b> ______________</td>
			<td style="width:33%;"><b>Received By:</b> ______________</td>
		</tr>
	</table>
</div>
"""


PICKUP_SLIP_HTML = """
<div class="azzir-pickup" style="font-size:12px; color:#000;">
	{% if not no_letterhead and letter_head %}<div class="letter-head">{{ letter_head }}</div>{% endif %}

	<h2 style="text-align:center; margin:6px 0; letter-spacing:1px;">PICKUP SLIP</h2>

	<table style="width:100%; margin-bottom:10px;">
		<tr>
			<td><b>Invoice:</b> {{ doc.name }}<br>
				<b>Date:</b> {{ frappe.utils.formatdate(doc.posting_date) }}<br>
				<b>Prepared By:</b> {{ frappe.db.get_value("User", doc.owner, "full_name") or doc.owner }}</td>
			<td style="text-align:right;"><b>Customer:</b> {{ doc.customer_name or doc.customer }}</td>
		</tr>
	</table>

	<table style="width:100%; border-collapse:collapse;">
		<thead>
			<tr style="border-top:2px solid #000; border-bottom:1px solid #000;">
				<th style="text-align:left; padding:5px;">#</th>
				<th style="text-align:left; padding:5px;">Part Number</th>
				<th style="text-align:left; padding:5px;">Description</th>
				<th style="text-align:right; padding:5px;">Pick Qty</th>
				<th style="text-align:left; padding:5px; width:38%;">Location (Warehouse : Stock)</th>
			</tr>
		</thead>
		<tbody>
			{% for row in doc.items %}
			{% set comps = (doc.packed_items or []) | selectattr("parent_item", "equalto", row.item_code) | list %}
			<tr style="border-bottom:1px solid #ddd; vertical-align:top;">
				<td style="padding:5px;">{{ loop.index }}</td>
				<td style="padding:5px;"><b>{{ row.item_code }}</b></td>
				<td style="padding:5px;">
					{{ row.item_name }}
					{% if comps %}<div style="color:#777; font-size:11px;">(bundle — pick components below)</div>{% endif %}
				</td>
				<td style="padding:5px; text-align:right;"><b>{{ "%.2f"|format(row.qty) }} {{ row.uom }}</b></td>
				<td style="padding:5px;">
					{% if comps %}
						<span style="color:#999;">See components ↓</span>
					{% elif row.warehouse %}
						{% set branch = get_stock_branch(row.item_code, row.warehouse) %}
						{% for w in branch %}
						<div style="padding-left:{{ w.depth * 16 }}px; {% if w.is_group %}font-weight:600;{% endif %}">
							{{ w.warehouse }} : {{ "%.2f"|format(w.qty) }}
						</div>
						{% endfor %}
					{% else %}
						<span style="color:#999;">No warehouse set on this line</span>
					{% endif %}
				</td>
			</tr>
			{% for c in comps %}
			<tr style="border-bottom:1px solid #f2f2f2; vertical-align:top; background:#fafafa;">
				<td style="padding:4px 5px;"></td>
				<td style="padding:4px 5px; padding-left:22px;">└ {{ c.item_code }}</td>
				<td style="padding:4px 5px;">{{ c.item_name }}</td>
				<td style="padding:4px 5px; text-align:right;">{{ "%.2f"|format(c.qty) }}</td>
				<td style="padding:4px 5px;">
					{% if c.warehouse %}<b>{{ c.warehouse }}</b> : {{ "%.2f"|format(c.actual_qty or 0) }}
					{% else %}<span style="color:#c0392b;">No warehouse set</span>{% endif %}
				</td>
			</tr>
			{% endfor %}
			{% endfor %}
		</tbody>
	</table>

	<div style="margin-top:30px;">
		<b>Picked By:</b> ____________________________
		&nbsp;&nbsp;&nbsp;&nbsp; <b>Signature:</b> ____________________
		&nbsp;&nbsp;&nbsp;&nbsp; <b>Date:</b> _____________
	</div>
</div>
"""


_PROFORMA_TEMPLATE = """
<div class="azzir-doc" style="font-size:12px; color:#000;">
	{%- set company_tin = frappe.db.get_value("Company", doc.company, "tax_id") -%}
	{%- set show_prices = __PRICES_FLAG__ -%}
	{%- set hide_part_no = doc.get("azzir_hide_part_no") -%}

	<!-- Letter head (custom formats must include it explicitly) -->
	{% if not no_letterhead and letter_head %}<div class="letter-head">{{ letter_head }}</div>{% endif %}

	<!-- Title -->
	<div style="text-align:right; margin-bottom:8px;">
		<span style="font-size:30px; font-weight:bold; letter-spacing:1px;">__TITLE__</span>
	</div>

	<!-- Party + meta -->
	<table style="width:100%; margin-bottom:12px;">
		<tr>
			<td style="vertical-align:top; width:55%;">
				<b>__PARTY_LABEL__:</b> __PARTY_VALUE__
				<div style="border:1px solid #999; padding:6px; margin-top:4px; min-height:70px;">
					{% if doc.get("address_display") %}{{ doc.address_display }}<br>{% endif %}
					{% if doc.get("contact_display") %}<b>Attn:</b> {{ doc.contact_display }}<br>{% endif %}
					{% if doc.get("contact_mobile") %}<b>Phone:</b> {{ doc.contact_mobile }}<br>{% endif %}
					{% if doc.get("contact_email") %}<b>Email:</b> {{ doc.contact_email }}{% endif %}
				</div>
			</td>
			<td style="vertical-align:top; padding-left:15px;">
				<table style="width:100%; border-collapse:collapse;">
					<tr><td style="text-align:right; padding:2px 6px;"><b>Ref :</b></td>
						<td style="border:1px solid #999; padding:2px 6px; text-align:center;">{{ doc.name }}</td></tr>
					<tr><td style="text-align:right; padding:2px 6px;"><b>Date :</b></td>
						<td style="border:1px solid #999; padding:2px 6px; text-align:center;">{{ frappe.utils.formatdate(doc.get("posting_date") or doc.get("transaction_date")) }}</td></tr>
					{% if doc.get("valid_till") %}
					<tr><td style="text-align:right; padding:2px 6px;"><b>Valid Till :</b></td>
						<td style="border:1px solid #999; padding:2px 6px; text-align:center;">{{ frappe.utils.formatdate(doc.valid_till) }}</td></tr>
					{% endif %}
					<tr><td style="text-align:right; padding:2px 6px;"><b>Currency :</b></td>
						<td style="border:1px solid #999; padding:2px 6px; text-align:center;">{{ doc.currency }}</td></tr>
					<tr><td style="text-align:right; padding:2px 6px;"><b>TIN :</b></td>
						<td style="border:1px solid #999; padding:2px 6px; text-align:center;">{{ company_tin or "" }}</td></tr>
				</table>
			</td>
		</tr>
	</table>

	<!-- Items -->
	<table style="width:100%; border-collapse:collapse;">
		<thead>
			<tr style="border-top:2px solid #000; border-bottom:1px solid #000;">
				<th style="padding:5px; text-align:left;">#</th>
				{% if not hide_part_no %}<th style="padding:5px; text-align:left;">Part Number</th>{% endif %}
				<th style="padding:5px; text-align:left;">Description</th>
				<th style="padding:5px; text-align:right;">Qty</th>
				{% if show_prices %}
				<th style="padding:5px; text-align:right;">Price</th>
				<th style="padding:5px; text-align:right;">Disc</th>
				<th style="padding:5px; text-align:right;">Tax</th>
				<th style="padding:5px; text-align:right;">Total (Excl)</th>
				{% endif %}
			</tr>
		</thead>
		<tbody>
			{% for row in doc.items %}
			{% set alt = row.get("azzir_old_code") or get_item_previous_code(row.item_code) %}
			<tr style="border-bottom:1px solid #ddd;">
				<td style="padding:5px;">{{ loop.index }}</td>
				{% if not hide_part_no %}<td style="padding:5px;">{{ row.item_code }}</td>{% endif %}
				<td style="padding:5px;">
					{{ description_for_print(row.item_code, row.description or row.item_name, hide_part_no) }}
					{% if alt and not hide_part_no %}<br><span style="color:#555;">({{ alt }})</span>{% endif %}
				</td>
				<td style="padding:5px; text-align:right;">{{ "%.2f"|format(row.qty) }}</td>
				{% if show_prices %}
				<td style="padding:5px; text-align:right;">{{ frappe.utils.fmt_money(row.rate, currency=doc.currency) }}</td>
				<td style="padding:5px; text-align:right;">{{ frappe.utils.fmt_money(row.discount_amount or 0, currency=doc.currency) }}</td>
				<td style="padding:5px; text-align:right;">{{ frappe.utils.fmt_money(0, currency=doc.currency) }}</td>
				<td style="padding:5px; text-align:right;">{{ frappe.utils.fmt_money(row.net_amount or row.amount, currency=doc.currency) }}</td>
				{% endif %}
			</tr>
			{% endfor %}
		</tbody>
	</table>

	<!-- Notes / Terms (from the document's Terms field — nothing hardcoded) -->
	{% if doc.get("terms") %}<div style="margin:15px 0;">{{ doc.terms }}</div>{% endif %}

	<!-- Prepared by (left) + totals (right) -->
	<table style="width:100%; margin-top:20px;">
		<tr>
			<td style="vertical-align:bottom; width:50%;">
				<table>
					{% if doc.get("payment_terms_template") %}<tr><td><b>Payment Terms:</b></td><td style="padding-left:10px;">{{ doc.payment_terms_template }}</td></tr>{% endif %}
					<tr><td colspan="2" style="padding-top:25px;"><b>Prepared By:</b> {{ frappe.db.get_value("User", doc.owner, "full_name") or doc.owner }}</td></tr>
					<tr><td colspan="2" style="padding-top:15px;"><b>Signature:</b> _____________________</td></tr>
				</table>
			</td>
			<td style="vertical-align:top;">
				{% if show_prices %}
				<table style="width:100%;">
					<tr style="border-top:1px solid #000;">
						<td style="text-align:right; padding:4px;"><b>SUB TOTAL (Excl) :</b></td>
						<td style="text-align:right; padding:4px; width:40%;">{{ frappe.utils.fmt_money(doc.net_total, currency=doc.currency) }}</td>
					</tr>
					<tr>
						<td style="text-align:right; padding:4px;"><b>VAT :</b></td>
						<td style="text-align:right; padding:4px;">{{ frappe.utils.fmt_money(doc.total_taxes_and_charges, currency=doc.currency) }}</td>
					</tr>
					<tr style="border-top:1px solid #000; border-bottom:2px solid #000;">
						<td style="text-align:right; padding:4px;"><b>GRAND TOTAL ({{ doc.currency }}) :</b></td>
						<td style="text-align:right; padding:4px;"><b>{{ frappe.utils.fmt_money(doc.grand_total, currency=doc.currency) }}</b></td>
					</tr>
				</table>
				{% else %}
				<table style="width:100%;">
					<tr><td style="padding-top:25px;"><b>Received By:</b> _____________________</td></tr>
					<tr><td style="padding-top:15px;"><b>Signature:</b> _____________________</td></tr>
				</table>
				{% endif %}
			</td>
		</tr>
	</table>

	{% if show_prices and doc.get("in_words") %}<p style="margin-top:10px;"><b>In Words:</b> {{ doc.in_words }}</p>{% endif %}
</div>
"""
