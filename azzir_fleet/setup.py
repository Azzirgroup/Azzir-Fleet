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
		},
		{
			"fieldname": "azzir_customer_logo",
			"label": "Customer Logo",
			"fieldtype": "Attach Image",
			"insert_after": "image",
			"description": "Shown next to the customer name on the print formats when set.",
		},
	],
	# A picture + remarks placed directly on the Quotation — shown on the printout.
	"Quotation": [
		{
			"fieldname": "azzir_quotation_image",
			"label": "Quotation Image",
			"fieldtype": "Attach Image",
			"insert_after": "company",
			"description": "Optional picture shown on this quotation's printout (below the items).",
		},
		{
			"fieldname": "azzir_remarks",
			"label": "Remarks",
			"fieldtype": "Small Text",
			"insert_after": "terms",
			"description": "Shown on the printout under the Prepared By / Signature.",
		},
		{
			"fieldname": "azzir_below_cost",
			"label": "Sold Below Buying Price",
			"fieldtype": "Check",
			"insert_after": "order_type",
			"read_only": 1,
			"no_copy": 1,
			"description": "Auto-set when any item's rate is below its valuation/buying price.",
		},
	],
	# Per-row image + remark on Quotation items — both show on the printout.
	"Quotation Item": [
		{
			"fieldname": "azzir_item_image",
			"label": "Image",
			"fieldtype": "Attach Image",
			"insert_after": "description",
		},
		{
			"fieldname": "azzir_item_remark",
			"label": "Remark",
			"fieldtype": "Small Text",
			"insert_after": "azzir_item_image",
			"in_list_view": 1,
		},
		{
			"fieldname": "azzir_previous_price",
			"label": "Previous Price",
			"fieldtype": "Currency",
			"insert_after": "price_list_rate",
			"read_only": 1,
			"options": "currency",
			"description": "The price list rate — so you can see the original price when the rate is lowered.",
		},
	],
	# Previous (list) price on Sales Invoice items too.
	"Sales Invoice Item": [
		{
			"fieldname": "azzir_previous_price",
			"label": "Previous Price",
			"fieldtype": "Currency",
			"insert_after": "price_list_rate",
			"read_only": 1,
			"options": "currency",
			"description": "The price list rate — so you can see the original price when the rate is lowered.",
		},
	],
	# Flag set when any line is sold below buying (valuation) price — drives the
	# below-cost approval workflow.
	"Sales Invoice": [
		{
			"fieldname": "azzir_below_cost",
			"label": "Sold Below Buying Price",
			"fieldtype": "Check",
			"insert_after": "azzir_source_quotation",
			"read_only": 1,
			"no_copy": 1,
			"description": "Auto-set when any item's rate is below its valuation/buying price.",
		},
	],
	# (azzir_remark lives directly in the Expense Entry doctype JSON now — it's our
	# own doctype, so a standard field syncs reliably with the doctype.)
	# Tax Inclusive/Exclusive helper on Expense Entry rows.
	"Expense Entry Account": [
		{"fieldname": "azzir_tax_type", "label": "Tax Type", "fieldtype": "Select",
		 "options": "\nInclusive\nExclusive", "insert_after": "amount", "in_list_view": 1},
		{"fieldname": "azzir_tax_rate", "label": "Tax %", "fieldtype": "Percent",
		 "insert_after": "azzir_tax_type", "in_list_view": 1},
		{"fieldname": "azzir_tax_amount", "label": "Tax Amount", "fieldtype": "Currency",
		 "insert_after": "azzir_tax_rate", "read_only": 1, "in_list_view": 1},
		{"fieldname": "azzir_net_amount", "label": "Net (excl. Tax)", "fieldtype": "Currency",
		 "insert_after": "azzir_tax_amount", "read_only": 1},
	],
	# Same helper on Journal Entry rows.
	"Journal Entry Account": [
		{"fieldname": "azzir_tax_type", "label": "Tax Type", "fieldtype": "Select",
		 "options": "\nInclusive\nExclusive", "insert_after": "credit_in_account_currency"},
		{"fieldname": "azzir_tax_rate", "label": "Tax %", "fieldtype": "Percent",
		 "insert_after": "azzir_tax_type"},
		{"fieldname": "azzir_tax_amount", "label": "Tax Amount", "fieldtype": "Currency",
		 "insert_after": "azzir_tax_rate", "read_only": 1},
		{"fieldname": "azzir_net_amount", "label": "Net (excl. Tax)", "fieldtype": "Currency",
		 "insert_after": "azzir_tax_amount", "read_only": 1},
	],
	# Dynamic intercompany discount — configured PER company (no hardcoding).
	"Company": [
		{
			"fieldname": "azzir_intercompany_discount",
			"label": "Intercompany Receipt Discount (%)",
			"fieldtype": "Percent",
			"insert_after": "default_currency",
			"description": "When THIS company receives stock from a sister company "
			"(intercompany transfer), the transfer rate is reduced by this %. 0 = none.",
		},
		{
			"fieldname": "azzir_letter_head",
			"label": "Print Letter Head",
			"fieldtype": "Link",
			"options": "Letter Head",
			"insert_after": "azzir_intercompany_discount",
			"description": "Letter head to show on this company's Quotation / Sales Invoice "
			"printouts. Lets the printout header change with the company.",
		},
	],
	# Statutory IDs on Employee.
	"Employee": [
		{
			"fieldname": "azzir_tax_id",
			"label": "Tax ID",
			"fieldtype": "Data",
			"insert_after": "company",
		},
		{
			"fieldname": "azzir_social_security_no",
			"label": "Social Security Number",
			"fieldtype": "Data",
			"insert_after": "azzir_tax_id",
		},
		# Employees can belong to more than one cost center.
		{
			"fieldname": "azzir_cost_centers",
			"label": "Cost Centers",
			"fieldtype": "Table",
			"options": "Employee Cost Center",
			"insert_after": "department",
			"description": "Cost centers this employee belongs to. Add a row per cost center.",
		},
	],
	"Warehouse": [
		{
			"fieldname": "azzir_cost_center",
			"label": "Cost Center",
			"fieldtype": "Link",
			"options": "Cost Center",
			"insert_after": "company",
			"description": "Users are allowed to SELECT this warehouse only if they are "
			"assigned this cost center (via User Permission). They can still see it.",
		},
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

# Doc-level toggle to hide the Part Number column on the proforma printout —
# on both Quotation and Sales Invoice.
_HIDE_PART_NO_DESC = (
	"Tick to hide BOTH the Part Number column AND the alternative/previous part "
	"number (in the Description) on this document's printout, so the table starts "
	"at Description."
)
CUSTOM_FIELDS.setdefault("Quotation", []).append(
	{
		"fieldname": "azzir_hide_part_no",
		"label": "Hide Part Numbers on Print",
		"fieldtype": "Check",
		"insert_after": "azzir_invoiced",
		"description": _HIDE_PART_NO_DESC,
	}
)
CUSTOM_FIELDS.setdefault("Sales Invoice", []).append(
	{
		"fieldname": "azzir_hide_part_no",
		"label": "Hide Part Numbers on Print",
		"fieldtype": "Check",
		"insert_after": "azzir_apply_vat",
		"description": _HIDE_PART_NO_DESC,
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

# Hidden flag (fetched from the item) so Warehouse can be made mandatory ONLY for
# stock items — service / non-stock lines don't need a warehouse.
_IS_STOCK_ITEM_FIELD = {
	"fieldname": "azzir_is_stock_item",
	"label": "Is Stock Item",
	"fieldtype": "Check",
	"insert_after": "item_code",
	"fetch_from": "item_code.is_stock_item",
	"read_only": 1,
	"hidden": 1,
	"no_copy": 1,
	"print_hide": 1,
}
for _dt in ("Quotation Item", "Sales Invoice Item", "Delivery Note Item"):
	CUSTOM_FIELDS.setdefault(_dt, []).append(dict(_IS_STOCK_ITEM_FIELD))

# Per-row buy-from-sister source: which sister company/warehouse THIS line is
# bought from. Defaults from the header, but each row can point at a different
# sister; on submit the rows are grouped by sister company into separate transfers.
_ROW_SUPPLY_FIELDS = [
	{
		# Per-row toggle: this line is sourced from a sister company. This is the sole
		# trigger (there is no header checkbox); an invoice can mix sister lines with
		# normal ones. Only eligible users see the column (hidden client-side otherwise).
		"fieldname": "azzir_row_from_sister",
		"label": "Buy From Sister Company",
		"fieldtype": "Check",
		"insert_after": "warehouse",
		"in_list_view": 1,
		"columns": 1,
	},
	{
		"fieldname": "azzir_supply_company",
		"label": "Supply Company",
		"fieldtype": "Link",
		"options": "Company",
		"insert_after": "azzir_row_from_sister",
		# Only relevant on a row that's actually from a sister.
		"depends_on": "eval:doc.azzir_row_from_sister",
		# Show as a grid column (each row can point at a different sister company).
		"in_list_view": 1,
		"columns": 2,
	},
	{
		"fieldname": "azzir_supply_warehouse",
		"label": "Supply Warehouse",
		"fieldtype": "Link",
		"options": "Warehouse",
		"insert_after": "azzir_supply_company",
		"depends_on": "eval:doc.azzir_row_from_sister",
		"in_list_view": 1,
		"columns": 2,
	},
]
for _dt in ("Quotation Item", "Sales Invoice Item"):
	for _f in _ROW_SUPPLY_FIELDS:
		CUSTOM_FIELDS.setdefault(_dt, []).append(dict(_f))

# Per-row link to the sister Delivery Note created for that line at submit.
CUSTOM_FIELDS.setdefault("Sales Invoice Item", []).append(
	{
		"fieldname": "azzir_sister_delivery_note",
		"label": "Delivery Note",
		"fieldtype": "Link",
		"options": "Delivery Note",
		"insert_after": "azzir_supply_warehouse",
		"read_only": 1,
		"in_list_view": 1,
		"columns": 2,
		"depends_on": "eval:parent.azzir_buy_from_sister",
		"description": "The sister Delivery Note auto-created for this line.",
	}
)

# --- Sell sister-company stock (corporate company buys from a sister at a discount)
# Flag a Cost Center as "Corporate": its assigned users can buy sister stock.
CUSTOM_FIELDS.setdefault("Cost Center", []).append(
	{
		"fieldname": "azzir_is_corporate",
		"label": "Corporate",
		"fieldtype": "Check",
		"insert_after": "cost_center_name",
		"description": "Users assigned this cost center may sell stock sourced from a "
		"sister company (buy-from-sister on the Sales Invoice).",
	}
)
# A per-user default Company. Setting it makes every new Quotation / Sales Invoice
# (desk + /sales portal) auto-fill the company (synced to the user's Company
# default — see azzir_fleet.company_default.sync_user_company).
CUSTOM_FIELDS.setdefault("User", []).append(
	{
		"fieldname": "azzir_company",
		"label": "Company",
		"fieldtype": "Link",
		"options": "Company",
		"insert_after": "user_type",
		"description": "Default company for this user — new Quotations and Sales "
		"Invoices (desk and the /sales portal) auto-fill with it.",
	}
)
# On a corporate warehouse, mark it as the landing point for one sister company's stock.
CUSTOM_FIELDS.setdefault("Warehouse", []).extend(
	[
		{
			"fieldname": "azzir_is_sister_landing",
			"label": "Receives Sister Company Stock",
			"fieldtype": "Check",
			"insert_after": "azzir_cost_center",
			"description": "Tick if this warehouse receives stock transferred from a sister company.",
		},
		{
			"fieldname": "azzir_sister_company",
			"label": "Sister Company",
			"fieldtype": "Link",
			"options": "Company",
			"insert_after": "azzir_is_sister_landing",
			"depends_on": "eval:doc.azzir_is_sister_landing",
			"mandatory_depends_on": "eval:doc.azzir_is_sister_landing",
			"description": "Stock bought from THIS sister company lands in this warehouse.",
		},
	]
)
# Sales Invoice: read-only links to the docs the per-row buy-from-sister flow
# auto-creates (also used to stay idempotent). The trigger now lives per item row
# (Sales Invoice Item.azzir_row_from_sister) — there is no header toggle.
CUSTOM_FIELDS.setdefault("Sales Invoice", []).extend(
	[
		{
			"fieldname": "azzir_intercompany_delivery_note",
			"label": "Intercompany Delivery Note",
			"fieldtype": "Link",
			"options": "Delivery Note",
			"insert_after": "company",
			"read_only": 1,
		},
		{
			"fieldname": "azzir_intercompany_sister_invoice",
			"label": "Intercompany Sister Invoice",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"insert_after": "azzir_intercompany_delivery_note",
			"read_only": 1,
		},
		{
			"fieldname": "azzir_intercompany_purchase_invoice",
			"label": "Intercompany Purchase Invoice",
			"fieldtype": "Link",
			"options": "Purchase Invoice",
			"insert_after": "azzir_intercompany_sister_invoice",
			"read_only": 1,
		},
		{
			"fieldname": "azzir_intercompany_done",
			"label": "Intercompany Transfer Done",
			"fieldtype": "Check",
			"insert_after": "azzir_intercompany_purchase_invoice",
			"read_only": 1,
			"print_hide": 1,
		},
		{
			"fieldname": "azzir_intercompany_refs",
			"label": "Intercompany Transfers",
			"fieldtype": "Small Text",
			"insert_after": "azzir_intercompany_done",
			"read_only": 1,
			"print_hide": 1,
			"description": "All sister transfers created for this invoice (one per sister company).",
		},
	]
)

# Quotation: the buy-from-sister choice starts here and carries to the Sales
# Invoice. NO intercompany documents are created at quotation stage — the logic
# only runs when the Sales Invoice is submitted.
# Quotation has no header buy-from-sister fields — the trigger lives per item row
# (Quotation Item.azzir_row_from_sister), same as the Sales Invoice.

# --- Purchase cycle: buy for another (internal) company ---------------------
# Per-row Target Company + Target Warehouse on Purchase Order / Receipt / Invoice
# items. Only used when the target company differs from the buying company (then
# the received stock is transferred there at submit — see azzir_fleet.purchase_cycle).
_ROW_TARGET_FIELDS = [
	{
		# Per-row toggle: this line is bought FOR another internal company. Sole
		# trigger (no header field) — an order can mix target lines with normal ones.
		"fieldname": "azzir_row_to_target",
		"label": "Buy For Target Company",
		"fieldtype": "Check",
		"insert_after": "warehouse",
		"in_list_view": 1,
		"columns": 1,
	},
	{
		"fieldname": "azzir_target_company",
		"label": "Target Company",
		"fieldtype": "Link",
		"options": "Company",
		"insert_after": "azzir_row_to_target",
		"depends_on": "eval:doc.azzir_row_to_target",
		"in_list_view": 1,
		"columns": 2,
		"description": "Buy this line for another internal company.",
	},
	{
		"fieldname": "azzir_target_warehouse",
		"label": "Target Warehouse",
		"fieldtype": "Link",
		"options": "Warehouse",
		"insert_after": "azzir_target_company",
		"depends_on": "eval:doc.azzir_row_to_target",
		"in_list_view": 1,
		"columns": 2,
		"description": "Warehouse in the Target Company that receives this line.",
	},
]
for _dt in ("Purchase Order Item", "Purchase Receipt Item", "Purchase Invoice Item"):
	for _f in _ROW_TARGET_FIELDS:
		CUSTOM_FIELDS.setdefault(_dt, []).append(dict(_f))

# Idempotency + audit trail on the stock-moving documents (header, read-only).
for _dt in ("Purchase Receipt", "Purchase Invoice"):
	CUSTOM_FIELDS.setdefault(_dt, []).extend(
		[
			{
				"fieldname": "azzir_target_done",
				"label": "Inter-company Target Transfer Done",
				"fieldtype": "Check",
				"insert_after": "company",
				"read_only": 1,
				"hidden": 1,
			},
			{
				"fieldname": "azzir_target_refs",
				"label": "Inter-company Target Transfers",
				"fieldtype": "Small Text",
				"insert_after": "azzir_target_done",
				"read_only": 1,
			},
		]
	)


OVERRIDE_ROLE = "Azzir Stock Override"


def _create_custom_fields_resilient():
	"""Create the custom fields ONE DOCTYPE AT A TIME so a single problem field
	(e.g. a doctype missing on a particular site) can't abort the whole batch and
	silently drop every field after it."""
	for _dt, _fields in CUSTOM_FIELDS.items():
		try:
			if not frappe.db.exists("DocType", _dt):
				continue
			create_custom_fields({_dt: _fields}, ignore_validate=True)
		except Exception:
			frappe.log_error(title=f"azzir_fleet custom fields failed for {_dt}")


def after_migrate():
	# Each step runs independently — a failure in one must not stop the others
	# (that's why the Customer Statement report, being last, could go missing).
	steps = [
		("custom_fields", _create_custom_fields_resilient),
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
		("group_stock_role", _setup_group_stock_role),
		("overdue_todo_notification", _setup_overdue_todo_notification),
		("below_cost_workflow", _setup_below_cost_workflow),
		("item_link_code_only", _show_item_code_only_in_links),
		("warehouse_mandatory", _make_warehouse_mandatory),
		("editable_customer_name", _make_customer_name_editable),
		("material_issue_workflow", _setup_material_issue_workflow),
		("session_limit", _enforce_session_limit),
		("multicurrency", _enable_multicurrency),
		("sales_overseer_role", _setup_sales_overseer_role),
		("procurement_overseer_role", _setup_procurement_overseer_role),
		("document_creator_role", _setup_document_creator_role),
		("sales_portal_role", _setup_sales_portal_role),
	]
	for label, fn in steps:
		try:
			fn()
		except Exception:
			frappe.log_error(title=f"azzir_fleet after_migrate failed: {label}")


def _setup_group_stock_role():
	"""Holders of this role see ALL companies' stock in the warehouse dialog;
	everyone else sees only their own default company."""
	if not frappe.db.exists("Role", "Azzir Group Stock"):
		frappe.get_doc(
			{"doctype": "Role", "role_name": "Azzir Group Stock", "desk_access": 1}
		).insert(ignore_permissions=True)


def _setup_sales_overseer_role():
	"""On the Azzir Sales frontend a salesperson only sees the quotations /
	invoices / delivery notes they created. Give a user this role and they see
	ALL sales instead (see azzir_fleet.sales_api.sales_list)."""
	if not frappe.db.exists("Role", "Azzir Sales Overseer"):
		frappe.get_doc(
			{"doctype": "Role", "role_name": "Azzir Sales Overseer", "desk_access": 1}
		).insert(ignore_permissions=True)


def _setup_document_creator_role():
	"""Owner-scoping role for sales documents. A user holding 'Document Creator'
	only ever sees the Quotations / Sales Invoices / Delivery Notes they created
	themselves — on the desk (list views, reports, opening a doc by URL) and in
	the /sales portal. Enforced by permission_query_conditions / has_permission
	in azzir_fleet.sales_api; the role itself grants no document permissions, it
	is added ALONGSIDE a user's normal Sales role."""
	if not frappe.db.exists("Role", "Document Creator"):
		frappe.get_doc(
			{"doctype": "Role", "role_name": "Document Creator", "desk_access": 1}
		).insert(ignore_permissions=True)


def _setup_procurement_overseer_role():
	"""A procurement user only sees the documents they created; give a user this
	role and they see everyone's (see azzir_fleet.procurement)."""
	if not frappe.db.exists("Role", "Azzir Procurement Overseer"):
		frappe.get_doc(
			{"doctype": "Role", "role_name": "Azzir Procurement Overseer", "desk_access": 1}
		).insert(ignore_permissions=True)


def _ensure_unrealized_pl_accounts():
	"""Every company in an intercompany transfer needs an Unrealized Profit / Loss
	Account (ERPNext requirement). Create one per company that lacks it and set it
	on the Company. Idempotent; covers all current and future companies."""
	for company in frappe.get_all("Company", pluck="name"):
		if frappe.db.get_value("Company", company, "unrealized_profit_loss_account"):
			continue
		abbr = frappe.get_cached_value("Company", company, "abbr")
		acc = "Unrealized Profit and Loss - %s" % abbr
		if not frappe.db.exists("Account", acc):
			parent = frappe.db.get_value(
				"Account", {"company": company, "is_group": 1, "root_type": "Liability"}, "name"
			) or frappe.db.get_value("Account", {"company": company, "is_group": 1}, "name")
			if not parent:
				continue
			root_type = frappe.db.get_value("Account", parent, "root_type") or "Liability"
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": "Unrealized Profit and Loss",
					"company": company,
					"parent_account": parent,
					"root_type": root_type,
					"is_group": 0,
				}
			).insert(ignore_permissions=True)
		frappe.db.set_value("Company", company, "unrealized_profit_loss_account", acc)


def _setup_sales_portal_role():
	"""Users with this role are taken straight to the /sales portal on login.

	We deliberately do NOT set Role.home_page = "sales": frappe.get_home_page walks
	EVERY role's home_page, and the Administrator account implicitly has all roles —
	so a role home_page of "sales" would send Administrator to /sales on login. The
	redirect is driven instead by:
	  * route_portal_users_on_login (on_session_creation) — sets flags.home_page for
	    users who ACTUALLY hold the role (Has Role check, Administrator exempt); and
	  * redirect_portal_users_off_desk (before_request) — the authoritative guard.
	If an old Role.home_page = "sales" is present (from a previous version), clear it."""
	if not frappe.db.exists("Role", "Sales Portal"):
		frappe.get_doc(
			{"doctype": "Role", "role_name": "Sales Portal", "desk_access": 1}
		).insert(ignore_permissions=True)
	if frappe.db.get_value("Role", "Sales Portal", "home_page"):
		frappe.db.set_value("Role", "Sales Portal", "home_page", None)
		# The home page is cached per user; drop it so the change takes effect.
		frappe.cache.delete_key("home_page")


def _setup_overdue_todo_notification():
	"""Notify the assignee when an assigned task (ToDo) passes its Complete-By date
	without being done."""
	if frappe.db.exists("Notification", {"document_type": "ToDo", "subject": ["like", "%overdue%"]}):
		return
	if not frappe.db.has_column("ToDo", "date") or not frappe.db.has_column("ToDo", "allocated_to"):
		return
	frappe.get_doc(
		{
			"doctype": "Notification",
			"subject": "Your assigned task is overdue",
			"document_type": "ToDo",
			"is_standard": 0,
			"enabled": 1,
			"channel": "System Notification",
			"event": "Days After",
			"date_changed": "date",
			"days_in_advance": 0,
			"condition": "doc.status not in ('Closed', 'Cancelled') and doc.allocated_to",
			"recipients": [{"receiver_by_document_field": "allocated_to"}],
			"message": (
				"Your assigned task on {{ doc.reference_type or 'a document' }} "
				"{{ doc.reference_name or '' }} was due on {{ doc.date }} and is not done yet."
			),
		}
	).insert(ignore_permissions=True)


def _ensure_workflow_states_actions():
	"""Shared Workflow State + Action Master records used by our approval workflows."""
	for state, style in (("Draft", "Danger"), ("Pending Approval", "Warning"), ("Approved", "Success")):
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{"doctype": "Workflow State", "workflow_state_name": state, "style": style}
			).insert(ignore_permissions=True)
	for action in ("Submit", "Request Approval", "Approve", "Reject"):
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc(
				{"doctype": "Workflow Action Master", "workflow_action_name": action}
			).insert(ignore_permissions=True)


