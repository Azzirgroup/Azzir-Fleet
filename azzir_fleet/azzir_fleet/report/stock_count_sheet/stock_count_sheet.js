// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt

frappe.query_reports["Stock Count Sheet"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "warehouse", label: __("Warehouse"), fieldtype: "Link", options: "Warehouse" },
		{ fieldname: "item_group", label: __("Item Group"), fieldtype: "Link", options: "Item Group" },
		{
			fieldname: "include_zero",
			label: __("Include Zero Balance"),
			fieldtype: "Check",
			default: 0,
			description: __("Also list items whose system balance is 0."),
		},
	],
};
