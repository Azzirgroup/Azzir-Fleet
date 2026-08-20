// Copyright (c) 2026, Azzir and contributors
// Delivery Note "Get Items From": hide Sales Order, add Sales Invoice so items
// are pulled from a submitted Sales Invoice instead. (Pick List stays.)

// Each line's warehouse is limited to the LEAF (bin) warehouses under the GROUP
// region that was chosen on the source Sales Invoice line. A plain (non-sourced)
// delivery note just lists all leaves.
function set_leaf_wh_query(frm) {
	frm.set_query("warehouse", "items", (doc, cdt, cdn) => {
		const row = locals[cdt][cdn];
		return {
			query: "azzir_fleet.warehouse.leaves_under",
			filters: {
				company: doc.company || undefined,
				si_item: (row && row.si_detail) || undefined,
			},
		};
	});
}

// A Delivery Note made from a Sales Invoice carries the SI's GROUP (region)
// warehouse on each line. Groups hold no stock, so drop them the moment the form
// opens: auto-fill the bin when the region has just one, else clear it so the
// user picks from the (already-filtered) list — no manual deleting needed.
function fix_group_warehouses(frm) {
	if (frm.doc.docstatus !== 0) return;
	const whs = [...new Set((frm.doc.items || []).map((r) => r.warehouse).filter(Boolean))];
	if (!whs.length) return;
	frappe.call({
		method: "azzir_fleet.warehouse.resolve_delivery_warehouses",
		args: { names: JSON.stringify(whs) },
		callback(r) {
			const map = r.message || {};
			if (!Object.keys(map).length) return; // no groups among them
			let changed = false;
			(frm.doc.items || []).forEach((row) => {
				if (row.warehouse && Object.prototype.hasOwnProperty.call(map, row.warehouse)) {
					frappe.model.set_value(row.doctype, row.name, "warehouse", map[row.warehouse] || "");
					changed = true;
				}
			});
			if (changed) frm.refresh_field("items");
		},
	});
}

frappe.ui.form.on("Delivery Note", {
	setup: set_leaf_wh_query,
	onload: set_leaf_wh_query,
	refresh(frm) {
		set_leaf_wh_query(frm);
		fix_group_warehouses(frm);
		// Safety net in case items populate a moment after the mapped doc opens.
		setTimeout(() => fix_group_warehouses(frm), 1200);
		if (frm.doc.docstatus !== 0) return; // get-items only makes sense on a draft

		const drop_sales_order = () =>
			frm.remove_custom_button(__("Sales Order"), __("Get Items From"));
		drop_sales_order();
		setTimeout(drop_sales_order, 500); // in case ERPNext adds it late

		frm.add_custom_button(
			__("Sales Invoice"),
			function () {
				erpnext.utils.map_current_doc({
					method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.make_delivery_note",
					source_doctype: "Sales Invoice",
					target: frm,
					setters: {
						customer: frm.doc.customer || undefined,
					},
					get_query_filters: {
						docstatus: 1,
						company: frm.doc.company || undefined,
						customer: frm.doc.customer || undefined,
					},
				});
			},
			__("Get Items From")
		);
	},
});
