// Pure redirect: exists so "credit note" matches it in global search (Pages are
// searchable by title) and takes the user straight to the filtered list, since
// ERPNext has no separate Credit Note doctype -- a credit note IS a Sales
// Invoice with Is Return checked.
frappe.pages["credit-note"].on_page_load = function (wrapper) {
	frappe.route_options = { is_return: 1 };
	frappe.set_route("List", "Sales Invoice");
};
