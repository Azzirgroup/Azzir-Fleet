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
			// ERPNext adds it in its own refresh, and re-adds it after async events
			// (status change, reload). One 500ms retry lost that race, so re-check
			// over the first couple of seconds and stop as soon as it's gone.
			if (frm.doc.doctype === "Purchase Order") {
				const drop = () => {
					try {
						frm.remove_custom_button(__("Purchase Receipt"), __("Create"));
					} catch (e) {
						/* button not there — nothing to remove */
					}
				};
				drop();
				[100, 300, 700, 1200, 2000].forEach((ms) => setTimeout(drop, ms));
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
			azzir_fleet.autofill_target_from_sister(frm, cdt, cdn);
		},
	});
});

// Auto Buy For Sister Company (Purchase Order only): the moment the row's own
// (receiving) Warehouse is known -- set directly, or filled in async a moment later
// by autofill_purchase_warehouse above -- check whether the buying company auto-buys
// for a sister, and if so fill in "Buy For Target Company" + Target Company + Target
// Warehouse right away, live, rather than waiting for Save.
azzir_fleet.autofill_target_from_sister = function (frm, cdt, cdn) {
	if (frm.doc.doctype !== "Purchase Order") return;
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !row.warehouse || row.azzir_row_to_target) return;
	frappe.call({
		method: "azzir_fleet.purchase_cycle.auto_target_for_row",
		args: { company: frm.doc.company, warehouse: row.warehouse },
		callback(r) {
			const d = r.message;
			const cur = locals[cdt] && locals[cdt][cdn];
			if (d && d.target_company && d.target_warehouse && cur && !cur.azzir_row_to_target) {
				frappe.model.set_value(cdt, cdn, "azzir_row_to_target", 1);
				frappe.model.set_value(cdt, cdn, "azzir_target_company", d.target_company);
				frappe.model.set_value(cdt, cdn, "azzir_target_warehouse", d.target_warehouse);
				// The values land in the underlying doc correctly either way, but an
				// OPEN row-edit dialog doesn't always repaint on its own when a
				// background call (not a direct user edit) changes its fields -- force
				// it, so you see the tick without having to close/reopen the row.
				const grid_row = frm.fields_dict.items.grid.grid_rows_by_docname[cdn];
				if (grid_row && grid_row.grid_form && grid_row.grid_form.fields_dict) {
					grid_row.grid_form.refresh();
				}
				frm.fields_dict.items.grid.refresh();
			}
		},
	});
};

frappe.ui.form.on("Purchase Order Item", {
	warehouse(frm, cdt, cdn) {
		azzir_fleet.autofill_target_from_sister(frm, cdt, cdn);
	},
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
