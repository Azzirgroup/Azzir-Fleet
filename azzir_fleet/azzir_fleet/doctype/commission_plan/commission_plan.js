// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt
//
// The Commission Plan is config only — the numbers are produced by the
// "Commission Report" (Reports > Commission Report), which lets you pick a plan
// or a branch, a date range and (optionally) one sales person.

frappe.ui.form.on("Commission Plan", {
	refresh(frm) {
		set_member_query(frm);
		if (!frm.is_new()) {
			frm.add_custom_button(__("Commission Report"), () => {
				frappe.set_route("query-report", "Commission Report", {
					commission_plan: frm.doc.name,
				});
			});
		}
	},
	branch(frm) {
		// Members are limited to the branch's sales people; clear stale picks.
		set_member_query(frm);
		(frm.doc.members || []).forEach((m) => frappe.model.set_value(m.doctype, m.name, "sales_person", null));
		frm.refresh_field("members");
	},
});

function set_member_query(frm) {
	frm.set_query("sales_person", "members", () => ({
		query: "azzir_fleet.commission.branch_sales_persons",
		filters: { branch: frm.doc.branch },
	}));
}
