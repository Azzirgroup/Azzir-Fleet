// Copyright (c) 2026, Azzir and contributors
// Purchase cycle (buy for another company): PER ROW. Tick "Buy For Target Company"
// on an item line, then pick its Target Company + Target Warehouse (the warehouse
// link is filtered to that company). No header fields. Also auto-fills the row's own
// (receiving) warehouse from where the item was last stored, like the Receipt.

frappe.provide("azzir_fleet");

azzir_fleet.set_target_wh_query = function (frm) {
	if (!frm.fields_dict.items) return;
	// Per-row target warehouse: only warehouses in the row's target company.
	frm.set_query("azzir_target_warehouse", "items", function (doc, cdt, cdn) {
		const row = locals[cdt][cdn] || {};
		return {
			filters: { company: row.azzir_target_company || "", is_group: 0, disabled: 0 },
		};
	});
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
		refresh(frm) {
			azzir_fleet.set_target_wh_query(frm);
			// Purchase Order: drop the standard "Create > Purchase Receipt" button.
			if (frm.doc.doctype === "Purchase Order") {
				const drop = () => frm.remove_custom_button(__("Purchase Receipt"), __("Create"));
				drop();
				setTimeout(drop, 500); // in case ERPNext adds it late
			}
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

// Per-row: unticking "Buy For Target Company" clears the target picks; changing the
// target company clears the target warehouse (it may not belong to the new company).
["Purchase Order Item", "Purchase Receipt Item", "Purchase Invoice Item"].forEach(function (dt) {
	frappe.ui.form.on(dt, {
		azzir_row_to_target(frm, cdt, cdn) {
			const row = locals[cdt][cdn];
			if (row && !row.azzir_row_to_target) {
				frappe.model.set_value(cdt, cdn, "azzir_target_company", "");
				frappe.model.set_value(cdt, cdn, "azzir_target_warehouse", "");
			}
		},
		azzir_target_company(frm, cdt, cdn) {
			frappe.model.set_value(cdt, cdn, "azzir_target_warehouse", "");
		},
	});
});
