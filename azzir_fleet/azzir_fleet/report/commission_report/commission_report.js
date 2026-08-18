// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt

frappe.query_reports["Commission Report"] = {
	filters: [
		{
			fieldname: "commission_plan",
			label: __("Commission Plan"),
			fieldtype: "Link",
			options: "Commission Plan",
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			description: __("Leave blank to use the plan's period."),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			description: __("Leave blank to use the plan's period."),
		},
		{
			fieldname: "sales_person",
			label: __("Sales Person"),
			fieldtype: "Link",
			options: "Sales Person",
			description: __("Optional — filter to one person."),
		},
	],
};
