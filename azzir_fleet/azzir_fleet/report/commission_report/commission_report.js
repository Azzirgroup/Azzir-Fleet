// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt

frappe.query_reports["Commission Report"] = {
	filters: [
		{
			fieldname: "commission_plan",
			label: __("Commission Plan"),
			fieldtype: "Link",
			options: "Commission Plan",
			description: __("Pick a plan, or filter by Branch below."),
		},
		{
			fieldname: "branch",
			label: __("Branch"),
			fieldtype: "Link",
			options: "Branch",
			description: __("Use instead of a plan to see all plans of a branch."),
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
