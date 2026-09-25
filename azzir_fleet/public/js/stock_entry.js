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

	// Default GROUP Source / Target Warehouse: only GROUP warehouses, cost-centre scoped.
	["azzir_group_source_warehouse", "azzir_group_target_warehouse"].forEach((field) => {
		if (!frm.fields_dict[field]) return;
		frm.set_query(field, function (doc) {
			return {
				query: "azzir_fleet.warehouse_cc.warehouse_query",
				filters: { company: doc.company, is_group: 1 },
			};
		});
	});

	// Row Target Warehouse: when a Group Target is set, only its child (leaf) warehouses.
	frm.set_query("t_warehouse", "items", function (doc) {
		if (doc.azzir_group_target_warehouse) {
			return {
				query: "azzir_fleet.stock_info.leaves_in_group",
				filters: { group: doc.azzir_group_target_warehouse },
			};
		}
		return {};
	});

	// When the Stock Entry was created FROM a Purchase Receipt, the source comes from
	// the receipt — lock the Group Source Warehouse so it can't override it.
	if (frm.fields_dict.azzir_group_source_warehouse) {
		frm.set_df_property("azzir_group_source_warehouse", "read_only", frm.doc.purchase_receipt_no ? 1 : 0);
	}
}

// When a Group Source is set and an item is chosen, auto-fill the row's Source
// Warehouse with the child warehouse holding the most of that item — but never
// override a warehouse already set (e.g. one that came from a Purchase Receipt).
function autofill_group_source(frm, cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !row.item_code || !frm.doc.azzir_group_source_warehouse) return;
	if (row.s_warehouse || row.reference_purchase_receipt || frm.doc.purchase_receipt_no) return;
	frappe.call({
		method: "azzir_fleet.stock_info.best_warehouse_in_group",
		args: { item_code: row.item_code, warehouse: frm.doc.azzir_group_source_warehouse },
		callback(r) {
			if (r.message) frappe.model.set_value(cdt, cdn, "s_warehouse", r.message);
		},
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
		autofill_group_source(frm, cdt, cdn);
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
