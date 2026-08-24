// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt

frappe.ui.form.on("Item Code Import", {
	refresh(frm) {
		frm.disable_save();

		frm.add_custom_button(__("Dry Run (Preview)"), () => {
			if (!frm.doc.spreadsheet) {
				frappe.msgprint(__("Attach a spreadsheet first."));
				return;
			}
			frappe.dom.freeze(__("Analysing spreadsheet..."));
			frappe.call({
				method: "azzir_fleet.item_code_import.preview",
				args: {
					file_url: frm.doc.spreadsheet,
					sheet: frm.doc.sheet_name,
					mode: (frm.doc.mode || "Replace").toLowerCase(),
				},
				always: () => frappe.dom.unfreeze(),
				callback: (r) => {
					frm.reload_doc();
					frappe.msgprint({
						title: __("Dry Run"),
						message: "<pre>" + frappe.utils.escape_html(r.message || "") + "</pre>",
						indicator: "blue",
					});
				},
			});
		});

		frm.add_custom_button(__("Run Import"), () => {
			if (!frm.doc.spreadsheet) {
				frappe.msgprint(__("Attach a spreadsheet first."));
				return;
			}
			frappe.confirm(
				__("Replace the code table for every matching item from this file? This runs in the background."),
				() => {
					frappe.call({
						method: "azzir_fleet.item_code_import.start",
						args: {
							file_url: frm.doc.spreadsheet,
							sheet: frm.doc.sheet_name,
							mode: (frm.doc.mode || "Replace").toLowerCase(),
						},
						callback: () => {
							frm.reload_doc();
							frappe.show_alert({
								message: __("Import queued — you'll be notified when it finishes."),
								indicator: "green",
							});
						},
					});
				}
			);
		}).addClass("btn-primary");
	},
});
