// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt

frappe.query_reports["Monthly Budget Comparison Report"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Int",
			default: new Date().getFullYear(),
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.status === __("Over Budget") && column.fieldname === "status") {
			value = `<span style="color:var(--red-600,#b00);font-weight:600;">${value}</span>`;
		}
		return value;
	},
};
