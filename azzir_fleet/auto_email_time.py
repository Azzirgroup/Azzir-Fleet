# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Per-report send time for Auto Email Report.

ERPNext's ``send_daily`` fires every Daily / Weekdays / Weekly report ONCE a day, at the
scheduler's daily time — there is no per-report time. This adds a **Send At** time field:
a report with it set goes out at that time of day instead.

How it works:
* ``AutoEmailReport.send`` is overridden so a SCHEDULED send only proceeds at/after the
  chosen time and only once per day (tracked in ``azzir_last_sent_date``). A manual
  "Send Now" (which runs inside an HTTP request) bypasses the gate and sends immediately.
* A frequent app scheduler (``send_timed_reports``, every 15 min) keeps calling ``send``
  through the day, so the report leaves close to its chosen time — ERPNext's once-a-day
  ``send_daily`` cannot do that on its own.

Reports WITHOUT a Send At time are untouched: ERPNext's default schedule still sends them.
"""

import calendar
import datetime

import frappe
from frappe.utils import get_time, now_datetime, today
from frappe.email.doctype.auto_email_report.auto_email_report import AutoEmailReport

_SCHED_FREQ = ("Daily", "Weekdays", "Weekly")


def _as_time(value) -> datetime.time | None:
	"""A Time field may come back as a timedelta (how Frappe stores it), a time, or a
	string — normalise to datetime.time."""
	if value is None or value == "":
		return None
	if isinstance(value, datetime.time):
		return value
	if isinstance(value, datetime.timedelta):
		secs = int(value.total_seconds())
		return datetime.time((secs // 3600) % 24, (secs // 60) % 60, secs % 60)
	try:
		return get_time(value)
	except Exception:
		return None


def blocked_by_time_gate(doc) -> bool:
	"""True when a SCHEDULED send should be held back right now — the chosen time has not
	arrived yet, or it was already sent today. Assumes a Send At time is set."""
	if doc.get("azzir_last_sent_date") and str(doc.get("azzir_last_sent_date")) == today():
		return True
	send_t = _as_time(doc.get("azzir_send_time"))
	if send_t and now_datetime().time() < send_t:
		return True
	return False


def due_today(doc) -> bool:
	"""Honour the frequency's own day rules (Weekdays skip the weekend; Weekly only on the
	chosen day)."""
	day = calendar.day_name[now_datetime().weekday()]
	if doc.frequency == "Weekdays" and day in ("Saturday", "Sunday"):
		return False
	if doc.frequency == "Weekly" and doc.get("day_of_week") != day:
		return False
	return True


class AzzirAutoEmailReport(AutoEmailReport):
	def send(self):
		send_time = self.get("azzir_send_time")
		# A scheduled run has no HTTP request; a manual "Send Now" does — let it through.
		scheduled = not getattr(frappe.local, "request", None)
		if send_time and scheduled and blocked_by_time_gate(self):
			return
		super().send()
		if send_time and scheduled:
			self.db_set("azzir_last_sent_date", today(), update_modified=False, commit=True)


def send_timed_reports():
	"""App scheduler (every 15 min): push out any time-scheduled Auto Email Report whose
	time has arrived today. ``send`` itself enforces the time + once-a-day guard, so this
	only has to keep trying and respect the frequency's day rules."""
	names = frappe.get_all(
		"Auto Email Report",
		filters={"enabled": 1, "frequency": ["in", _SCHED_FREQ]},
		pluck="name",
	)
	for name in names:
		doc = frappe.get_doc("Auto Email Report", name)
		if not doc.get("azzir_send_time") or not due_today(doc):
			continue
		try:
			doc.send()
		except Exception:
			doc.log_error(f"Failed timed send of Auto Email Report {name}")
