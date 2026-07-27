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


def enforce_session_limit(login_manager=None):
	user = frappe.session.user
	if not user or user in ("Guest", "Administrator"):
		return
	# force=False -> keeps the `simultaneous_sessions` most recent sessions.
	clear_sessions(user, keep_current=True, force=False)
