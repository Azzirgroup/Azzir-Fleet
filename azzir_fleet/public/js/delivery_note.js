// Copyright (c) 2026, Azzir and contributors
// Delivery Note "Get Items From": hide Sales Order, add Sales Invoice so items
// are pulled from a submitted Sales Invoice instead. (Pick List stays.)

frappe.ui.form.on("Delivery Note", {
	refresh(frm) {
		azzir_fleet.set_warehouse_cc_query(frm);
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