def _setup_below_cost_workflow():
	"""Route below-cost Sales Invoices through manager approval; normal ones submit
	directly. Uses the azzir_below_cost flag (set on validate) in the transition
	conditions."""
	_ensure_workflow_states_actions()
	# Same below-cost approval on both Sales Invoice and Quotation.
	_make_below_cost_workflow("Sales Below Cost Approval", "Sales Invoice", "Accounts User", "Accounts Manager")
	_make_below_cost_workflow("Quotation Below Cost Approval", "Quotation", "Sales User", "Sales Manager")


def _show_item_code_only_in_links():
	"""Item link fields (Sales Invoice items, etc.) show just the item CODE, not
	'code: item_name'. Turns off 'Show Title in Link Fields' on the Item doctype."""
	make_property_setter(
		"Item", None, "show_title_field_in_link", 0, "Check",
		for_doctype=True, validate_fields_for_doctype=False,
	)


def _make_warehouse_mandatory():
	"""Warehouse is required on any line that carries a STOCK item — a region on
	Quotation / Sales Invoice, a bin on Delivery Note. Service / non-stock lines
	are exempt (via the azzir_is_stock_item fetch flag)."""
	for dt in ("Quotation Item", "Sales Invoice Item", "Delivery Note Item"):
		make_property_setter(
			dt, "warehouse", "mandatory_depends_on", "eval:doc.azzir_is_stock_item", "Data",
			validate_fields_for_doctype=False,
		)


