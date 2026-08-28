// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt

frappe.query_reports["Reorder Level Report"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			description: __("Optional — one warehouse only."),
		},
		{
			fieldname: "reordered_within_days",
			label: __("Reordered Within (Days)"),
			fieldtype: "Int",
			default: 30,
			description: __(
				"Hide items that already have a Purchase Invoice raised in the last N days. 0 = hide if any open Purchase Invoice exists at all."
			),
		},
		{
			fieldname: "show_reordered",
			label: __("Show Already-Reordered Items"),
			fieldtype: "Check",
			default: 0,
			description: __("Tick to also list items that already have a Purchase Invoice."),
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && column.fieldname === "shortage" && flt(data.shortage) > 0) {
			value = `<span style="color:var(--red-600,#b00);font-weight:600;">${value}</span>`;
		}
		return value;
	},
};
