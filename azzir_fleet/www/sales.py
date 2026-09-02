import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/sales"
		raise frappe.Redirect

	from azzir_fleet.session import is_portal_restricted

	context.csrf_token = frappe.sessions.get_csrf_token()
	context.boot = {
		"csrf_token": context.csrf_token,
		"sitename": frappe.local.site,
		"user": frappe.session.user,
		# 'Sales Portal' users are locked out of the desk, so the app hides its
		# "Desk →" link for them rather than offering a link that only 302s back.
		"portal_only": is_portal_restricted(),
	}
	frappe.db.commit()
	return context