def _make_customer_name_editable():
	"""Let users override the fetched Customer Name on sales documents. It still
	auto-fills from the customer, but becomes editable and carries downstream
	(Quotation -> Sales Invoice -> Delivery Note)."""
	for dt in ("Quotation", "Sales Invoice", "Delivery Note"):
		make_property_setter(dt, "customer_name", "read_only", 0, "Check", validate_fields_for_doctype=False)


def _setup_material_issue_workflow():
	"""Route Stock Entries of type 'Material Issue' through approval; every other
	stock entry type keeps the plain 'Submit'. OFF by default (activate when ready)."""
	_ensure_workflow_states_actions()
	name = "Material Issue Approval"
	if frappe.db.exists("Workflow", name):
		return
	submit_role, approve_role = "Stock User", "Stock Manager"
	frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": name,
			"document_type": "Stock Entry",
			"is_active": 0,
			"send_email_alert": 0,
			"workflow_state_field": "workflow_state",
			"states": [
				{"state": "Draft", "doc_status": "0", "allow_edit": submit_role},
				{"state": "Pending Approval", "doc_status": "0", "allow_edit": approve_role},
				{"state": "Approved", "doc_status": "1", "allow_edit": approve_role},
			],
			"transitions": [
				{"state": "Draft", "action": "Submit", "next_state": "Approved",
				 "allowed": submit_role, "condition": 'doc.stock_entry_type != "Material Issue"'},
				{"state": "Draft", "action": "Request Approval", "next_state": "Pending Approval",
				 "allowed": submit_role, "condition": 'doc.stock_entry_type == "Material Issue"'},
				{"state": "Pending Approval", "action": "Approve", "next_state": "Approved",
				 "allowed": approve_role},
				{"state": "Pending Approval", "action": "Reject", "next_state": "Draft",
				 "allowed": approve_role},
			],
		}
	).insert(ignore_permissions=True)


