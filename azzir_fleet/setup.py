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
	"""Create/refresh the Sales Invoice print format (proforma style, item code +
	alternative code in description + preparer name)."""
	name = "Sales Invoice with Old Code"
	if frappe.db.exists("Print Format", name):
		pf = frappe.get_doc("Print Format", name)
		pf.html = SALES_INVOICE_OLD_CODE_HTML
		pf.custom_format = 1
		pf.print_format_type = "Jinja"
		pf.flags.ignore_permissions = True
		pf.save(ignore_permissions=True)
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
<div class="azzir-invoice" style="font-size:12px; color:#000;">
	{%- set company_tin = frappe.db.get_value("Company", doc.company, "tax_id") -%}

	<!-- Title -->
	<div style="text-align:right; margin-bottom:8px;">
		<span style="font-size:22px; font-style:italic; font-weight:bold;">PROFORMA INVOICE</span>
	</div>

	<!-- Customer + meta -->
	<table style="width:100%; margin-bottom:12px;">
		<tr>
			<td style="vertical-align:top; width:55%;">
				<b>Customer:</b> {{ doc.customer_name or doc.customer }}
				<div style="border:1px solid #999; padding:6px; margin-top:4px; min-height:70px;">
					<b>{{ doc.customer_name or doc.customer }}</b><br>
					{% if doc.address_display %}{{ doc.address_display }}{% endif %}
				</div>
			</td>
			<td style="vertical-align:top; padding-left:15px;">
				<table style="width:100%; border-collapse:collapse;">
					<tr><td style="text-align:right; padding:2px 6px;"><b>Ref :</b></td>
						<td style="border:1px solid #999; padding:2px 6px; text-align:center;">{{ doc.po_no or doc.name }}</td></tr>
					<tr><td style="text-align:right; padding:2px 6px;"><b>Date :</b></td>
						<td style="border:1px solid #999; padding:2px 6px; text-align:center;">{{ frappe.utils.formatdate(doc.posting_date) }}</td></tr>
					<tr><td style="text-align:right; padding:2px 6px;"><b>Currency :</b></td>
						<td style="border:1px solid #999; padding:2px 6px; text-align:center;">{{ doc.currency }}</td></tr>
					<tr><td style="text-align:right; padding:2px 6px;"><b>S-TIN :</b></td>
						<td style="border:1px solid #999; padding:2px 6px; text-align:center;">{{ company_tin or "" }}</td></tr>
					<tr><td style="text-align:right; padding:2px 6px;"><b>S-VRN :</b></td>
						<td style="border:1px solid #999; padding:2px 6px; text-align:center;">{{ doc.company_tax_id or "" }}</td></tr>
				</table>
			</td>
		</tr>
	</table>

	<!-- Items -->
	<table style="width:100%; border-collapse:collapse;">
		<thead>
			<tr style="border-top:2px solid #000; border-bottom:1px solid #000;">
				<th style="padding:5px; text-align:left;">Item Code</th>
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
				<td style="padding:5px;">{{ row.item_code }}</td>
				<td style="padding:5px;">
					{{ row.item_name }}
					{% if alt %}<br><span style="color:#555;">Alt: {{ alt }}</span>{% endif %}
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

	<!-- Notes / Terms (from the invoice's Terms field — nothing hardcoded) -->
	{% if doc.terms %}<div style="margin:15px 0;">{{ doc.terms }}</div>{% endif %}

	<!-- Terms (left) + totals (right) -->
	<table style="width:100%; margin-top:20px;">
		<tr>
			<td style="vertical-align:bottom; width:50%;">
				<table>
					<tr><td><b>Payment Terms:</b></td><td style="padding-left:10px;">{{ doc.payment_terms_template or "" }}</td></tr>
					<tr><td><b>Validity:</b></td><td style="padding-left:10px;">{{ doc.get("validity") or "" }}</td></tr>
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
						<td style="text-align:right; padding:4px;"><b>INVOICE TOTAL ({{ doc.currency }}) :</b></td>
						<td style="text-align:right; padding:4px;"><b>{{ frappe.utils.fmt_money(doc.grand_total, currency=doc.currency) }}</b></td>
					</tr>
				</table>
			</td>
		</tr>
	</table>

	{% if doc.in_words %}<p style="margin-top:10px;"><b>In Words:</b> {{ doc.in_words }}</p>{% endif %}
</div>
"""
