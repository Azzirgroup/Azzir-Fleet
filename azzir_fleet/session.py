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


# After login a portal user lands on the bare /app (or /apps launcher) — that is what
# we bounce to /sales. We deliberately do NOT touch /desk: typing /desk (or any desk
# page like /desk/item, /desk/user) is a deliberate visit and is always allowed
# through, so a portal user can still reach the desk when they mean to.
_DESK_ROOTS = ("/app", "/apps")


def redirect_portal_users_off_desk():
	"""before_request: send 'Sales Portal' users who land on the bare desk root to the
	/sales portal (their home), while letting them open any SPECIFIC desk page they
	type — /desk/item, /desk/user, /desk/quotation, etc.

	Runs on every request before the page renders, so it catches the desk landing no
	matter how they got there — a fresh login, a Frappe Cloud SSO landing on the desk
	root, or a bookmarked root. The Sales Portal role wins over every other role
	(System Manager included); only the Administrator superuser account is exempt.
	302 (temporary) so nothing is cached if the role is later removed.
	"""
	req = getattr(frappe.local, "request", None)
	if not req:
		return
	# Only the BARE desk root — a deeper path like /desk/item is a page they meant to
	# open. Never /api, /assets, /files, /sales, etc.
	p = (req.path or "").rstrip("/") or "/"
	if p not in _DESK_ROOTS:
		return
	# Escape hatch: ?desk=1 on the root lets a portal user into the desk home on
	# purpose; the client guard then drops an `azzir_desk=1` session cookie so it
	# sticks for the rest of that browser session (cleared when the browser closes).
	try:
		if req.args.get("desk") == "1" or req.cookies.get("azzir_desk") == "1":
			return
	except Exception:
		pass
	user = getattr(frappe.session, "user", None)
	if not user or user in ("Guest", "Administrator"):
		return
	try:
		if SALES_PORTAL_ROLE not in frappe.get_roles(user):
			return
	except Exception:
		return

	from werkzeug.routing import RequestRedirect

	class _TempRedirect(RequestRedirect):
		code = 302

	raise _TempRedirect("/sales")


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