def _make_below_cost_workflow(name, doctype, submit_role, approve_role):
	"""Normal docs -> 'Submit' only; below-cost -> 'Request Approval' then a manager
	'Approve'. Built OFF by default (a workflow appears on ALL docs once active)."""
	if frappe.db.exists("Workflow", name):
		return
	frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": name,
			"document_type": doctype,
			"is_active": 0,
			"send_email_alert": 0,
			"workflow_state_field": "workflow_state",
			"states": [
				{"state": "Draft", "doc_status": "0", "allow_edit": submit_role},
				{"state": "Pending Approval", "doc_status": "0", "allow_edit": approve_role},
				{"state": "Approved", "doc_status": "1", "allow_edit": approve_role},
			],
			"transitions": [
				{"state": "Draft", "action": "Submit", "next_state": "Approved",
				 "allowed": submit_role, "condition": "doc.azzir_below_cost == 0"},
				{"state": "Draft", "action": "Request Approval", "next_state": "Pending Approval",
				 "allowed": submit_role, "condition": "doc.azzir_below_cost == 1"},
				{"state": "Pending Approval", "action": "Approve", "next_state": "Approved",
				 "allowed": approve_role},
				{"state": "Pending Approval", "action": "Reject", "next_state": "Draft",
				 "allowed": approve_role},
			],
		}
	).insert(ignore_permissions=True)


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

	# Monthly Budget print format (set as its default).
	if frappe.db.exists("DocType", "Monthly Budget"):
		_upsert_print_format("Monthly Budget (Azzir)", "Monthly Budget", MONTHLY_BUDGET_HTML)
		make_property_setter(
			"Monthly Budget", None, "default_print_format", "Monthly Budget (Azzir)", "Data",
			for_doctype=True, validate_fields_for_doctype=False,
		)

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


MONTHLY_BUDGET_HTML = """
<div class="azzir-budget" style="font-size:12px; color:#000;">
	{% if not no_letterhead and letter_head %}<div class="letter-head">{{ letter_head }}</div>{% endif %}
	{%- set cur = frappe.db.get_value("Company", doc.company, "default_currency") -%}

	<h2 style="text-align:center; letter-spacing:1px; margin:6px 0;">MONTHLY BUDGET</h2>

	<table style="width:100%; margin-bottom:10px;">
		<tr>
			<td style="vertical-align:top;">
				<b>Company:</b> {{ doc.company }}<br>
				<b>Period:</b> {{ doc.month }} {{ doc.year }}
				{% if doc.get("from_date") %}<br><b>Dates:</b> {{ frappe.utils.formatdate(doc.from_date) }} &mdash; {{ frappe.utils.formatdate(doc.to_date) }}{% endif %}
			</td>
			<td style="vertical-align:top; text-align:right;">
				<b>Ref:</b> {{ doc.name }}<br>
				<b>If Exceeded:</b> {{ doc.action_if_exceeded }}
			</td>
		</tr>
	</table>

	<table style="width:100%; border-collapse:collapse;">
		<thead>
			<tr style="border-top:2px solid #000; border-bottom:1px solid #000;">
				<th style="text-align:left; padding:5px;">#</th>
				<th style="text-align:left; padding:5px;">Account</th>
				<th style="text-align:right; padding:5px;">Budget</th>
				<th style="text-align:right; padding:5px;">Actual</th>
				<th style="text-align:right; padding:5px;">Balance</th>
			</tr>
		</thead>
		<tbody>
			{% for row in doc.accounts %}
			<tr style="border-bottom:1px solid #ddd;">
				<td style="padding:5px;">{{ loop.index }}</td>
				<td style="padding:5px;">{{ row.account }}</td>
				<td style="padding:5px; text-align:right;">{{ frappe.utils.fmt_money(row.amount, currency=cur) }}</td>
				<td style="padding:5px; text-align:right;">{{ frappe.utils.fmt_money(row.actual_amount, currency=cur) }}</td>
				<td style="padding:5px; text-align:right; {% if row.balance < 0 %}color:#c0392b;{% endif %}">{{ frappe.utils.fmt_money(row.balance, currency=cur) }}</td>
			</tr>
			{% endfor %}
			<tr style="border-top:2px solid #000; font-weight:bold;">
				<td colspan="2" style="padding:6px; text-align:right;">TOTAL :</td>
				<td style="padding:6px; text-align:right;">{{ frappe.utils.fmt_money(doc.total_budget, currency=cur) }}</td>
				<td style="padding:6px; text-align:right;">{{ frappe.utils.fmt_money(doc.total_actual, currency=cur) }}</td>
				<td style="padding:6px; text-align:right;">{{ frappe.utils.fmt_money(doc.total_balance, currency=cur) }}</td>
			</tr>
		</tbody>
	</table>

	<div style="margin-top:25px;">
		<b>Prepared By:</b> {{ frappe.db.get_value("User", doc.owner, "full_name") or doc.owner }}
		&nbsp;&nbsp;&nbsp;&nbsp; <b>Signature:</b> ____________________
	</div>
</div>
"""


