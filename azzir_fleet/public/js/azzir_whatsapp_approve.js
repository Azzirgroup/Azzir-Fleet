// Copyright (c) 2026, Azzir and contributors
// Extends the whatsapp_integration app FROM azzir_fleet (no changes to that app).
//
// On a below-cost document that is PENDING APPROVAL, add a button that WhatsApps
// the manager the document PDF *plus* an "Approve" link that opens it in ERPNext.
// It reuses the WhatsApp client's own sender list and send API, and resolves the
// number the same way the client does (doc phone -> Customer mobile).

const AZZIR_WA_DOCTYPES = ["Quotation", "Sales Invoice", "Delivery Note"];

function azzir_wa_available() {
	try {
		if (frappe.boot && frappe.boot.versions) return !!frappe.boot.versions.whatsapp_integration;
	} catch (e) {}
	return true; // can't tell -> assume present (it is on sites that use this)
}

// Only relevant while the doc is waiting for approval (the below-cost workflow
// parks it at a "Pending …" state, docstatus still 0).
function azzir_wa_pending(frm) {
	return frm.doc.docstatus === 0 && /pending/i.test(frm.doc.workflow_state || "");
}

function azzir_wa_doc_phone(doc) {
	return doc.contact_mobile || doc.customer_mobile_no || doc.mobile_no || doc.phone || doc.contact_phone || "";
}

function azzir_wa_open_dialog(frm) {
	frappe.call({
		method: "whatsapp_integration.api.whatsapp.whatsapp.get_whatsapp_senders",
		callback(r) {
			const senders = r.message || [];
			const phone = azzir_wa_doc_phone(frm.doc);
			if (phone) return azzir_wa_dialog(frm, senders, phone);
			if (frm.doc.customer) {
				frappe.db.get_value("Customer", frm.doc.customer, "mobile_no").then((res) => {
					azzir_wa_dialog(frm, senders, (res && res.message && res.message.mobile_no) || "");
				});
			} else {
				azzir_wa_dialog(frm, senders, "");
			}
		},
	});
}

function azzir_wa_dialog(frm, senders, phone) {
	const fields = [];
	if (senders.length) {
		fields.push({
			label: __("Send From"), fieldname: "sender", fieldtype: "Select",
			options: senders.map((s) => s.value),
			default: (senders.find((s) => s.is_default) || senders[0]).value, reqd: 1,
		});
	}
	fields.push(
		{
			label: __("WhatsApp Number"), fieldname: "phone_number", fieldtype: "Data",
			default: phone, reqd: 1, description: __("Include the country code, e.g. 255…"),
		},
		{
			label: __("Note (optional)"), fieldname: "note", fieldtype: "Small Text",
			default: __("This {0} is below buying price and needs your approval.", [frm.doc.doctype]),
		},
	);
	const d = new frappe.ui.Dialog({
		title: __("Send for Approval on WhatsApp"),
		fields,
		primary_action_label: __("Send"),
		primary_action(values) {
			d.hide();
			frappe.dom.freeze(__("Sending on WhatsApp…"));
			frappe.call({
				method: "azzir_fleet.whatsapp_approve.send_with_approve",
				args: {
					doctype: frm.doc.doctype, docname: frm.doc.name,
					phone_number: values.phone_number, sender: values.sender || null, note: values.note || null,
				},
				always: () => frappe.dom.unfreeze(),
				callback() {
					frappe.show_alert({ message: __("Sent on WhatsApp with an approve link."), indicator: "green" });
				},
			});
		},
	});
	d.show();
}

AZZIR_WA_DOCTYPES.forEach((dt) => {
	frappe.ui.form.on(dt, {
		refresh(frm) {
			if (frm.is_new() || !azzir_wa_available() || !azzir_wa_pending(frm)) return;
			frm.add_custom_button(
				__("Send for Approval (WhatsApp)"),
				() => azzir_wa_open_dialog(frm),
				__("WhatsApp"),
			);
		},
	});
});
