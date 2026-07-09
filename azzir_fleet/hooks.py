app_name = "azzir_fleet"
app_title = "Azzir Fleet"
app_publisher = "Azzir"
app_description = "Item code change tool with alias-aware search"
app_email = "azzirgrouplimited@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "azzir_fleet",
# 		"logo": "/assets/azzir_fleet/logo.png",
# 		"title": "Azzir Fleet",
# 		"route": "/azzir_fleet",
# 		"has_permission": "azzir_fleet.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/azzir_fleet/css/azzir_fleet.css"
app_include_js = [
	"/assets/azzir_fleet/js/azzir_alias.js",
	"/assets/azzir_fleet/js/azzir_stock.js",
]

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
		"azzir_fleet.stock_info.get_stock_tree",
		"azzir_fleet.stock_info.get_stock_branch",
	],
}

# Installation
# ------------

# before_install = "azzir_fleet.install.before_install"
after_install = "azzir_fleet.setup.after_install"
after_migrate = "azzir_fleet.setup.after_migrate"

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

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Item": {
		"validate": "azzir_fleet.item_codes.validate",
		"on_update": "azzir_fleet.item_codes.on_update",
		"after_rename": "azzir_fleet.item_codes.after_rename",
	},
	# Maximum Order Qty — buying documents
	"Material Request": {"validate": "azzir_fleet.qty_limits.validate_buying"},
	"Purchase Order": {"validate": "azzir_fleet.qty_limits.validate_buying"},
	"Purchase Receipt": {"validate": "azzir_fleet.qty_limits.validate_buying"},
	"Purchase Invoice": {"validate": "azzir_fleet.qty_limits.validate_buying"},
	# Maximum Sales Qty — selling documents
	"Quotation": {
		"before_validate": "azzir_fleet.vat.apply_vat_option",
		"validate": [
			"azzir_fleet.qty_limits.validate_selling",
			"azzir_fleet.quotation.set_quotation_validity",
		],
	},
	"Supplier Quotation": {
		"validate": [
			"azzir_fleet.qty_limits.validate_buying",
			"azzir_fleet.quotation.set_quotation_validity",
		]
	},
	"Sales Order": {
		"before_validate": "azzir_fleet.vat.apply_vat_option",
		"validate": "azzir_fleet.qty_limits.validate_selling",
	},
	"Delivery Note": {
		"before_validate": "azzir_fleet.vat.apply_vat_option",
		"validate": "azzir_fleet.qty_limits.validate_selling",
	},
	"Sales Invoice": {
		"before_validate": "azzir_fleet.vat.apply_vat_option",
		"validate": [
			"azzir_fleet.qty_limits.validate_selling",
			"azzir_fleet.qty_limits.validate_sales_stock",
		],
	},
	"POS Invoice": {"validate": "azzir_fleet.qty_limits.validate_selling"},
	# Monthly Budget control (Warn/Stop). JE covers Expense Entry too.
	"Journal Entry": {
		"validate": "azzir_fleet.azzir_fleet.doctype.monthly_budget.monthly_budget.check_journal_entry_budget"
	},
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