PICKUP_SLIP_HTML = """
<div class="azzir-pickup" style="font-size:12px; color:#000;">
	{% if not no_letterhead and letter_head %}<div class="letter-head">{{ letter_head }}</div>{% endif %}

	<h2 style="text-align:center; margin:6px 0; letter-spacing:1px;">PICKUP SLIP</h2>
	{% if (doc.get("items") or []) | selectattr("azzir_row_from_sister") | list %}<div style="text-align:center; color:#b00; font-size:11px; margin:-2px 0 8px;">Some lines are picked from a <b>sister company</b> warehouse (shown below)</div>{% endif %}

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
					{% elif row.get("azzir_row_from_sister") and row.get("azzir_supply_warehouse") %}
						{# Buy-from-sister: pick from the SISTER warehouse the stock was
						   requested from (the Delivery Note source), not our landing warehouse. #}
						{% set sw = row.azzir_supply_warehouse %}
						{% set sqty = frappe.db.get_value("Bin", {"item_code": row.item_code, "warehouse": sw}, "actual_qty") or 0 %}
						<div style="font-weight:600;">{{ sw }} : {{ "%.2f"|format(sqty) }}</div>
						{% if row.get("azzir_supply_company") %}<div style="color:#777; font-size:11px;">Sister: {{ row.azzir_supply_company }}</div>{% endif %}
						{% if row.get("azzir_sister_delivery_note") %}<div style="color:#777; font-size:11px;">DN: {{ row.azzir_sister_delivery_note }}</div>{% endif %}
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

	<!-- Letter head — per company: use the company's configured letter head so the
	     printout header changes with the company; fall back to the doc's letter head. -->
	{%- set _co_lh = frappe.db.get_value("Company", doc.company, "azzir_letter_head") -%}
	{%- set _lh_html = (frappe.db.get_value("Letter Head", _co_lh, "content") if _co_lh else None) or letter_head -%}
	{% if not no_letterhead and _lh_html %}<div class="letter-head">{{ _lh_html }}</div>{% endif %}

	<!-- Title -->
	<div style="text-align:right; margin-bottom:8px;">
		<span style="font-size:30px; font-weight:bold; letter-spacing:1px;">__TITLE__</span>
	</div>

	<!-- Party + meta -->
	<table style="width:100%; margin-bottom:12px;">
		<tr>
			<td style="vertical-align:top; width:55%;">
				{%- set _cust = doc.get("customer") or (doc.get("party_name") if doc.get("quotation_to") == "Customer" else None) -%}
				{%- set cust_logo = frappe.db.get_value("Customer", _cust, "azzir_customer_logo") if _cust else None -%}
				{#- Branch = the cost center, shown by name (not the raw cost-center id).
				    Try the doc, then the first item, then its warehouse, then the
				    creator's assigned cost center (their branch). -#}
				{%- set _cc = doc.get("cost_center") -%}
				{%- if not _cc and doc.get("items") and doc.get("items")[0].get("cost_center") -%}{%- set _cc = doc.get("items")[0].get("cost_center") -%}{%- endif -%}
				{%- if not _cc and doc.get("items") and doc.get("items")[0].get("warehouse") -%}{%- set _cc = frappe.db.get_value("Warehouse", doc.get("items")[0].get("warehouse"), "azzir_cost_center") -%}{%- endif -%}
				{%- if not _cc -%}{%- set _ucc = frappe.get_all("User Permission", filters={"user": doc.owner, "allow": "Cost Center"}, pluck="for_value") -%}{%- if _ucc -%}{%- set _cc = _ucc[0] -%}{%- endif -%}{%- endif -%}
				{%- set _branch = frappe.db.get_value("Cost Center", _cc, "cost_center_name") if _cc else None -%}
				{% if _branch and doc.doctype == "Sales Invoice" %}<div style="font-size:18px; font-weight:bold; margin-bottom:5px;">Branch: {{ _branch }}</div>{% endif %}
				<b>__PARTY_LABEL__:</b> __PARTY_VALUE__
				{% if cust_logo %}<img src="{{ cust_logo }}" style="height:34px; vertical-align:middle; margin-left:8px;">{% endif %}
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
				{% if doc.doctype == "Delivery Note" %}<th style="padding:5px; text-align:left;">Warehouse</th>{% endif %}
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
					{% if row.get("azzir_item_remark") %}<br><span style="color:#777; font-size:11px;">{{ row.azzir_item_remark }}</span>{% endif %}
					{% if row.get("azzir_item_image") %}<br><img src="{{ row.azzir_item_image }}" style="max-height:60px; margin-top:3px;">{% endif %}
				</td>
				{% if doc.doctype == "Delivery Note" %}<td style="padding:5px;">{{ row.warehouse or "" }}</td>{% endif %}
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

	<!-- Optional image placed directly on the Quotation -->
	{% if doc.get("azzir_quotation_image") %}
	<div style="margin-top:12px; text-align:center;">
		<img src="{{ doc.azzir_quotation_image }}" style="max-width:60%; max-height:260px;">
	</div>
	{% endif %}

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
					{% if doc.get("azzir_remarks") %}<tr><td colspan="2" style="padding-top:15px;"><b>Remarks:</b> {{ doc.azzir_remarks }}</td></tr>{% endif %}
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
						<td style="text-align:right; padding:4px;"><b>GRAND TOTAL :</b></td>
						<td style="text-align:right; padding:4px;"><b>{{ "{:,.2f}".format(frappe.utils.flt(doc.grand_total)) }}</b></td>
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

	{% if show_prices and doc.get("in_words") %}<p style="margin-top:10px;"><b>In Words:</b> {{ doc.in_words.replace(doc.currency, "").replace("  ", " ").strip() }}</p>{% endif %}
</div>
"""


# --------------------------------------------------------------------------- #
# Role workspaces (Sales / Procurement / HR / Accounting / Director)
# Each: number-card tiles + shortcut tiles + grouped sidebar links, following
# the real flow. Robust — any link/report/doctype not present on a site is
# skipped, and empty cards are dropped. Created only if missing (delete a
# workspace to regenerate it).
# --------------------------------------------------------------------------- #
def _target_exists(link_type, link_to):
	if link_type == "DocType":
		return bool(frappe.db.exists("DocType", link_to))
	if link_type == "Report":
		return bool(frappe.db.exists("Report", link_to))
	if link_type == "Page":
		return bool(frappe.db.exists("Page", link_to))
	return True


