// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt

frappe.query_reports["Customer Balances Report"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
			description: __("Optional — one customer only."),
		},
		{
			fieldname: "show_zero",
			label: __("Show Zero Balances"),
			fieldtype: "Check",
			default: 0,
			description: __("Include customers with nothing outstanding."),
		},
	],
};
