# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})

	conditions, params = get_conditions(filters)
	data = get_data(conditions, params)
	columns = get_columns()
	chart = get_chart(data)
	report_summary = get_report_summary(data)

	return columns, data, None, chart, report_summary


def get_conditions(filters):
	# update_stock = 0: an invoice that already moved stock itself needs no
	# separate receipt. pii.purchase_receipt is empty: this line was NOT made
	# from an already-submitted receipt (the normal "received first" flow) --
	# it is still waiting on one, made the other way round (invoice first).
	conditions = [
		"pi.docstatus = 1",
		"pi.is_return = 0",
		"pi.update_stock = 0",
		"(pii.purchase_receipt is null or pii.purchase_receipt = '')",
	]
	params = {}

	if filters.get("company"):
		conditions.append("pi.company = %(company)s")
		params["company"] = filters.company

	if filters.get("supplier"):
		conditions.append("pi.supplier = %(supplier)s")
		params["supplier"] = filters.supplier

	if filters.get("from_date"):
		conditions.append("pi.posting_date >= %(from_date)s")
		params["from_date"] = filters.from_date

	if filters.get("to_date"):
		conditions.append("pi.posting_date <= %(to_date)s")
		params["to_date"] = filters.to_date

	if filters.get("item_code"):
		conditions.append("pii.item_code = %(item_code)s")
		params["item_code"] = filters.item_code

	if filters.get("item_group"):
		conditions.append("pii.item_group = %(item_group)s")
		params["item_group"] = filters.item_group

	if filters.get("warehouse"):
		conditions.append("pii.warehouse = %(warehouse)s")
		params["warehouse"] = filters.warehouse

	return conditions, params


def get_data(conditions, params):
	"""One row per Purchase Invoice line still waiting on a Purchase Receipt.
	Received-so-far is picked up from the REVERSE link: a Purchase Receipt
	made later "against" this invoice stamps purchase_invoice/
	purchase_invoice_item onto its own item row, not onto the invoice's."""
	query = f"""
		SELECT
			pi.name AS purchase_invoice,
			pi.posting_date AS posting_date,
			pi.supplier AS supplier,
			pi.supplier_name AS supplier_name,
			pi.company AS company,
			pii.name AS pii_name,
			pii.item_code AS item_code,
			pii.item_name AS item_name,
			pii.item_group AS item_group,
			pii.purchase_order AS purchase_order,
			pii.warehouse AS warehouse,
			pii.cost_center AS cost_center,
			pii.uom AS uom,
			pii.qty AS invoiced_qty,
			pii.rate AS rate,
			COALESCE(SUM(pri.received_qty), 0) AS received_qty,
			DATEDIFF(CURDATE(), pi.posting_date) AS days_outstanding
		FROM `tabPurchase Invoice` pi
		INNER JOIN `tabPurchase Invoice Item` pii ON pii.parent = pi.name
		LEFT JOIN `tabPurchase Receipt Item` pri
			ON pri.purchase_invoice_item = pii.name AND pri.docstatus = 1
		WHERE {" AND ".join(conditions)}
		GROUP BY pii.name
		HAVING (pii.qty - COALESCE(SUM(pri.received_qty), 0)) > 0.0001
		ORDER BY pi.posting_date ASC
	"""
	rows = frappe.db.sql(query, params, as_dict=True)

	for row in rows:
		row.outstanding_qty = flt(row.invoiced_qty) - flt(row.received_qty)
		row.outstanding_amount = row.outstanding_qty * flt(row.rate)
		row.status = _("Partially Received") if flt(row.received_qty) > 0 else _("Not Received")
		del row["pii_name"]

	return rows


def get_columns():
	return [
		{"fieldname": "purchase_invoice", "label": _("Purchase Invoice"), "fieldtype": "Link", "options": "Purchase Invoice", "width": 150},
		{"fieldname": "posting_date", "label": _("Invoice Date"), "fieldtype": "Date", "width": 95},
		{"fieldname": "days_outstanding", "label": _("Days Pending"), "fieldtype": "Int", "width": 95},
		{"fieldname": "supplier", "label": _("Supplier"), "fieldtype": "Link", "options": "Supplier", "width": 150},
		{"fieldname": "supplier_name", "label": _("Supplier Name"), "fieldtype": "Data", "width": 160},
		{"fieldname": "item_code", "label": _("Item"), "fieldtype": "Link", "options": "Item", "width": 120},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 160},
		{"fieldname": "item_group", "label": _("Item Group"), "fieldtype": "Link", "options": "Item Group", "width": 110},
		{"fieldname": "purchase_order", "label": _("Purchase Order"), "fieldtype": "Link", "options": "Purchase Order", "width": 130},
		{"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 140},
		{"fieldname": "cost_center", "label": _("Cost Center"), "fieldtype": "Link", "options": "Cost Center", "width": 130},
		{"fieldname": "uom", "label": _("UOM"), "fieldtype": "Link", "options": "UOM", "width": 70},
		{"fieldname": "invoiced_qty", "label": _("Invoiced Qty"), "fieldtype": "Float", "width": 100},
		{"fieldname": "received_qty", "label": _("Received Qty"), "fieldtype": "Float", "width": 100},
		{"fieldname": "outstanding_qty", "label": _("Outstanding Qty"), "fieldtype": "Float", "width": 110},
		{"fieldname": "rate", "label": _("Rate"), "fieldtype": "Currency", "width": 100},
		{"fieldname": "outstanding_amount", "label": _("Outstanding Amount"), "fieldtype": "Currency", "width": 140},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 120},
		{"fieldname": "company", "label": _("Company"), "fieldtype": "Link", "options": "Company", "width": 120},
	]


def get_chart(data):
	if not data:
		return None

	# Top 15 suppliers by outstanding amount -- who to chase first.
	by_supplier = {}
	for row in data:
		key = row.get("supplier_name") or row.get("supplier")
		by_supplier[key] = by_supplier.get(key, 0) + flt(row.get("outstanding_amount"))

	top = sorted(by_supplier.items(), key=lambda x: x[1], reverse=True)[:15]

	return {
		"data": {
			"labels": [t[0] for t in top],
			"datasets": [{"name": _("Outstanding Amount"), "values": [t[1] for t in top]}],
		},
		"type": "bar",
		"colors": ["#e74c3c"],
	}


def get_report_summary(data):
	if not data:
		return []

	total_amount = sum(flt(row.get("outstanding_amount")) for row in data)
	total_qty = sum(flt(row.get("outstanding_qty")) for row in data)
	suppliers_affected = len({row.get("supplier") for row in data})
	oldest = max(flt(row.get("days_outstanding")) for row in data)

	return [
		{"value": len(data), "label": _("Pending Invoice Lines"), "datatype": "Int"},
		{"value": suppliers_affected, "label": _("Suppliers Affected"), "datatype": "Int"},
		{"value": total_qty, "label": _("Outstanding Qty"), "datatype": "Float"},
		{"value": total_amount, "label": _("Outstanding Amount"), "datatype": "Currency"},
		{"value": int(oldest), "label": _("Oldest Pending (Days)"), "datatype": "Int"},
	]
