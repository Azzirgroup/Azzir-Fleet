// Copyright (c) 2026, Azzir and contributors
// Purchase Invoice: wrap the standard "Create > Purchase Receipt" button so it warns
// before making another draft when one already exists, unsubmitted, from this invoice.

frappe.provide("azzir_fleet");

frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		// ERPNext core adds "Create > Purchase Receipt" itself, asynchronously, and
		// re-adds it after status changes / reloads — same race azzir_purchase.js
		// already handles for Purchase Order's own Create button. Replace it with a
		// guarded version each time it reappears, rather than a single-shot swap.
		const replace = () => {
			try {
				frm.remove_custom_button(__("Purchase Receipt"), __("Create"));
			} catch (e) {
				/* button not there yet — nothing to remove */
			}
			frm.add_custom_button(
				__("Purchase Receipt"),
				function () {
					azzir_fleet.guard_create(frm, {
						child_doctype: "Purchase Receipt Item",
						link_field: "purchase_invoice",
						target_doctype: "Purchase Receipt",
						make() {
							frappe.model.open_mapped_doc({
								method: "erpnext.accounts.doctype.purchase_invoice.purchase_invoice.make_purchase_receipt",
								frm: frm,
							});
						},
					});
				},
				__("Create")
			);
		};
		[100, 300, 700, 1200, 2000].forEach((ms) => setTimeout(replace, ms));
	},
});
