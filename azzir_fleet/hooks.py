app_name = "azzir_fleet"
app_title = "Azzir Fleet"
app_publisher = "Azzir"
app_description = "Item code change tool with alias-aware search"
app_email = "azzirgrouplimited@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page / app switcher.
# This is what makes the Azzir Fleet workspaces (Sales, Procurement, HR,
# Accounting, Director) appear in the desk sidebar.
# The Azzir Sales frappe-ui frontend (/sales), shown as its own app with a logo
# on the apps screen / desktop.
add_to_apps_screen = [
	{
		"name": "azzir_fleet",
		"logo": "/assets/azzir_fleet/frontend/logo.svg",
		"title": "Azzir Sales",
		"route": "/sales",
		"has_permission": "azzir_fleet.sales_api.has_app_permission",
	}
]

# Every path under /sales renders the SPA shell; the Vue router takes over.
website_route_rules = [
	{"from_route": "/sales/<path:app_path>", "to_route": "sales"},
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/azzir_fleet/css/azzir_fleet.css"
# One content-hashed bundle (see public/js/azzir_fleet.bundle.js) so the desk
# scripts cache-bust on every build instead of going stale per device.
app_include_js = ["azzir_fleet.bundle.js"]

# include js, css files in header of web template
# web_include_css = "/assets/azzir_fleet/css/azzir_fleet.css"
# web_include_js = "/assets/azzir_fleet/js/azzir_fleet.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "azzir_fleet/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Item": "public/js/item_codes.js",
	"Quotation": "public/js/quotation.js",
	"Sales Invoice": "public/js/sales_invoice.js",
	"Stock Entry": "public/js/stock_entry.js",
	"Delivery Note": "public/js/delivery_note.js",
	"Purchase Receipt": "public/js/purchase_receipt.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "azzir_fleet/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": [
		"azzir_fleet.alias.get_item_old_codes",
		"azzir_fleet.alias.get_item_previous_code",
		"azzir_fleet.alias.description_for_print",
		"azzir_fleet.stock_info.get_stock_tree",
		"azzir_fleet.stock_info.get_stock_branch",
	],
}

# Session
# ----------
# Cap concurrent logins per user (phone + desktop). Must NOT use System Settings
# .deny_multiple_sessions — that force-clears ALL other sessions.
on_session_creation = [
	"azzir_fleet.session.enforce_session_limit",
	# Route 'Sales Portal' users to /sales on login; others go to the desk.
	"azzir_fleet.session.route_portal_users_on_login",
]

# Installation
# ------------

# before_install = "azzir_fleet.install.before_install"
after_install = "azzir_fleet.setup.after_install"
after_migrate = "azzir_fleet.setup.after_migrate"

# Declarative desk sidebars (one desktop icon + own menu each): Sales,
# Procurement, HR, Accounting, Director. Shipped as JSON fixtures so they deploy
# reliably (imported on every migrate) instead of being created by runtime code.
fixtures = [
	{
		# Role home dashboards, shipped as data (JSON) — synced BEFORE the sidebars
		# so the sidebar 'Home' links resolve. Only names that don't clash with
		# ERPNext/HRMS defaults (Accounting/HR reuse those existing workspaces).
		"dt": "Workspace",
		"filters": [["name", "in", ["Sales", "Procurement", "Director"]]],
	},
	{
		# "Azzir Fleet" is a hidden suppressor (only a section break, so it doesn't
		# render) — it stops Frappe from auto-generating a cluttered module sidebar,
		# leaving ONLY the 5 icons. Each role sidebar carries a 'Home' link to its
		# workspace.
		"dt": "Workspace Sidebar",
		"filters": [["name", "in", ["Sales", "Procurement", "HR", "Accounting", "Director", "Azzir Fleet"]]],
	},
]

# Uninstallation
# ------------