def _ensure_number_card(nc):
	existing = frappe.db.get_value("Number Card", {"label": nc["label"]}, "name")
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Number Card",
			"label": nc["label"],
			"document_type": nc["document_type"],
			"function": nc.get("function", "Count"),
			"is_public": 1,
			"show_percentage_stats": 0,
			"filters_json": nc.get("filters_json", "[]"),
			"color": nc.get("color", "#5E64FF"),
		}
	).insert(ignore_permissions=True)
	return doc.name


def _ensure_sidebar_homes():
	"""Give each role Workspace Sidebar a 'Home' item that opens its Workspace, so
	clicking the desktop icon lands on a dashboard. Points at the workspace created
	by _setup_workspaces, or an existing ERPNext/HRMS one of the same name.
	Idempotent; runs after the workspaces exist (order matters for the dynamic link)."""
	pairs = [
		("Sales", "Sales"), ("Procurement", "Procurement"), ("HR", "HR"),
		("Accounting", "Accounting"), ("Director", "Director"),
	]
	for sidebar_name, ws in pairs:
		if not frappe.db.exists("Workspace Sidebar", sidebar_name):
			continue
		if not frappe.db.exists("Workspace", ws):
			continue
		doc = frappe.get_doc("Workspace Sidebar", sidebar_name)
		if any(it.get("link_type") == "Workspace" and it.get("link_to") == ws for it in doc.items):
			continue
		items = [it.as_dict() for it in doc.items]
		items.insert(
			0,
			{"type": "Link", "label": "Home", "link_type": "Workspace", "link_to": ws, "icon": "home"},
		)
		doc.set("items", items)
		# Don't re-export the standard fixture to disk while saving.
		prev = frappe.flags.in_import
		frappe.flags.in_import = True
		try:
			doc.save(ignore_permissions=True)
		finally:
			frappe.flags.in_import = prev


def _make_workspace(spec):
	label = spec["label"]
	if frappe.db.exists("Workspace", label):
		return

	def bid():
		return frappe.generate_hash(length=10)

	ws = frappe.new_doc("Workspace")
	ws.title = label
	ws.label = label
	ws.name = label
	ws.icon = spec.get("icon", "dashboard")
	ws.module = "Azzir Fleet"
	ws.public = 1
	ws.sequence_id = spec.get("sequence", 50)

	for role in spec.get("roles", []):
		if frappe.db.exists("Role", role):
			ws.append("roles", {"role": role})

	content = [{"id": bid(), "type": "header",
	            "data": {"text": '<span class="h4"><b>%s</b></span>' % spec["title"], "col": 12}}]

	# number-card tiles
	for nc in spec.get("number_cards", []):
		if not frappe.db.exists("DocType", nc["document_type"]):
			continue
		name = _ensure_number_card(nc)
		ws.append("number_cards", {"number_card_name": name, "label": nc["label"]})
		content.append({"id": bid(), "type": "number_card",
		                "data": {"number_card_name": name, "col": 4}})

	# shortcut tiles
	scs = [s for s in spec.get("shortcuts", []) if _target_exists(s.get("type", "DocType"), s["link_to"])]
	if scs:
		content.append({"id": bid(), "type": "header",
		                "data": {"text": '<span class="h5"><b>Shortcuts</b></span>', "col": 12}})
		for s in scs:
			ws.append("shortcuts", {"type": s.get("type", "DocType"), "link_to": s["link_to"],
			                        "label": s["label"], "color": s.get("color", "Grey"),
			                        "doc_view": s.get("doc_view", "")})
			content.append({"id": bid(), "type": "shortcut",
			                "data": {"shortcut_name": s["label"], "col": 3}})

	# grouped sidebar link cards
	valid = []
	for card in spec.get("cards", []):
		links = [l for l in card["links"] if _target_exists(l.get("link_type", "DocType"), l["link_to"])]
		if links:
			valid.append((card["title"], links))
	if valid:
		content.append({"id": bid(), "type": "header",
		                "data": {"text": '<span class="h5"><b>Explore</b></span>', "col": 12}})
		for title, links in valid:
			ws.append("links", {"type": "Card Break", "label": title, "link_count": len(links),
			                    "hidden": 0, "onboard": 0})
			for l in links:
				ws.append("links", {"type": "Link", "label": l["label"],
				                    "link_type": l.get("link_type", "DocType"), "link_to": l["link_to"],
				                    "hidden": 0, "onboard": 0,
				                    "is_query_report": 1 if l.get("link_type") == "Report" else 0})
			content.append({"id": bid(), "type": "card", "data": {"card_name": title, "col": 4}})

	ws.content = frappe.as_json(content)
	ws.insert(ignore_permissions=True)


