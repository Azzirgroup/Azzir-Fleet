// Copyright (c) 2026, Azzir and contributors
// Quotation: swap the standard "Create > Sales Order" for "Create > Sales Invoice"
// (hidden when the quotation itself came from a Sales Invoice), plus live stock cols.

frappe.ui.form.on("Quotation", {
	onload_post_render(frm) {
		azzir_fleet.toggle_buy_from_sister(frm);
	},
	azzir_supply_company(frm) {
		azzir_fleet.set_supply_wh_query(frm);
		frm.set_value("azzir_supply_warehouse", "");
	},
	refresh(frm) {
		azzir_fleet.set_warehouse_cc_query(frm);
		azzir_fleet.toggle_buy_from_sister(frm);
		azzir_fleet.set_supply_wh_query(frm);
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
		azzir_fleet.autoset_cc_warehouse(frm, cdt, cdn);
	},
	warehouse(frm, cdt, cdn) {
		azzir_fleet.fetch_row_stock(cdt, cdn);
	},
	azzir_view_stock(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row && row.item_code) {
			azzir_fleet.show_stock_dialog(row.item_code, (wh) =>
				frappe.model.set_value(cdt, cdn, "warehouse", wh)
			);
		}
	},
});