# before_uninstall = "azzir_fleet.uninstall.before_uninstall"
# after_uninstall = "azzir_fleet.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "azzir_fleet.utils.before_app_install"
# after_app_install = "azzir_fleet.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "azzir_fleet.utils.before_app_uninstall"
# after_app_uninstall = "azzir_fleet.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "azzir_fleet.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# Procurement users see only the documents they created; the 'Azzir Procurement
# Overseer' role (or Purchase Manager / System Manager) sees all.
permission_query_conditions = {
	dt: "azzir_fleet.procurement.get_permission_query_conditions"
	for dt in (
		"Material Request",
		"Request for Quotation",
		"Supplier Quotation",
		"Purchase Order",
		"Purchase Receipt",
		"Purchase Invoice",
	)
}
# Sales people see only the quotations / invoices / delivery notes they created;
# the 'Azzir Sales Overseer' role (or Sales Manager / System Manager) sees all.
permission_query_conditions.update(
	{
		dt: "azzir_fleet.sales_api.get_permission_query_conditions"
		for dt in ("Quotation", "Sales Invoice", "Delivery Note")
	}
)

has_permission = {
	dt: "azzir_fleet.procurement.has_permission"
	for dt in (
		"Material Request",
		"Request for Quotation",
		"Supplier Quotation",
		"Purchase Order",
		"Purchase Receipt",
		"Purchase Invoice",
	)
}
has_permission.update(
	{
		dt: "azzir_fleet.sales_api.has_permission"
		for dt in ("Quotation", "Sales Invoice", "Delivery Note")
	}
)

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Item": {
		"validate": "azzir_fleet.item_codes.validate",
		"on_update": "azzir_fleet.item_codes.on_update",
		"after_rename": "azzir_fleet.item_codes.after_rename",
	},
	# A user's Company field (azzir_company) becomes their default company, so new
	# Quotations / Sales Invoices auto-fill it (desk + /sales portal).
	"User": {
		"on_update": "azzir_fleet.company_default.sync_user_company",
	},
	# Mirror the Employee 'Cost Centers' table into User Permissions so the
	# linked user only sees data for their cost center(s); none = sees all.
	"Employee": {
		"on_update": "azzir_fleet.employee_permissions.sync_cost_center_permissions",
		"on_trash": "azzir_fleet.employee_permissions.clear_cost_center_permissions",
	},
	# Maker-checker: the creator of a Stock Entry draft cannot submit it.
	"Stock Entry": {
		"before_submit": [
			"azzir_fleet.stock_entry_approval.block_self_submit",
			"azzir_fleet.stock_entry_approval.block_transit_self_receive",
		]
	},
	# Maximum Order Qty — buying documents
	"Material Request": {"validate": "azzir_fleet.qty_limits.validate_buying"},
	"Purchase Order": {"validate": "azzir_fleet.qty_limits.validate_buying"},
	"Purchase Invoice": {
		"before_validate": "azzir_fleet.intercompany.apply_intercompany_discount",
		"validate": [
			"azzir_fleet.qty_limits.validate_buying",
			"azzir_fleet.purchase_invoice.validate_unique_bill_no",
		],
	},
	"Purchase Receipt": {
		"before_validate": "azzir_fleet.intercompany.apply_intercompany_discount",
		"validate": "azzir_fleet.qty_limits.validate_buying",
	},
	# Maximum Sales Qty — selling documents.
	# apply_vat_option runs LAST on validate (after ERPNext re-applies default taxes).
	"Quotation": {
		"before_validate": "azzir_fleet.customer_name.capture_override",
		"validate": [
			"azzir_fleet.warehouse.require_warehouse_for_stock",
			"azzir_fleet.qty_limits.validate_selling",
			"azzir_fleet.quotation.set_quotation_validity",
			"azzir_fleet.vat.apply_vat_option",
			"azzir_fleet.below_cost.flag_below_cost",
			"azzir_fleet.below_cost.set_previous_price",
			"azzir_fleet.customer_name.restore_override",
		],
	},
	"Supplier Quotation": {
		"validate": [
			"azzir_fleet.qty_limits.validate_buying",
			"azzir_fleet.quotation.set_quotation_validity",
		]
	},
	"Sales Order": {
		"validate": [
			"azzir_fleet.qty_limits.validate_selling",
			"azzir_fleet.vat.apply_vat_option",
		],
	},
	"Delivery Note": {
		"before_validate": "azzir_fleet.customer_name.capture_override",
		"validate": [
			"azzir_fleet.qty_limits.validate_selling",
			"azzir_fleet.vat.apply_vat_option",
			"azzir_fleet.customer_name.restore_override",
			"azzir_fleet.warehouse.require_warehouse_for_stock",
		],
	},
	"Sales Invoice": {
		"before_validate": "azzir_fleet.customer_name.capture_override",
		"validate": [
			"azzir_fleet.intercompany_sale.set_landing_warehouse",
			"azzir_fleet.warehouse.require_warehouse_for_stock",
			"azzir_fleet.qty_limits.validate_selling",
			"azzir_fleet.qty_limits.validate_sales_stock",
			"azzir_fleet.vat.apply_vat_option",
			"azzir_fleet.below_cost.flag_below_cost",
			"azzir_fleet.below_cost.set_previous_price",
			"azzir_fleet.customer_name.restore_override",
		],
		"before_submit": [
			"azzir_fleet.intercompany_sale.process_sister_purchase",
			"azzir_fleet.stock_reservation.check_stock_reservation",
		],
		"on_submit": "azzir_fleet.sales_invoice.mark_quotation_invoiced",
		"on_cancel": "azzir_fleet.sales_invoice.unmark_quotation_invoiced",
	},
	"POS Invoice": {"validate": "azzir_fleet.qty_limits.validate_selling"},
	# Monthly Budget control (Warn/Stop). JE covers Expense Entry too.
	"Journal Entry": {
		"validate": [
			"azzir_fleet.azzir_fleet.doctype.monthly_budget.monthly_budget.check_journal_entry_budget",
			"azzir_fleet.tax_calc.compute_journal_entry_tax",
		]
	},
	"Expense Entry": {"validate": "azzir_fleet.tax_calc.compute_expense_entry_tax"},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"azzir_fleet.tasks.all"
