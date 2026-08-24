# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Bulk-load Item alternative part numbers into the azzir_alias_codes child table
(Item Code Entry) using batched SQL — built for tens of thousands of rows.

For each Item in the spreadsheet it REPLACES that item's code table with the
sheet's rows: the item's own code is kept as the single Primary (so the item is
never renamed) and the alternatives are added. Codes already owned by a DIFFERENT
item are skipped and reported (the app forbids reusing a code).

Spreadsheet columns (row 1 = header):
    ID | azzir_alias_codes.code | azzir_alias_codes.is_primary | azzir_alias_codes.source

Used by both the CLI script (import_item_codes.py) and the "Item Code Import"
DocType (upload + run from the desk, incl. on Frappe Cloud)."""

import frappe
from frappe.utils import now_datetime

CHILD_DT = "Item Code Entry"
PARENT_FIELD = "azzir_alias_codes"
DELETE_BATCH = 500
INSERT_CHUNK = 5000
DEFAULT_SHEET = "Item Codes"


def parse_workbook(path_or_stream, sheet=None):
	"""{item_id: [(code, is_primary, source), ...]} preserving row order + the id order."""
	import openpyxl

	wb = openpyxl.load_workbook(path_or_stream, read_only=True, data_only=True)
	name = sheet or DEFAULT_SHEET
	ws = wb[name] if name in wb.sheetnames else wb.worksheets[0]
	rows = ws.iter_rows(min_row=1, values_only=True)
	next(rows, None)  # header
	groups, order = {}, []
	for r in rows:
		if not r or r[0] in (None, ""):
			continue
		item = str(r[0]).strip()
		code = str(r[1]).strip() if len(r) > 1 and r[1] is not None else ""
		if not code:
			continue
		is_primary = 1 if (len(r) > 2 and r[2] in (1, "1", True)) else 0
		source = (r[3] if len(r) > 3 and r[3] else "Manual")
		if item not in groups:
			groups[item] = []
			order.append(item)
		groups[item].append((code, is_primary, source))
	return groups, order


def build_plan(groups, order):
	"""Resolve conflicts. Returns (import_items, desired, stats).
	desired = {item: [(code, is_primary, source, idx), ...]}."""
	item_names = set(frappe.db.sql_list("select name from `tabItem`"))
	import_items = [i for i in order if i in item_names]
	missing = [i for i in order if i not in item_names]
	import_set = set(import_items)

	# Codes reserved by items NOT being reimported: their own name + their aliases.
	reserved = {}
	for nm in item_names:
		if nm not in import_set:
			reserved[nm] = nm
	for code, parent in frappe.db.sql(
		"select code, parent from `tabItem Code Entry` where parenttype = 'Item'"
	):
		if parent not in import_set:
			reserved.setdefault(code, parent)

	assigned = {}
	desired = {}
	conflicts = []
	for item in import_items:
		out, seen, idx = [], set(), 0
		for code, is_primary, source in groups[item]:
			if code in seen:
				continue
			if code in reserved and reserved[code] != item:
				conflicts.append((item, code, "used by %s" % reserved[code]))
				continue
			if code in assigned and assigned[code] != item:
				conflicts.append((item, code, "already given to %s" % assigned[code]))
				continue
			seen.add(code)
			assigned[code] = item
			idx += 1
			out.append((code, 1 if code == item else 0, source or "Manual", idx))
		# Guarantee the item's own code is present as the single Primary.
		if item not in seen:
			idx += 1
			out.append((item, 1, "Primary", idx))
		if not any(p for (_, p, _, _) in out):
			for n, (c, p, s, i) in enumerate(out):
				if c == item:
					out[n] = (c, 1, s, i)
					break
		desired[item] = out

	stats = {
		"file_items": len(order),
		"existing": len(import_items),
		"missing": missing,
		"conflicts": conflicts,
		"rows": sum(len(v) for v in desired.values()),
	}
	return import_items, desired, stats


def apply_plan(import_items, desired, progress=None):
	"""Replace each item's code table with the desired rows, in batches."""
	now = now_datetime()
	for i in range(0, len(import_items), DELETE_BATCH):
		chunk = import_items[i:i + DELETE_BATCH]
		ph = ", ".join(["%s"] * len(chunk))
		frappe.db.sql(
			"delete from `tabItem Code Entry` where parenttype = 'Item' and parent in (%s)" % ph,
			tuple(chunk),
		)
		frappe.db.commit()
		if progress:
			progress("deleted %d/%d items" % (min(i + DELETE_BATCH, len(import_items)), len(import_items)))

	fields = [
		"name", "creation", "modified", "modified_by", "owner", "docstatus",
		"idx", "parent", "parentfield", "parenttype", "code", "is_primary", "source", "changed_on",
	]
	values = []
	for item, out in desired.items():
		for code, is_primary, source, idx in out:
			values.append((
				frappe.generate_hash(length=10), now, now, "Administrator", "Administrator", 0,
				idx, item, PARENT_FIELD, "Item", code, is_primary, source, now,
			))
	for i in range(0, len(values), INSERT_CHUNK):
		frappe.db.bulk_insert(CHILD_DT, fields, values[i:i + INSERT_CHUNK])
		frappe.db.commit()
		if progress:
			progress("inserted %d/%d rows" % (min(i + INSERT_CHUNK, len(values)), len(values)))
	return len(values)


