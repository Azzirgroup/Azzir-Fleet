# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Cap concurrent logins per user (phone + desktop) without hard single-session.

Frappe's System Settings.deny_multiple_sessions calls clear_sessions(force=True),
which ignores User.simultaneous_sessions and kills EVERY other session — so users
got logged out the moment they signed in on a second device, and their open tab
then hit `search_link` as Guest ("Method Not Allowed").

Instead we leave that flag off and enforce the limit here on login with
force=False, which honours User.simultaneous_sessions and only drops the OLDEST
sessions beyond it."""

import frappe
from frappe.sessions import clear_sessions

MAX_SESSIONS = 2

SALES_PORTAL_ROLE = "Sales Portal"


def enforce_session_limit(login_manager=None):
	user = frappe.session.user
	if not user or user in ("Guest", "Administrator"):
		return
	# force=False -> keeps the `simultaneous_sessions` most recent sessions.
	clear_sessions(user, keep_current=True, force=False)


def route_portal_users_on_login(login_manager=None):
	"""Send users with the 'Sales Portal' role straight to the /sales app after
	login; everyone else lands on their normal desk dashboard.

	Runs during on_session_creation, before Frappe computes the post-login
	home page, so setting `flags.home_page` here wins over the default
	workspace / desk redirect."""
	if frappe.session.user == "Guest":
		return
	if SALES_PORTAL_ROLE in frappe.get_roles():
		frappe.local.flags.home_page = "sales"
		# A user's default workspace otherwise overrides the home page (frappe
		# get_home_page), sending them to the desk instead of the portal. Clear it
		# so the portal redirect always wins, on every login path.
		if frappe.db.get_value("User", frappe.session.user, "default_workspace"):
			frappe.db.set_value(
				"User", frappe.session.user, "default_workspace", None, update_modified=False
			)