# 	],
# 	"daily": [
# 		"azzir_fleet.tasks.daily"
# 	],
# 	"hourly": [
# 		"azzir_fleet.tasks.hourly"
# 	],
# 	"weekly": [
# 		"azzir_fleet.tasks.weekly"
# 	],
# 	"monthly": [
# 		"azzir_fleet.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "azzir_fleet.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "azzir_fleet.custom.task.CustomTaskMixin"
# }

# Keep Product Bundle components on the Sales Invoice even when Update Stock is OFF.
override_doctype_class = {
	"Sales Invoice": "azzir_fleet.overrides.AzzirSalesInvoice",
}

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"frappe.desk.search.search_link": "azzir_fleet.alias.search_link",
	"erpnext.selling.page.point_of_sale.point_of_sale.get_items": "azzir_fleet.pos.get_items",
	"frappe.desk.reportview.get": "azzir_fleet.listview.get",
	"frappe.desk.reportview.get_list": "azzir_fleet.listview.get_list",
	"frappe.desk.reportview.get_count": "azzir_fleet.listview.get_count",
	"erpnext.controllers.queries.item_query": "azzir_fleet.alias.item_query",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "azzir_fleet.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["azzir_fleet.utils.before_request"]
# after_request = ["azzir_fleet.utils.after_request"]

# Job Events
# ----------
# before_job = ["azzir_fleet.utils.before_job"]
# after_job = ["azzir_fleet.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"azzir_fleet.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
export_python_type_annotations = True

# Require all whitelisted methods to have type annotations
require_type_annotated_api_methods = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

