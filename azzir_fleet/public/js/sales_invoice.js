// Copyright (c) 2026, Azzir and contributors
// Sales Invoice items grid: same live stock columns as Quotation
// (dialog + click handled in the shared azzir_stock.js).

frappe.ui.form.on("Sales Invoice Item", {
	item_code(frm, cdt, cdn) {
		azzir_fleet.fetch_row_stock(cdt, cdn);
	},
	warehouse(frm, cdt, cdn) {
		azzir_fleet.fetch_row_stock(cdt, cdn);
	},
	azzir_view_stock(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row && row.item_code) azzir_fleet.show_stock_dialog(row.item_code);
	},
});
