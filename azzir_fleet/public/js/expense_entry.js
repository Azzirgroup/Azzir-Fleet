// Copyright (c) 2026, Azzir and contributors
// "Paid On Behalf Of Sister Company": filter the sister Purchase Invoice picker to
// only the chosen sister's invoices for this exact supplier that still have
// something outstanding, and bring the Accounts table down to a single row matching
// that invoice's outstanding balance -- instead of a plain unfiltered link field.

frappe.ui.form.on("Expense Entry", {
	onload(frm) {
		frm.set_query("azzir_sister_purchase_invoice", function () {
			return {
				filters: {
					company: frm.doc.azzir_sister_company || "",
					supplier: frm.doc.supplier || "",
					docstatus: 1,
					outstanding_amount: [">", 0],
				},
			};
		});
	},
	// The previously picked invoice may no longer belong to the new sister company.
	azzir_sister_company(frm) {
		if (frm.doc.azzir_sister_purchase_invoice) {
			frm.set_value("azzir_sister_purchase_invoice", "");
		}
	},
	// Same if the supplier itself changes.
	supplier(frm) {
		if (!frm.doc.azzir_paid_on_behalf_of_sister) return;
		if (frm.doc.azzir_sister_purchase_invoice) {
			frm.set_value("azzir_sister_purchase_invoice", "");
		}
	},
	azzir_paid_on_behalf_of_sister(frm) {
		if (!frm.doc.azzir_paid_on_behalf_of_sister) {
			["supplier", "azzir_sister_company", "azzir_sister_purchase_invoice"].forEach((f) => {
				frappe.model.set_value(frm.doctype, frm.docname, f, "");
			});
		}
	},
	// Bring the Accounts table down to a single row matching exactly what the
	// sister invoice still owes -- the whole point of this entry is to settle it.
	// The actual GL Account on that row is filled in server-side on save.
	azzir_sister_purchase_invoice(frm) {
		if (!frm.doc.azzir_sister_purchase_invoice) return;
		frappe.db.get_value("Purchase Invoice", frm.doc.azzir_sister_purchase_invoice, "outstanding_amount").then((r) => {
			const outstanding = (r.message || {}).outstanding_amount;
			if (!outstanding) return;
			frm.clear_table("accounts");
			const row = frm.add_child("accounts");
			row.amount = outstanding;
			frm.refresh_field("accounts");
		});
	},
});
