// Copyright (c) 2026, Azzir and contributors
// Purchase cycle (buy for another company): header Target Company/Warehouse are
// DEFAULTS that populate the item rows; the per-row Target Warehouse link is
// filtered to warehouses in that row's Target Company. Also auto-fills the row's
// own (receiving) warehouse from where the item was last stored, like the Receipt.

frappe.provide("azzir_fleet");

azzir_fleet.set_target_wh_query = function (frm) {
	if (!frm.fields_dict.items) return;
	// Per-row target warehouse: only warehouses in the row's target company.
	frm.set_query("azzir_target_warehouse", "items", function (doc, cdt, cdn) {
		const row = locals[cdt][cdn] || {};
		return {
			filters: {
				company: row.azzir_target_company || doc.azzir_target_company || "",
				is_group: 0,
				disabled: 0,
			},
		};
	});
	// Header default target warehouse: warehouses in the header target company.
	if (frm.fields_dict.azzir_target_warehouse) {
		frm.set_query("azzir_target_warehouse", function (doc) {
			return { filters: { company: doc.azzir_target_company || "", is_group: 0, disabled: 0 } };
		});
	}
};

// Header target company/warehouse are DEFAULTS: push them onto the item rows
// (each row can then be changed to a different target company).
azzir_fleet.populate_target = function (frm, field) {
	const val = frm.doc[field];
	if (!val) return;
	(frm.doc.items || []).forEach((r) => frappe.model.set_value(r.doctype, r.name, field, val));
};

// Auto-fill the row's own receiving warehouse from the item's last-stored warehouse.
azzir_fleet.autofill_purchase_warehouse = function (frm, cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !row.item_code || row.warehouse) return;
	frappe.call({
		method: "azzir_fleet.stock_info.last_warehouse",
		args: { item_code: row.item_code, company: frm.doc.company },
		callback(r) {
			if (r.message && locals[cdt][cdn] && !locals[cdt][cdn].warehouse) {
				frappe.model.set_value(cdt, cdn, "warehouse", r.message);
			}
		},
	});
};

["Purchase Order", "Purchase Receipt", "Purchase Invoice"].forEach(function (dt) {
	frappe.ui.form.on(dt, {
		onload: azzir_fleet.set_target_wh_query,
		refresh: azzir_fleet.set_target_wh_query,
		azzir_target_company(frm) {
			azzir_fleet.set_target_wh_query(frm);
			frm.set_value("azzir_target_warehouse", "");
			azzir_fleet.populate_target(frm, "azzir_target_company");
		},
		azzir_target_warehouse(frm) {
			azzir_fleet.populate_target(frm, "azzir_target_warehouse");
		},
	});
});

// Purchase Order / Invoice item rows: same last-warehouse autofill the Receipt has.
// (Purchase Receipt keeps its own handler in purchase_receipt.js.)
["Purchase Order Item", "Purchase Invoice Item"].forEach(function (dt) {
	frappe.ui.form.on(dt, {
		item_code(frm, cdt, cdn) {
			azzir_fleet.autofill_purchase_warehouse(frm, cdt, cdn);
		},
	});
});

// When a row's Target Company changes, clear its Target Warehouse (it may not
// belong to the new company).
["Purchase Order Item", "Purchase Receipt Item", "Purchase Invoice Item"].forEach(function (dt) {
	frappe.ui.form.on(dt, {
		azzir_target_company(frm, cdt, cdn) {
			frappe.model.set_value(cdt, cdn, "azzir_target_warehouse", "");
		},
	});
});