def _setup_workspaces():
	specs = [
		{
			"label": "Sales", "title": "Sales", "icon": "sell", "sequence": 51,
			"roles": ["Sales User", "Sales Manager"],
			"number_cards": [
				{"label": "Open Quotations", "document_type": "Quotation",
				 "filters_json": '[["Quotation","status","=","Open"]]', "color": "#5E64FF"},
				{"label": "Unpaid Sales Invoices", "document_type": "Sales Invoice",
				 "filters_json": '[["Sales Invoice","status","=","Unpaid"]]', "color": "#FF5858"},
				{"label": "Draft Sales Invoices", "document_type": "Sales Invoice",
				 "filters_json": '[["Sales Invoice","docstatus","=",0]]', "color": "#FFB868"},
			],
			"shortcuts": [
				{"label": "Quotation", "link_to": "Quotation", "color": "Blue"},
				{"label": "Sales Invoice", "link_to": "Sales Invoice", "color": "Green"},
				{"label": "Delivery Note", "link_to": "Delivery Note", "color": "Orange"},
				{"label": "Customer", "link_to": "Customer", "color": "Grey"},
			],
			"cards": [
				{"title": "Sales Flow", "links": [
					{"label": "Quotation", "link_to": "Quotation"},
					{"label": "Sales Order", "link_to": "Sales Order"},
					{"label": "Sales Invoice", "link_to": "Sales Invoice"},
					{"label": "Delivery Note", "link_to": "Delivery Note"},
				]},
				{"title": "Masters", "links": [
					{"label": "Customer", "link_to": "Customer"},
					{"label": "Item", "link_to": "Item"},
					{"label": "Price List", "link_to": "Price List"},
				]},
				{"title": "Reports", "links": [
					{"label": "Commission Report", "link_type": "Report", "link_to": "Commission Report"},
					{"label": "Sales Register", "link_type": "Report", "link_to": "Sales Register"},
					{"label": "Customer Statement", "link_type": "Page", "link_to": "customer-statement"},
				]},
			],
		},
		{
			"label": "Procurement", "title": "Procurement", "icon": "buying", "sequence": 52,
			"roles": ["Purchase User", "Purchase Manager"],
			"number_cards": [
				{"label": "Open Material Requests", "document_type": "Material Request",
				 "filters_json": '[["Material Request","status","=","Pending"]]', "color": "#5E64FF"},
				{"label": "Draft Purchase Orders", "document_type": "Purchase Order",
				 "filters_json": '[["Purchase Order","docstatus","=",0]]', "color": "#FFB868"},
				{"label": "Unpaid Purchase Invoices", "document_type": "Purchase Invoice",
				 "filters_json": '[["Purchase Invoice","status","=","Unpaid"]]', "color": "#FF5858"},
			],
			"shortcuts": [
				{"label": "Material Request", "link_to": "Material Request", "color": "Blue"},
				{"label": "Purchase Order", "link_to": "Purchase Order", "color": "Green"},
				{"label": "Purchase Receipt", "link_to": "Purchase Receipt", "color": "Orange"},
				{"label": "Supplier", "link_to": "Supplier", "color": "Grey"},
			],
			"cards": [
				{"title": "Buying Flow", "links": [
					{"label": "Material Request", "link_to": "Material Request"},
					{"label": "Supplier Quotation", "link_to": "Supplier Quotation"},
					{"label": "Purchase Order", "link_to": "Purchase Order"},
					{"label": "Purchase Receipt", "link_to": "Purchase Receipt"},
					{"label": "Purchase Invoice", "link_to": "Purchase Invoice"},
				]},
				{"title": "Masters", "links": [
					{"label": "Supplier", "link_to": "Supplier"},
					{"label": "Item", "link_to": "Item"},
				]},
				{"title": "Reports", "links": [
					{"label": "Purchase Register", "link_type": "Report", "link_to": "Purchase Register"},
					{"label": "Purchase Order Analysis", "link_type": "Report", "link_to": "Purchase Order Analysis"},
				]},
			],
		},
		{
			"label": "HR", "title": "Human Resources", "icon": "hr", "sequence": 53,
			"roles": ["HR User", "HR Manager"],
			"number_cards": [
				{"label": "Active Employees", "document_type": "Employee",
				 "filters_json": '[["Employee","status","=","Active"]]', "color": "#29CD42"},
				{"label": "Open Leave Applications", "document_type": "Leave Application",
				 "filters_json": '[["Leave Application","status","=","Open"]]', "color": "#FFB868"},
				{"label": "Draft Salary Slips", "document_type": "Salary Slip",
				 "filters_json": '[["Salary Slip","docstatus","=",0]]', "color": "#5E64FF"},
			],
			"shortcuts": [
				{"label": "Employee", "link_to": "Employee", "color": "Blue"},
				{"label": "Attendance", "link_to": "Attendance", "color": "Green"},
				{"label": "Leave Application", "link_to": "Leave Application", "color": "Orange"},
				{"label": "Salary Slip", "link_to": "Salary Slip", "color": "Purple"},
			],
			"cards": [
				{"title": "People", "links": [
					{"label": "Employee", "link_to": "Employee"},
					{"label": "Department", "link_to": "Department"},
					{"label": "Designation", "link_to": "Designation"},
				]},
				{"title": "Leave & Attendance", "links": [
					{"label": "Attendance", "link_to": "Attendance"},
					{"label": "Leave Application", "link_to": "Leave Application"},
					{"label": "Holiday List", "link_to": "Holiday List"},
				]},
				{"title": "Payroll", "links": [
					{"label": "Salary Slip", "link_to": "Salary Slip"},
					{"label": "Payroll Entry", "link_to": "Payroll Entry"},
					{"label": "Payroll Component Summary", "link_type": "Report", "link_to": "Payroll Component Summary"},
				]},
			],
		},
		{
			"label": "Accounting", "title": "Accounting", "icon": "accounting", "sequence": 54,
			"roles": ["Accounts User", "Accounts Manager"],
			"number_cards": [
				{"label": "Unpaid Sales Invoices", "document_type": "Sales Invoice",
				 "filters_json": '[["Sales Invoice","status","=","Unpaid"]]', "color": "#FF5858"},
				{"label": "Unpaid Purchase Invoices", "document_type": "Purchase Invoice",
				 "filters_json": '[["Purchase Invoice","status","=","Unpaid"]]', "color": "#FFB868"},
				{"label": "Draft Journal Entries", "document_type": "Journal Entry",
				 "filters_json": '[["Journal Entry","docstatus","=",0]]', "color": "#5E64FF"},
			],
			"shortcuts": [
				{"label": "Payment Entry", "link_to": "Payment Entry", "color": "Green"},
				{"label": "Journal Entry", "link_to": "Journal Entry", "color": "Blue"},
				{"label": "Expense Entry", "link_to": "Expense Entry", "color": "Orange"},
				{"label": "Monthly Budget", "link_to": "Monthly Budget", "color": "Purple"},
			],
			"cards": [
				{"title": "Transactions", "links": [
					{"label": "Payment Entry", "link_to": "Payment Entry"},
					{"label": "Journal Entry", "link_to": "Journal Entry"},
					{"label": "Expense Entry", "link_to": "Expense Entry"},
					{"label": "Sales Invoice", "link_to": "Sales Invoice"},
					{"label": "Purchase Invoice", "link_to": "Purchase Invoice"},
				]},
				{"title": "Budget", "links": [
					{"label": "Monthly Budget", "link_to": "Monthly Budget"},
					{"label": "Monthly Budget Report", "link_type": "Report", "link_to": "Monthly Budget Report"},
					{"label": "Monthly Budget Comparison Report", "link_type": "Report", "link_to": "Monthly Budget Comparison Report"},
				]},
				{"title": "Financial Reports", "links": [
					{"label": "General Ledger", "link_type": "Report", "link_to": "General Ledger"},
					{"label": "Accounts Receivable", "link_type": "Report", "link_to": "Accounts Receivable"},
					{"label": "Accounts Payable", "link_type": "Report", "link_to": "Accounts Payable"},
					{"label": "Profit and Loss Statement", "link_type": "Report", "link_to": "Profit and Loss Statement"},
					{"label": "Balance Sheet", "link_type": "Report", "link_to": "Balance Sheet"},
				]},
			],
		},
		{
			"label": "Director", "title": "Director's Overview", "icon": "dashboard", "sequence": 50,
			"roles": [],
			"number_cards": [
				{"label": "Unpaid Sales Invoices", "document_type": "Sales Invoice",
				 "filters_json": '[["Sales Invoice","status","=","Unpaid"]]', "color": "#FF5858"},
				{"label": "Draft Purchase Orders", "document_type": "Purchase Order",
				 "filters_json": '[["Purchase Order","docstatus","=",0]]', "color": "#FFB868"},
				{"label": "Active Employees", "document_type": "Employee",
				 "filters_json": '[["Employee","status","=","Active"]]', "color": "#29CD42"},
			],
			"shortcuts": [
				{"label": "Profit and Loss Statement", "type": "Report", "link_to": "Profit and Loss Statement", "color": "Green"},
				{"label": "Monthly Budget Comparison Report", "type": "Report", "link_to": "Monthly Budget Comparison Report", "color": "Blue"},
				{"label": "Commission Report", "type": "Report", "link_to": "Commission Report", "color": "Purple"},
				{"label": "Accounts Receivable", "type": "Report", "link_to": "Accounts Receivable", "color": "Orange"},
			],
			"cards": [
				{"title": "Performance", "links": [
					{"label": "Commission Report", "link_type": "Report", "link_to": "Commission Report"},
					{"label": "Monthly Budget Comparison Report", "link_type": "Report", "link_to": "Monthly Budget Comparison Report"},
					{"label": "Sales Register", "link_type": "Report", "link_to": "Sales Register"},
				]},
				{"title": "Financials", "links": [
					{"label": "Profit and Loss Statement", "link_type": "Report", "link_to": "Profit and Loss Statement"},
					{"label": "Balance Sheet", "link_type": "Report", "link_to": "Balance Sheet"},
					{"label": "Accounts Receivable", "link_type": "Report", "link_to": "Accounts Receivable"},
					{"label": "Accounts Payable", "link_type": "Report", "link_to": "Accounts Payable"},
				]},
				{"title": "Operations", "links": [
					{"label": "Sales Invoice", "link_to": "Sales Invoice"},
					{"label": "Purchase Invoice", "link_to": "Purchase Invoice"},
					{"label": "Delivery Note", "link_to": "Delivery Note"},
					{"label": "Stock Balance", "link_type": "Report", "link_to": "Stock Balance"},
				]},
			],
		},
	]
	for spec in specs:
		try:
			_make_workspace(spec)
		except Exception:
			frappe.log_error(title="azzir_fleet workspace failed: %s" % spec.get("label"))


