// Copyright (c) 2026, Azzir and contributors
// Sales Invoice items grid: same live stock columns as Quotation
// (dialog + click handled in the shared azzir_stock.js).

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		// Reverse-flow convenience: spin up a Quotation from this invoice.
		frm.add_custom_button(
			__("Quotation"),
			function () {
				frappe.model.open_mapped_doc({
					method: "azzir_fleet.sales_invoice.make_quotation",
					frm: frm,
				});
			},
			__("Create")
		);

		// Create a Delivery Note from a submitted invoice (works even when the
		// invoice didn't keep stock / came after a Sales Order).
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(
				__("Delivery Note"),
				function () {
					frappe.model.open_mapped_doc({
						method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.make_delivery_note",
						frm: frm,
					});
				},
				__("Create")
			);
		}
	},
});

frappe.ui.form.on("Sales Invoice Item", {
	item_code(frm, cdt, cdn) {
		azzir_fleet.fetch_row_stock(cdt, cdn);
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
