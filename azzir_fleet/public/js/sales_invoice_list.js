// Colour the custom "Delivery Status" column in the Sales Invoice list like the
// native Status pills (green = fully, orange = partly, red = not delivered).
frappe.listview_settings["Sales Invoice"] = frappe.listview_settings["Sales Invoice"] || {};

(function () {
	const s = frappe.listview_settings["Sales Invoice"];
	const colorFor = {
		"Fully Delivered": "green",
		"Partly Delivered": "orange",
		"Not Delivered": "red",
	};
	s.formatters = Object.assign({}, s.formatters, {
		azzir_delivery_status(value) {
			if (!value) return "";
			const color = colorFor[value] || "gray";
			const label = frappe.utils.escape_html(value);
			return `<span class="indicator-pill ${color}">${label}</span>`;
		},
	});

	// Soft default: only applies until the user has their OWN saved filter state
	// for this list view (Frappe's list_view.js checks view_user_settings.filters
	// first, falling back to this). So it shows "Is Sales Invoice" ticked out of
	// the box, but the moment a user ticks/unticks anything themselves, their own
	// choice is what sticks from then on -- never locked, never re-forced.
	s.filters = [["azzir_is_sales_invoice", "=", 1]];

	// "Is Return" and "Is Sales Invoice" are opposites -- a document can never be
	// both, so checking one disables (and force-unchecks) the other in the
	// standard filter bar. Rebound on every refresh since the filter bar can be
	// re-rendered; namespaced + always unbound first so handlers never stack.
	function wire_mutual_exclusion(listview) {
		const a = listview.page.fields_dict["is_return"];
		const b = listview.page.fields_dict["azzir_is_sales_invoice"];
		if (!a || !b) return; // filter bar not built yet -- next refresh will catch it

		function sync() {
			a.$input.prop("disabled", !!b.get_value());
			b.$input.prop("disabled", !!a.get_value());
		}

		function bind(field, other) {
			field.$input.off("change.azzir_mutex").on("change.azzir_mutex", function () {
				if ($(this).is(":checked") && other.get_value()) {
					other.set_value(0);
				}
				sync();
			});
		}

		bind(a, b);
		bind(b, a);
		sync();
	}

	// Chain, don't clobber -- erpnext core's own sales_invoice_list.js already sets
	// onload (adds the "Delivery Note" / "Payment" bulk-action buttons); whichever
	// of the two files loads second would otherwise wipe the other's onload out.
	const existing_onload = s.onload;
	s.onload = function (listview) {
		if (existing_onload) existing_onload(listview);
		wire_mutual_exclusion(listview);
	};
	const existing_refresh = s.refresh;
	s.refresh = function (listview) {
		if (existing_refresh) existing_refresh(listview);
		wire_mutual_exclusion(listview);
	};
})();
