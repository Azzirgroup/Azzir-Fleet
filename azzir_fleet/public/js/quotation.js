// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt
//
// Live stock on the Quotation items grid:
//  - "Stock (This WH)"  = item stock in the row's warehouse
//  - "Stock (All WH)"   = total across all warehouses; click it for a per-warehouse
//                         breakdown grouped by the warehouse tree.

frappe.provide("azzir_fleet");

frappe.ui.form.on("Quotation Item", {
	item_code(frm, cdt, cdn) {
		azzir_fleet.fetch_row_stock(cdt, cdn);
	},
	warehouse(frm, cdt, cdn) {
		azzir_fleet.fetch_row_stock(cdt, cdn);
	},
});

azzir_fleet.fetch_row_stock = function (cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !row.item_code) return;
	frappe.call({
		method: "azzir_fleet.stock_info.get_item_stock",
		args: { item_code: row.item_code, warehouse: row.warehouse || "" },
		callback(r) {
			if (!r.message) return;
			frappe.model.set_value(cdt, cdn, "azzir_wh_stock", r.message.wh_stock);
			frappe.model.set_value(cdt, cdn, "azzir_all_stock", r.message.all_stock);
		},
	});
};

// Click the "Stock (All WH)" cell -> per-warehouse breakdown dialog.
$(document).on("click", '.grid-row [data-fieldname="azzir_all_stock"]', function () {
	const cdn = $(this).closest("[data-name]").attr("data-name");
	const row = cdn && locals["Quotation Item"] && locals["Quotation Item"][cdn];
	if (row && row.item_code) azzir_fleet.show_stock_dialog(row.item_code);
});

// azzir_fleet.show_stock_dialog lives in the shared azzir_stock.js (app_include_js).

// Visual cue that the All-WH cell is clickable.
$('<style>.grid-row [data-fieldname="azzir_all_stock"]{cursor:pointer;color:#1a73e8;text-decoration:underline;}</style>').appendTo("head");
