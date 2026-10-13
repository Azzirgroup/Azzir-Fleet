// Copyright (c) 2026, Azzir and contributors
// "Paid On Behalf Of Sister Company": filter the sister invoice pickers (Sales Invoice
// for Receive, Purchase Invoice for Pay) to only the chosen sister's invoices for this
// exact party that still have something outstanding, and auto-fill the paid amount
// from whichever invoice is picked -- instead of a plain unfiltered link field.

frappe.ui.form.on("Payment Entry", {
	onload(frm) {
		frm.set_query("azzir_sister_invoice", function () {
			return {
				filters: {
					company: frm.doc.azzir_sister_company || "",
					customer: frm.doc.party || "",
					docstatus: 1,
					outstanding_amount: [">", 0],
				},
			};
		});
		frm.set_query("azzir_sister_purchase_invoice", function () {
			return {
				filters: {
					company: frm.doc.azzir_sister_company || "",
					supplier: frm.doc.party || "",
					docstatus: 1,
					outstanding_amount: [">", 0],
				},
			};
		});
	},
	// The previously picked invoice may no longer belong to the new sister company.
	azzir_sister_company(frm) {
		["azzir_sister_invoice", "azzir_sister_purchase_invoice"].forEach((f) => {
			if (frm.doc[f]) frappe.model.set_value(frm.doctype, frm.docname, f, "");
		});
	},
	// Same if the party itself changes.
	party(frm) {
		if (!frm.doc.azzir_paid_on_behalf_of_sister) return;
		["azzir_sister_invoice", "azzir_sister_purchase_invoice"].forEach((f) => {
			if (frm.doc[f]) frappe.model.set_value(frm.doctype, frm.docname, f, "");
		});
	},
	// Switching Receive/Pay changes which invoice field is even relevant.
	payment_type(frm) {
		if (!frm.doc.azzir_paid_on_behalf_of_sister) return;
		["azzir_sister_invoice", "azzir_sister_purchase_invoice"].forEach((f) => {
			if (frm.doc[f]) frappe.model.set_value(frm.doctype, frm.docname, f, "");
		});
	},
	azzir_paid_on_behalf_of_sister(frm) {
		if (!frm.doc.azzir_paid_on_behalf_of_sister) {
			["azzir_sister_company", "azzir_sister_invoice", "azzir_sister_purchase_invoice"].forEach((f) => {
				frappe.model.set_value(frm.doctype, frm.docname, f, "");
			});
		}
	},
	// Bring the paid/received amount down to match the picked invoice's own
	// outstanding balance -- the whole point of this invoice is to settle exactly it.
	azzir_sister_invoice(frm) {
		if (!frm.doc.azzir_sister_invoice) return;
		frappe.db.get_value("Sales Invoice", frm.doc.azzir_sister_invoice, "outstanding_amount").then((r) => {
			const outstanding = (r.message || {}).outstanding_amount;
			if (outstanding) {
				frm.set_value("paid_amount", outstanding);
				frm.set_value("received_amount", outstanding);
			}
		});
	},
	azzir_sister_purchase_invoice(frm) {
		if (!frm.doc.azzir_sister_purchase_invoice) return;
		frappe.db.get_value("Purchase Invoice", frm.doc.azzir_sister_purchase_invoice, "outstanding_amount").then((r) => {
			const outstanding = (r.message || {}).outstanding_amount;
			if (outstanding) {
				frm.set_value("paid_amount", outstanding);
				frm.set_value("received_amount", outstanding);
			}
		});
	},
});
