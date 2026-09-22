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
})();
