// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt

frappe.ui.form.on("Item Code Import", {
	refresh(frm) {
		frm.add_custom_button(__("Dry Run (Preview)"), () => run(frm, "preview"));
		frm.add_custom_button(__("Run Import"), () => {
			const mode = frm.doc.mode || "Replace";
			frappe.confirm(
				__("{0} item codes from this file? This runs in the background.", [mode]),
				() => run(frm, "start")
			);
		}).addClass("btn-primary");
	},
});

function run(frm, method) {
	if (!frm.doc.spreadsheet) {
		frappe.msgprint(__("Attach a spreadsheet first."));
		return;
	}

	const call = () => {
		if (method === "preview") frappe.dom.freeze(__("Analysing spreadsheet..."));
		frappe.call({
			method: "azzir_fleet.item_code_import." + method,
			args: {
				file_url: frm.doc.spreadsheet,
				sheet: frm.doc.sheet_name,
				mode: (frm.doc.mode || "Replace").toLowerCase(),
			},
			always: () => frappe.dom.unfreeze(),
			callback: (r) => {
				frm.reload_doc(); // safe now — inputs were saved first
				if (method === "preview") {
					frappe.msgprint({
						title: __("Dry Run"),
						message: "<pre>" + frappe.utils.escape_html(r.message || "") + "</pre>",
						indicator: "blue",
					});
				} else {
					frappe.show_alert({
						message: __("Import queued — you'll be notified when it finishes."),
						indicator: "green",
					});
				}
			},
		});
	};

	// Persist the attachment + mode BEFORE running, so reload_doc doesn't wipe them.
	if (frm.is_dirty()) {
		frm.save().then(call);
	} else {
		call();
	}
}
