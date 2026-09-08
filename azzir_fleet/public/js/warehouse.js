// Copyright (c) 2026, Azzir and contributors
// Warehouse.azzir_branch (Branch link) is filtered by the warehouse's is_group:
//   - a GROUP warehouse  -> only branches flagged Is Group
//   - a LEAF  warehouse  -> only branches NOT flagged Is Group
// The query reads frm.doc.is_group live, so it stays correct if is_group changes.

function azzir_set_branch_query(frm) {
	frm.set_query("azzir_branch", () => ({
		filters: { azzir_is_group: frm.doc.is_group ? 1 : 0 },
	}));
}

frappe.ui.form.on("Warehouse", {
	onload(frm) {
		azzir_set_branch_query(frm);
	},
	refresh(frm) {
		azzir_set_branch_query(frm);
	},
	is_group(frm) {
		// The current pick may no longer match the new group/leaf state — clear it
		// so the user re-picks from the correct list.
		if (frm.doc.azzir_branch) frm.set_value("azzir_branch", null);
		azzir_set_branch_query(frm);
	},
});
