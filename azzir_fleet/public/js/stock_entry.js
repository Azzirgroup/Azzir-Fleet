// Copyright (c) 2026, Azzir and contributors
// Stock Entry row detail: total stock across all warehouses + a button that opens
// the per-warehouse tree dialog. (Nothing added to the grid.)

frappe.provide("azzir_fleet");

function set_stock_item_query(frm) {
	// Only show items that have stock in the source warehouse (row's source, else
	// the document's default source). No source set -> all items.
	frm.set_query("item_code", "items", function (doc, cdt, cdn) {
		const row = locals[cdt][cdn];
		const wh = (row && row.s_warehouse) || doc.from_warehouse;
		if (wh) {
			return {
				query: "azzir_fleet.stock_info.items_with_stock",
				filters: { warehouse: wh },
			};
		}
		return {};
	});
}

frappe.ui.form.on("Stock Entry", {
	setup: set_stock_item_query,
	onload: set_stock_item_query,
	refresh: set_stock_item_query,
});

frappe.ui.form.on("Stock Entry Detail", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt] && locals[cdt][cdn];
		if (!row || !row.item_code) return;
		frappe.call({
			method: "azzir_fleet.stock_info.get_item_stock",
			args: { item_code: row.item_code },
			callback(r) {
				if (r.message) {
					frappe.model.set_value(cdt, cdn, "azzir_all_stock", r.message.all_stock);
				}
			},
		});
	},

	azzir_view_stock(frm, cdt, cdn) {
		const row = locals[cdt] && locals[cdt][cdn];
		if (row && row.item_code) azzir_fleet.show_stock_dialog(row.item_code);
	},
});
