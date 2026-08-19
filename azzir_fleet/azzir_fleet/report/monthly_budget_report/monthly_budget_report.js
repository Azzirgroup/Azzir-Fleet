// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt

frappe.query_reports["Monthly Budget Report"] = {
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
		{
			fieldname: "month",
			label: __("Month"),
			fieldtype: "Select",
			options: [
				"",
				"January", "February", "March", "April", "May", "June",
				"July", "August", "September", "October", "November", "December",
			].join("\n"),
			description: __("Leave blank for the whole year; pick one to see e.g. last month."),
		},
		{
			fieldname: "account",
			label: __("Account"),
			fieldtype: "Link",
			options: "Account",
			description: __("Optional — one account only."),
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.status === __("Over Budget")) {
			if (column.fieldname === "status" || column.fieldname === "pct_used") {
				value = `<span style="color:var(--red-600,#b00);font-weight:600;">${value}</span>`;
			}
		}
		return value;
	},
};
