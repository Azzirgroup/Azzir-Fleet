// Copyright (c) 2026, Azzir and contributors
// Stock Entry row detail: total stock across all warehouses + a button that opens
// the per-warehouse tree dialog. (Nothing added to the grid.)

frappe.provide("azzir_fleet");

function set_stock_item_query(frm) {
	// Item Code is intentionally NOT filtered by stock — ANY item can be picked
	// (old codes still resolve via the standard alias-aware item search). Whether the
	// source warehouse actually has enough stock is checked at submit, not here — so
	// selecting an item never silently clears just because that source is empty.

	// Reverse: once the item is chosen, the row's Source Warehouse lists only the
	// warehouses that actually hold that item — no hunting for where the stock is.
	frm.set_query("s_warehouse", "items", function (doc, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row && row.item_code) {
			return {
				query: "azzir_fleet.stock_info.warehouses_with_stock",
				filters: { item_code: row.item_code, company: doc.company },
			};
		}
		return {};
	});

	// Header Set Source / Set Target Warehouse: cost-centre scoped like the sales
	// docs (only warehouses the user may select; groups allowed).
	["from_warehouse", "to_warehouse"].forEach((field) => {
		frm.set_query(field, function (doc) {
			return {
				query: "azzir_fleet.warehouse_cc.warehouse_query",
				filters: { company: doc.company },
			};
		});
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
		if (row && row.item_code) {
			// Stock Entry rows have source (s_warehouse) / target (t_warehouse), not
			// a single `warehouse` — set the source, which is the "has stock" one.
			azzir_fleet.show_stock_dialog(row.item_code, (wh) =>
				frappe.model.set_value(cdt, cdn, "s_warehouse", wh)
			);
		}
	},
});
