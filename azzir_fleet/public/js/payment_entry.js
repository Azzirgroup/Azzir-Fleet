// Copyright (c) 2026, Azzir and contributors
// "Paid On Behalf Of Sister Company": filter the Sister Invoice picker to only the
// chosen sister's invoices for this exact party that still have something outstanding,
// and auto-fill the paid amount from whichever invoice is picked -- instead of a plain
// unfiltered Sales Invoice link showing every invoice in the system.

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
	},
	// The previously picked invoice may no longer belong to the new sister company.
	azzir_sister_company(frm) {
		if (frm.doc.azzir_sister_invoice) {
			frappe.model.set_value(frm.doctype, frm.docname, "azzir_sister_invoice", "");
		}
	},
	// Same if the customer itself changes.
	party(frm) {
		if (frm.doc.azzir_paid_on_behalf_of_sister && frm.doc.azzir_sister_invoice) {
			frappe.model.set_value(frm.doctype, frm.docname, "azzir_sister_invoice", "");
		}
	},
	azzir_paid_on_behalf_of_sister(frm) {
		if (!frm.doc.azzir_paid_on_behalf_of_sister) {
			frappe.model.set_value(frm.doctype, frm.docname, "azzir_sister_company", "");
			frappe.model.set_value(frm.doctype, frm.docname, "azzir_sister_invoice", "");
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
});
