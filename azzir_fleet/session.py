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


# Desk page roots a 'Sales Portal' user is locked out of. Matched on the path's
# leading segment, so /app, /app/quotation/QTN-0001, /desk and /desk/item are all
# covered. Deliberately NOT /api, /assets, /files or /printview — the portal
# itself makes those requests and would break without them.
_DESK_ROOTS = ("/app", "/apps", "/desk")


def _is_desk_path(path: str) -> bool:
	"""True for the desk itself and every page under it."""
	p = (path or "").rstrip("/") or "/"
	return any(p == root or p.startswith(root + "/") for root in _DESK_ROOTS)


def is_portal_restricted(user: str | None = None) -> bool:
	"""True when this user is confined to the /sales portal and must not reach the
	desk. The 'Sales Portal' role wins over every other role (System Manager
	included); only the built-in Administrator account is exempt, so a site is
	never left without a way into the desk."""
	user = user or getattr(frappe.session, "user", None)
	if not user or user in ("Guest", "Administrator"):
		return False
	try:
		return SALES_PORTAL_ROLE in frappe.get_roles(user)
	except Exception:
		return False


def redirect_portal_users_off_desk():
	"""before_request: confine 'Sales Portal' users to the /sales portal.

	EVERY desk page is bounced to /sales — the bare root AND any deep link such as
	/app/quotation/QTN-0001 or /desk/user, typed, bookmarked or followed from an
	email. There is no ?desk=1 / cookie escape hatch: the role means 'portal only'.

	Runs on every request before the page renders, so it catches the desk no matter
	how the user got there — a fresh login, a Frappe Cloud SSO landing, or a stale
	desk shell. 302 (temporary) so nothing is cached if the role is later removed.
	"""
	req = getattr(frappe.local, "request", None)
	if not req or not _is_desk_path(getattr(req, "path", "")):
		return
	if not is_portal_restricted():
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
	user = frappe.session.user
	# Administrator is exempt: frappe.get_roles("Administrator") returns EVERY role in
	# the system (not just assigned ones), so a plain role check would wrongly treat
	# Administrator as a portal user and send it to /sales on login.
	if user in ("Guest", "Administrator"):
		return
	# Check the ACTUAL role assignment (Has Role), not get_roles — same reason.
	if frappe.db.exists("Has Role", {"parent": user, "parenttype": "User", "role": SALES_PORTAL_ROLE}):
		frappe.local.flags.home_page = "sales"
		# A user's default workspace otherwise overrides the home page (frappe
		# get_home_page), sending them to the desk instead of the portal. Clear it
		# so the portal redirect always wins, on every login path.
		if frappe.db.get_value("User", frappe.session.user, "default_workspace"):
			frappe.db.set_value(
				"User", frappe.session.user, "default_workspace", None, update_modified=False
			)


