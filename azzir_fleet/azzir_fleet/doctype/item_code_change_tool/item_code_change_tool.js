// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt

frappe.ui.form.on("Item Code Change Tool", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Preview"), () => {
				frm.call("generate_preview").then(() => frm.reload_doc());
			});

			if (["Previewed", "Failed"].includes(frm.doc.status)) {
				frm.add_custom_button(__("Run Changes"), () => {
					frappe.confirm(
						__(
							"This will rename all items with status OK. Old codes are saved as aliases. Continue?"
						),
						() => {
							frm.call("run_changes", { run_now: 0 }).then(() => {
								frappe.show_alert({
									message: __("Rename job queued. Refresh to see progress."),
									indicator: "blue",
								});
								frm.reload_doc();
							});
						}
					);
				}).addClass("btn-primary");
			}
		}
	},
});