def summarize(stats, applied_rows=None):
	"""Human-readable summary string for the DocType / CLI."""
	lines = [
		"Items in file:  %d" % stats["file_items"],
		"Existing items: %d  (updated)" % stats["existing"],
		"Missing items:  %d  (skipped)" % len(stats["missing"]),
		"Code conflicts: %d  (skipped)" % len(stats["conflicts"]),
		"Rows planned:   %d" % stats["rows"],
	]
	if applied_rows is not None:
		lines.append("Rows written:   %d" % applied_rows)
	if stats["missing"]:
		lines.append("\nMissing (first 20):")
		lines += ["  - %s" % m for m in stats["missing"][:20]]
	if stats["conflicts"]:
		lines.append("\nConflicts (first 20):")
		lines += ["  - %s : %s (%s)" % c for c in stats["conflicts"][:20]]
	return "\n".join(lines)


def run_from_path(path, commit=False, progress=None):
	"""End-to-end from a file path. Returns (stats, applied_rows)."""
	groups, order = parse_workbook(path)
	import_items, desired, stats = build_plan(groups, order)
	applied = None
	if commit:
		applied = apply_plan(import_items, desired, progress=progress)
		frappe.db.commit()
	return stats, applied


# --------------------------------------------------------------------------- #
# Desk (Item Code Import DocType) — upload a file and run from the browser.
# --------------------------------------------------------------------------- #
def _file_path(file_url):
	if not file_url:
		frappe.throw(frappe._("Attach a spreadsheet first."))
	return frappe.get_doc("File", {"file_url": file_url}).get_full_path()


@frappe.whitelist()
def preview(file_url: str, sheet: str | None = None) -> str:
	"""Dry run: parse + plan, return a summary. Writes nothing."""
	groups, order = parse_workbook(_file_path(file_url), sheet)
	_, _, stats = build_plan(groups, order)
	summary = summarize(stats)
	frappe.db.set_single_value("Item Code Import", "result", summary)
	frappe.db.set_single_value("Item Code Import", "status", "Dry run: %d rows planned" % stats["rows"])
	return summary


@frappe.whitelist()
def start(file_url: str, sheet: str | None = None) -> str:
	"""Queue the real import as a background job (handles large files)."""
	_file_path(file_url)  # validate now
	frappe.db.set_single_value("Item Code Import", "status", "Queued...")
	frappe.enqueue(
		"azzir_fleet.item_code_import.background_run",
		queue="long",
		timeout=3600,
		file_url=file_url,
		sheet=sheet,
		user=frappe.session.user,
	)
	return "queued"


def background_run(file_url, sheet=None, user=None):
	"""Worker job: apply the import and record the result on the Single doctype."""
	try:
		groups, order = parse_workbook(_file_path(file_url), sheet)
		import_items, desired, stats = build_plan(groups, order)
		applied = apply_plan(import_items, desired)
		frappe.db.commit()
		summary = summarize(stats, applied)
		frappe.db.set_single_value("Item Code Import", "result", summary)
		frappe.db.set_single_value("Item Code Import", "status", "Completed: %d rows written" % applied)
		frappe.db.commit()
		if user:
			frappe.publish_realtime(
				"msgprint",
				{"message": frappe._("Item code import complete: %d rows.") % applied, "title": "Done"},
				user=user,
			)
	except Exception:
		frappe.db.rollback()
		frappe.db.set_single_value("Item Code Import", "status", "Failed — see Error Log")
		frappe.db.commit()
		frappe.log_error(title="Item Code Import failed")
		if user:
			frappe.publish_realtime(
				"msgprint",
				{"message": frappe._("Item code import failed — check Error Log."), "title": "Failed"},
				user=user,
			)
