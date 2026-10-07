// Copyright (c) 2026, Azzir and contributors
// Wrap a "Create > X" mapper button so it checks for an existing, unsubmitted draft
// already made from this source first -- offering to open it instead of silently
// letting a duplicate draft pile up when someone forgot they already started one.

frappe.provide("azzir_fleet");

// child_doctype/link_field: where a mapped row records its source (e.g. "Delivery
// Note Item" / "against_sales_invoice"). target_doctype: the doctype being created
// (for the dialog text). make: the function that actually creates the new document,
// called when there's nothing to warn about, or the user picks "Create new anyway".
azzir_fleet.guard_create = function (frm, { child_doctype, link_field, target_doctype, make }) {
	frappe.call({
		method: "azzir_fleet.draft_guard.find_draft_target",
		args: { child_doctype, link_field, source_name: frm.doc.name },
		callback(r) {
			const existing = r.message;
			if (!existing) {
				make();
				return;
			}
			const d = new frappe.ui.Dialog({
				title: __("Unsaved {0} already exists", [__(target_doctype)]),
				fields: [
					{
						fieldtype: "HTML",
						options: `<p>${__("{0} {1} was already started from this document and hasn't been saved or submitted yet.", [__(target_doctype), `<b>${frappe.utils.escape_html(existing)}</b>`])}</p>`,
					},
				],
				primary_action_label: __("Go to it"),
				primary_action() {
					d.hide();
					frappe.set_route("Form", target_doctype, existing);
				},
				secondary_action_label: __("Create new anyway"),
				secondary_action() {
					d.hide();
					make();
				},
			});
			d.show();
		},
	});
};
