// Copyright (c) 2026, Azzir and contributors
// Quotation: swap the standard "Create > Sales Order" for "Create > Sales Invoice"
// (hidden when the quotation itself came from a Sales Invoice), plus live stock cols.

// Sales documents don't move stock, so a user only picks a GROUP (region)
// warehouse — never a bin. The real bin is chosen later on the Delivery Note.
function set_group_wh_query(frm) {
	frm.set_query("warehouse", "items", (doc) => ({
		query: "azzir_fleet.warehouse.group_warehouses",
		filters: { company: doc.company },
	}));
	if (frm.fields_dict.set_warehouse) {
		frm.set_query("set_warehouse", (doc) => ({
			query: "azzir_fleet.warehouse.group_warehouses",
			filters: { company: doc.company },
		}));
	}
}

frappe.ui.form.on("Quotation", {
	setup: set_group_wh_query,
	onload: set_group_wh_query,
	refresh(frm) {
		set_group_wh_query(frm);
		const drop_sales_order = () => frm.remove_custom_button(__("Sales Order"), __("Create"));
		// Remove now and again shortly after, in case ERPNext adds it late.
		drop_sales_order();
		setTimeout(drop_sales_order, 500);

		// Offer Sales Invoice only on a submitted quotation that (a) did NOT originate
		// from a Sales Invoice (avoids invoice -> quotation -> invoice loop) and
		// (b) has not already been invoiced (a submitted SI set azzir_invoiced).
		if (
			frm.doc.docstatus === 1 &&
			!frm.doc.azzir_source_sales_invoice &&
			!frm.doc.azzir_invoiced
		) {
			frm.add_custom_button(
				__("Sales Invoice"),
				function () {
					frappe.model.open_mapped_doc({
						method: "azzir_fleet.quotation.make_sales_invoice",
						frm: frm,
					});
				},
				__("Create")
			);
		}
	},
});

frappe.ui.form.on("Quotation Item", {
	item_code(frm, cdt, cdn) {
		azzir_fleet.fetch_row_stock(cdt, cdn);
		azzir_fleet.strip_leaf_after_autofill(cdt, cdn); // no auto default bin
	},
	warehouse(frm, cdt, cdn) {
		azzir_fleet.on_sales_warehouse(cdt, cdn);
	},
	azzir_view_stock(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row && row.item_code) {
			azzir_fleet.show_stock_dialog(
				row.item_code,
				(wh) => frappe.model.set_value(cdt, cdn, "warehouse", wh),
				{ groups_only: true }
			);
		}
	},
});
