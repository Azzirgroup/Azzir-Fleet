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
	# Stores the old code the user typed to find this item (captured client-side).
	"Sales Invoice Item": [
		{
			"fieldname": "azzir_old_code",
			"label": "Old Code (entered)",
			"fieldtype": "Data",
			"insert_after": "item_code",
			"read_only": 1,
			"hidden": 1,
			"no_copy": 1,
		}
	],
}


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
	setup_print_format()


def setup_print_format():
	"""Create a Sales Invoice print format that prints `item_code (old_code)`.
	Created once; never overwrites later edits."""
	name = "Sales Invoice with Old Code"
	if frappe.db.exists("Print Format", name):
		return
	frappe.get_doc(
		{
			"doctype": "Print Format",
			"name": name,
			"doc_type": "Sales Invoice",
			"module": "Azzir Fleet",
			"print_format_type": "Jinja",
			"custom_format": 1,
			"standard": "No",
			"html": SALES_INVOICE_OLD_CODE_HTML,
		}
	).insert(ignore_permissions=True)


def after_install():
	after_migrate()


SALES_INVOICE_OLD_CODE_HTML = """
<div class="azzir-invoice">
	<h2 style="margin-bottom:0;">{{ doc.company }}</h2>
	<h4 style="margin-top:4px;">Tax Invoice</h4>
	<table style="width:100%; margin-bottom:10px;">
		<tr>
			<td><b>Invoice #:</b> {{ doc.name }}<br>
				<b>Date:</b> {{ frappe.utils.formatdate(doc.posting_date) }}</td>
			<td style="text-align:right;"><b>Customer:</b> {{ doc.customer_name or doc.customer }}
				{% if doc.po_no %}<br><b>PO #:</b> {{ doc.po_no }}{% endif %}</td>
		</tr>
	</table>
	<table class="table table-bordered" style="width:100%; border-collapse:collapse;">
		<thead>
			<tr>
				<th style="width:5%;">#</th>
				<th style="width:45%;">Item</th>
				<th style="width:12%; text-align:right;">Qty</th>
				<th style="width:18%; text-align:right;">Rate</th>
				<th style="width:20%; text-align:right;">Amount</th>
			</tr>
		</thead>
		<tbody>
			{% for row in doc.items %}
			<tr>
				<td>{{ row.idx }}</td>
				<td>
					<b>{{ row.item_code }}{% if row.azzir_old_code %} ({{ row.azzir_old_code }}){% endif %}</b>
					{% if row.item_name and row.item_name != row.item_code %}<br>{{ row.item_name }}{% endif %}
				</td>
				<td style="text-align:right;">{{ row.qty }} {{ row.uom }}</td>
				<td style="text-align:right;">{{ frappe.utils.fmt_money(row.rate, currency=doc.currency) }}</td>
				<td style="text-align:right;">{{ frappe.utils.fmt_money(row.amount, currency=doc.currency) }}</td>
			</tr>
			{% endfor %}
		</tbody>
	</table>
	<table style="width:100%; margin-top:10px;">
		<tr>
			<td style="text-align:right;"><b>Net Total:</b></td>
			<td style="text-align:right; width:25%;">{{ frappe.utils.fmt_money(doc.net_total, currency=doc.currency) }}</td>
		</tr>
		{% for tax in doc.taxes %}
		<tr>
			<td style="text-align:right;">{{ tax.description }}:</td>
			<td style="text-align:right;">{{ frappe.utils.fmt_money(tax.tax_amount, currency=doc.currency) }}</td>
		</tr>
		{% endfor %}
		<tr>
			<td style="text-align:right;"><b>Grand Total:</b></td>
			<td style="text-align:right;"><b>{{ frappe.utils.fmt_money(doc.grand_total, currency=doc.currency) }}</b></td>
		</tr>
	</table>
	{% if doc.in_words %}<p style="margin-top:8px;"><b>In Words:</b> {{ doc.in_words }}</p>{% endif %}
</div>
"""
