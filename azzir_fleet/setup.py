# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""App setup — installs the Item Codes child table on Item."""

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
	# Live stock columns on the Quotation grid (read-only; filled client-side).
	"Quotation Item": [
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

OVERRIDE_ROLE = "Azzir Stock Override"


def after_migrate():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
	# Keep the Units of Measure section (which now holds the Item Codes table)
	# always expanded.
	make_property_setter(
		"Item",
		"unit_of_measure_conversion",
		"collapsible",
		0,
		"Check",
		validate_fields_for_doctype=False,
	)
	setup_print_formats()
	# Relabel Item Code -> Part Number on the Item master.
	make_property_setter(
		"Item", "item_code", "label", "Part Number", "Data", validate_fields_for_doctype=False
	)
	_setup_override_role()
	_enforce_single_session()
	_enable_multicurrency()


def _setup_override_role():
	"""Role whose holders bypass the min/max/stock qty limits."""
	if not frappe.db.exists("Role", OVERRIDE_ROLE):
		frappe.get_doc(
			{"doctype": "Role", "role_name": OVERRIDE_ROLE, "desk_access": 1}
		).insert(ignore_permissions=True)


def _enforce_single_session():
	"""One active session per user (logging in elsewhere ends the old session).

	The actual switch is System Settings.deny_multiple_sessions — without it,
	simultaneous_sessions alone does NOT log the user out on a new device.
	"""
	frappe.db.set_single_value("System Settings", "deny_multiple_sessions", 1)
	make_property_setter(
		"User", "simultaneous_sessions", "default", 1, "Data", validate_fields_for_doctype=False
	)
	for user in frappe.get_all(
		"User",
		filters={"enabled": 1, "name": ["not in", ("Administrator", "Guest")]},
		pluck="name",
	):
		if frappe.db.get_value("User", user, "simultaneous_sessions") != 1:
			frappe.db.set_value("User", user, "simultaneous_sessions", 1, update_modified=False)


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
	# (print format name, doctype, title, party)
	("Sales Invoice with Old Code", "Sales Invoice", "PROFORMA INVOICE", "customer"),
	("Quotation (Azzir)", "Quotation", "PROFORMA INVOICE", "customer"),
	("Sales Order (Azzir)", "Sales Order", "SALES ORDER", "customer"),
	("Delivery Note (Azzir)", "Delivery Note", "DELIVERY NOTE", "customer"),
	("Purchase Order (Azzir)", "Purchase Order", "PURCHASE ORDER", "supplier"),
	("Purchase Receipt (Azzir)", "Purchase Receipt", "PURCHASE RECEIPT", "supplier"),
	("Purchase Invoice (Azzir)", "Purchase Invoice", "PURCHASE INVOICE", "supplier"),
	("Supplier Quotation (Azzir)", "Supplier Quotation", "SUPPLIER QUOTATION", "supplier"),
]


def setup_print_formats():
	"""Create/refresh proforma-style print formats for all transaction doctypes
	and set each as its doctype's default."""
	for name, dt, title, party in PRINT_FORMATS:
		html = _proforma_html(title, party)
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


def _proforma_html(title, party):
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
	)


def after_install():
	after_migrate()


PICKUP_SLIP_HTML = """
<div class="azzir-pickup" style="font-size:12px; color:#000;">
	{% if not no_letterhead and letter_head %}<div class="letter-head">{{ letter_head }}</div>{% endif %}

	<h2 style="text-align:center; margin:6px 0; letter-spacing:1px;">PICKUP SLIP</h2>

	<table style="width:100%; margin-bottom:10px;">
		<tr>
			<td><b>Invoice:</b> {{ doc.name }}<br><b>Date:</b> {{ frappe.utils.formatdate(doc.posting_date) }}</td>
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
			<tr style="border-bottom:1px solid #ddd; vertical-align:top;">
				<td style="padding:5px;">{{ loop.index }}</td>
				<td style="padding:5px;"><b>{{ row.item_code }}</b></td>
				<td style="padding:5px;">{{ row.item_name }}</td>
				<td style="padding:5px; text-align:right;"><b>{{ "%.2f"|format(row.qty) }} {{ row.uom }}</b></td>
				<td style="padding:5px;">
					{% set tree = get_stock_tree(row.item_code) %}
					{% if tree %}
						{% for w in tree %}
						<div style="padding-left:{{ w.depth * 16 }}px; {% if w.is_group %}font-weight:600;{% endif %}">
							{{ '[+]' if w.is_group else '-' }} {{ w.warehouse }} : {{ "%.2f"|format(w.qty) }}
						</div>
						{% endfor %}
					{% else %}
						<span style="color:#999;">No stock recorded</span>
					{% endif %}
				</td>
			</tr>
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
					{% if doc.get("address_display") %}{{ doc.address_display }}{% endif %}
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
				<th style="padding:5px; text-align:left;">Part Number</th>
				<th style="padding:5px; text-align:left;">Description</th>
				<th style="padding:5px; text-align:right;">Qty</th>
				<th style="padding:5px; text-align:right;">Price</th>
				<th style="padding:5px; text-align:right;">Disc</th>
				<th style="padding:5px; text-align:right;">Tax</th>
				<th style="padding:5px; text-align:right;">Total (Excl)</th>
			</tr>
		</thead>
		<tbody>
			{% for row in doc.items %}
			{% set alt = row.get("azzir_old_code") or get_item_old_codes(row.item_code) %}
			<tr style="border-bottom:1px solid #ddd;">
				<td style="padding:5px;">{{ loop.index }}</td>
				<td style="padding:5px;">{{ row.item_code }}</td>
				<td style="padding:5px;">
					{{ row.item_name }}
					{% if alt %}<br><span style="color:#555;">({{ alt }})</span>{% endif %}
				</td>
				<td style="padding:5px; text-align:right;">{{ "%.2f"|format(row.qty) }}</td>
				<td style="padding:5px; text-align:right;">{{ frappe.utils.fmt_money(row.rate, currency=doc.currency) }}</td>
				<td style="padding:5px; text-align:right;">{{ frappe.utils.fmt_money(row.discount_amount or 0, currency=doc.currency) }}</td>
				<td style="padding:5px; text-align:right;">{{ frappe.utils.fmt_money(0, currency=doc.currency) }}</td>
				<td style="padding:5px; text-align:right;">{{ frappe.utils.fmt_money(row.net_amount or row.amount, currency=doc.currency) }}</td>
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
			</td>
		</tr>
	</table>

	{% if doc.get("in_words") %}<p style="margin-top:10px;"><b>In Words:</b> {{ doc.in_words }}</p>{% endif %}
</div>
"""
