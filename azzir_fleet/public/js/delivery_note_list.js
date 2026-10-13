// Delivery Notes must be created FROM a Sales Invoice (Create > Delivery Note), never
// blank off the list view -- that's how a DN loses its link back to the invoice it
// came from. `can_create` is a plain instance property Frappe sets once (from the
// user's actual create permission) and never resets on refresh -- flipping it off
// here suppresses the "+ Add" button, the Ctrl+B shortcut, AND the "create your
// first Delivery Note" empty-state button all at once, correctly, instead of fighting
// each render with DOM removal. The mapped-doc flow off a Sales Invoice calls
// frappe.model.open_mapped_doc directly and never goes through this page at all.
frappe.listview_settings["Delivery Note"] = frappe.listview_settings["Delivery Note"] || {};

(function () {
	const s = frappe.listview_settings["Delivery Note"];
	const prev_onload = s.onload;
	s.onload = function (listview) {
		if (prev_onload) prev_onload(listview);
		listview.can_create = false;
		listview.set_primary_action();
	};
})();
