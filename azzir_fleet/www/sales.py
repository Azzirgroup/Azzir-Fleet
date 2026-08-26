import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/sales"
		raise frappe.Redirect

	context.csrf_token = frappe.sessions.get_csrf_token()
	context.boot = {
		"csrf_token": context.csrf_token,
		"sitename": frappe.local.site,
		"user": frappe.session.user,
	}
	frappe.db.commit()
	return context