# --------------------------------------------------------------------------- #
# Standalone sidebars (each = its own desktop icon + its own independent menu),
# the same primitive petrol_station's "Fuel Station" uses (Workspace Sidebar).
# Five separate icons: Sales, Procurement, HR, Accounting, Director.
# --------------------------------------------------------------------------- #
def _make_sidebar(title, icon, items):
	if not frappe.db.exists("DocType", "Workspace Sidebar"):
		return
	if frappe.db.exists("Workspace Sidebar", title):
		return
	doc = frappe.new_doc("Workspace Sidebar")
	doc.title = title
	doc.header_icon = icon
	doc.app = "azzir_fleet"
	doc.module = "Azzir Fleet"
	doc.standard = 0
	has_link = False
	for it in items:
		if it.get("type") == "Section Break":
			doc.append("items", {"type": "Section Break", "label": it["label"]})
			continue
		lt = it.get("link_type", "DocType")
		if not _target_exists(lt, it["link_to"]):
			continue
		doc.append("items", {
			"type": "Link", "label": it["label"], "link_type": lt,
			"link_to": it["link_to"], "icon": it.get("icon", ""),
		})
		has_link = True
	if not has_link:
		return
	doc.insert(ignore_permissions=True)


def _setup_sidebars():
	specs = [
		{"title": "Sales", "icon": "sell", "items": [
			{"type": "Section Break", "label": "Sales"},
			{"label": "Quotation", "link_to": "Quotation", "icon": "file-text"},
			{"label": "Sales Order", "link_to": "Sales Order", "icon": "clipboard-list"},
			{"label": "Sales Invoice", "link_to": "Sales Invoice", "icon": "receipt-text"},
			{"label": "Delivery Note", "link_to": "Delivery Note", "icon": "truck"},
			{"label": "Customer", "link_to": "Customer", "icon": "users"},
			{"label": "Item", "link_to": "Item", "icon": "package"},
			{"type": "Section Break", "label": "Reports"},
			{"label": "Commission Report", "link_type": "Report", "link_to": "Commission Report", "icon": "notebook-text"},
			{"label": "Sales Register", "link_type": "Report", "link_to": "Sales Register", "icon": "notebook-text"},
			{"label": "Customer Statement", "link_type": "Page", "link_to": "customer-statement", "icon": "sheet"},
		]},
		{"title": "Procurement", "icon": "buying", "items": [
			{"type": "Section Break", "label": "Buying"},
			{"label": "Material Request", "link_to": "Material Request", "icon": "clipboard-list"},
			{"label": "Supplier Quotation", "link_to": "Supplier Quotation", "icon": "file-text"},
			{"label": "Purchase Order", "link_to": "Purchase Order", "icon": "shopping-cart"},
			{"label": "Purchase Receipt", "link_to": "Purchase Receipt", "icon": "truck"},
			{"label": "Purchase Invoice", "link_to": "Purchase Invoice", "icon": "receipt-text"},
			{"label": "Supplier", "link_to": "Supplier", "icon": "users"},
			{"type": "Section Break", "label": "Reports"},
			{"label": "Purchase Register", "link_type": "Report", "link_to": "Purchase Register", "icon": "notebook-text"},
			{"label": "Purchase Order Analysis", "link_type": "Report", "link_to": "Purchase Order Analysis", "icon": "notebook-text"},
		]},
		{"title": "HR", "icon": "hr", "items": [
			{"type": "Section Break", "label": "People"},
			{"label": "Employee", "link_to": "Employee", "icon": "user-round"},
			{"label": "Attendance", "link_to": "Attendance", "icon": "calendar-check"},
			{"label": "Leave Application", "link_to": "Leave Application", "icon": "plane"},
			{"type": "Section Break", "label": "Payroll"},
			{"label": "Salary Slip", "link_to": "Salary Slip", "icon": "receipt-text"},
			{"label": "Payroll Entry", "link_to": "Payroll Entry", "icon": "accounting"},
			{"label": "Payroll Component Summary", "link_type": "Report", "link_to": "Payroll Component Summary", "icon": "notebook-text"},
		]},
		{"title": "Accounting", "icon": "accounting", "items": [
			{"type": "Section Break", "label": "Transactions"},
			{"label": "Payment Entry", "link_to": "Payment Entry", "icon": "circle-dollar-sign"},
			{"label": "Journal Entry", "link_to": "Journal Entry", "icon": "book"},
			{"label": "Expense Entry", "link_to": "Expense Entry", "icon": "expenses"},
			{"label": "Sales Invoice", "link_to": "Sales Invoice", "icon": "receipt-text"},
			{"label": "Purchase Invoice", "link_to": "Purchase Invoice", "icon": "receipt-text"},
			{"label": "Monthly Budget", "link_to": "Monthly Budget", "icon": "accounting"},
			{"type": "Section Break", "label": "Financial Reports"},
			{"label": "General Ledger", "link_type": "Report", "link_to": "General Ledger", "icon": "sheet"},
			{"label": "Accounts Receivable", "link_type": "Report", "link_to": "Accounts Receivable", "icon": "sheet"},
			{"label": "Accounts Payable", "link_type": "Report", "link_to": "Accounts Payable", "icon": "sheet"},
			{"label": "Profit and Loss Statement", "link_type": "Report", "link_to": "Profit and Loss Statement", "icon": "sheet"},
			{"label": "Balance Sheet", "link_type": "Report", "link_to": "Balance Sheet", "icon": "sheet"},
			{"label": "Monthly Budget Report", "link_type": "Report", "link_to": "Monthly Budget Report", "icon": "notebook-text"},
			{"label": "Monthly Budget Comparison Report", "link_type": "Report", "link_to": "Monthly Budget Comparison Report", "icon": "notebook-text"},
		]},
		{"title": "Director", "icon": "star", "items": [
			{"type": "Section Break", "label": "Performance"},
			{"label": "Commission Report", "link_type": "Report", "link_to": "Commission Report", "icon": "notebook-text"},
			{"label": "Monthly Budget Comparison Report", "link_type": "Report", "link_to": "Monthly Budget Comparison Report", "icon": "notebook-text"},
			{"label": "Sales Register", "link_type": "Report", "link_to": "Sales Register", "icon": "notebook-text"},
			{"type": "Section Break", "label": "Financials"},
			{"label": "Profit and Loss Statement", "link_type": "Report", "link_to": "Profit and Loss Statement", "icon": "sheet"},
			{"label": "Balance Sheet", "link_type": "Report", "link_to": "Balance Sheet", "icon": "sheet"},
			{"label": "Accounts Receivable", "link_type": "Report", "link_to": "Accounts Receivable", "icon": "sheet"},
			{"type": "Section Break", "label": "Operations"},
			{"label": "Sales Invoice", "link_to": "Sales Invoice", "icon": "receipt-text"},
			{"label": "Purchase Invoice", "link_to": "Purchase Invoice", "icon": "receipt-text"},
			{"label": "Stock Balance", "link_type": "Report", "link_to": "Stock Balance", "icon": "stock"},
		]},
	]
	for s in specs:
		try:
			_make_sidebar(s["title"], s["icon"], s["items"])
		except Exception:
			frappe.log_error(title="azzir_fleet sidebar failed: %s" % s["title"])
