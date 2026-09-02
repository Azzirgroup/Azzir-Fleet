// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt

frappe.query_reports["Reorder Level Report"] = {
	// Grouped as a tree: warehouse (parent) → out-of-band items (children).
	tree: true,
	name_field: "label",
	initial_depth: 1,
	filters: [
		{
			// No default — show every company's warehouses until one is picked.
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			description: __("Optional — one warehouse only."),
		},
		{
			// Alias-aware: type a current OR alternative (old) part number.
			fieldname: "items",
			label: __("Item"),
			fieldtype: "MultiSelectList",
			description: __("Optional — also matches alternative part numbers."),
			get_data(txt) {
				return new Promise((resolve) => {
					frappe.call({
						method: "azzir_fleet.alias.item_search_for_spa",
						args: { txt: txt || "" },
						callback(r) {
							resolve(
								(r.message || []).map((it) => ({
									value: it.name,
									description: it.alt
										? `↺ ${it.alt} · ${it.item_name || ""}`
										: it.item_name || "",
								}))
							);
						},
					});
				});
			},
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
		// Warehouse (parent) rows: bold; item (child) code links to the Item.
		if (data && data.indent === 0) {
			value = default_formatter(value, row, column, data);
			if (column.fieldname === "label") {
				value = `<span style="font-weight:700;">🏢 ${value}</span>`;
			}
			return value;
		}
		if (data && column.fieldname === "label" && data.item_code) {
			return `<a href="/app/item/${encodeURIComponent(data.item_code)}">${frappe.utils.escape_html(
				data.item_code
			)}</a>`;
		}
		value = default_formatter(value, row, column, data);
		if (data && column.fieldname === "status" && data.status === __("Below Minimum")) {
			value = `<span style="color:var(--red-600,#b00);font-weight:600;">${value}</span>`;
		}
		return value;
	},
};
