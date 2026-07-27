// Copyright (c) 2026, Azzir and contributors
// Compatibility shim for Frappe 17.0.0-dev.
//
// query_report.js loads a report with:
//     frappe.model.with_doctype(this.report_doc?.ref_doctype)
// On this build `getdoctype` made its `doctype` arg a REQUIRED positional, so a
// falsy ref_doctype (empty/undefined) sends `{with_parent: 1}` with no doctype
// and the server 500s:
//     TypeError: getdoctype() missing 1 required positional argument: 'doctype'
// which kills the whole report page.
//
// Guard it: when there's no doctype, resolve immediately (exactly what the
// original does when the doctype's meta is already cached) instead of hitting
// the server. Everything downstream already guards on report_doc.ref_doctype.
frappe.provide("frappe.model");
(function () {
	const _with_doctype = frappe.model.with_doctype;
	if (!_with_doctype || _with_doctype.__azzir_guarded) return;

	frappe.model.with_doctype = function (doctype, callback, async) {
		if (!doctype) {
			callback && callback();
			return Promise.resolve();
		}
		return _with_doctype.call(this, doctype, callback, async);
	};
	frappe.model.with_doctype.__azzir_guarded = true;
})();
