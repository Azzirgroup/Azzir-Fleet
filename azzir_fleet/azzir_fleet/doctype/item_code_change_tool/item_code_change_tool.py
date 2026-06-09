# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime
from jinja2.sandbox import SandboxedEnvironment


def _build_env():
	"""Jinja env used to evaluate the user's code format expression."""
	env = SandboxedEnvironment()
	env.filters["zfill"] = lambda value, width=0: str(value).zfill(int(width))
	return env


class ItemCodeChangeTool(Document):
	# ------------------------------------------------------------------ #
	# Item selection
	# ------------------------------------------------------------------ #
	def _get_target_items(self):
		filters = {}
		if self.apply_to == "Filtered":
			if self.item_group:
				filters["item_group"] = self.item_group
			if self.brand:
				filters["brand"] = self.brand
			if self.custom_filters:
				try:
					extra = json.loads(self.custom_filters)
					if isinstance(extra, dict):
						filters.update(extra)
				except Exception:
					frappe.throw(_("Advanced Filters must be valid JSON"))
		if not self.include_disabled:
			filters["disabled"] = 0

		return frappe.get_all(
			"Item",
			filters=filters,
			fields=["*"],
			order_by="item_group asc, brand asc, item_code asc",
		)

	# ------------------------------------------------------------------ #
	# Expression evaluation
	# ------------------------------------------------------------------ #
	def _render_code(self, env, item, counter, idx):
		try:
			template = env.from_string(self.code_expression or "")
			value = template.render(item=item, counter=counter, idx=idx)
		except Exception as e:
			return None, f"Expression error: {e}"
		value = (value or "").strip()
		if not value:
			return None, "Expression produced an empty code"
		return value, None

	def _counter_key(self, item):
		if self.counter_reset == "Per Item Group":
			return item.get("item_group") or "__none__"
		if self.counter_reset == "Per Brand":
			return item.get("brand") or "__none__"
		return "__global__"

	# ------------------------------------------------------------------ #
	# Preview
	# ------------------------------------------------------------------ #
	@frappe.whitelist()
	def generate_preview(self):
		items = self._get_target_items()
		env = _build_env()

		counters = {}
		start = int(self.counter_start or 1)
		seen_new = {}  # new_code -> first item that claimed it
		rename_set = {it["name"] for it in items}

		rows = []
		stats = {"OK": 0, "Duplicate": 0, "Unchanged": 0, "Error": 0}

		for idx, item in enumerate(items):
			key = self._counter_key(item)
			counter = counters.get(key, start)

			old_code = item["name"]
			new_code, err = self._render_code(env, item, counter, idx)
			counters[key] = counter + 1

			row = {"item": old_code, "old_code": old_code, "new_code": new_code or ""}

			if err:
				row["status"], row["message"] = "Error", err
			elif new_code == old_code:
				row["status"], row["message"] = "Unchanged", "New code matches current code"
			elif new_code in seen_new:
				row["status"] = "Duplicate"
				row["message"] = f"Same new code as {seen_new[new_code]}"
			elif self._code_taken(new_code, rename_set):
				row["status"] = "Duplicate"
				row["message"] = "Code already used by another item/alias"
			else:
				row["status"], row["message"] = "OK", ""
				seen_new[new_code] = old_code

			stats[row["status"]] = stats.get(row["status"], 0) + 1
			rows.append(row)

		self.set("preview_items", [])
		for r in rows:
			self.append("preview_items", r)

		self.preview_summary = (
			f"{len(rows)} item(s): "
			f"{stats.get('OK', 0)} OK, {stats.get('Duplicate', 0)} duplicate, "
			f"{stats.get('Unchanged', 0)} unchanged, {stats.get('Error', 0)} error."
		)
		self.status = "Previewed"
		self.save()
		return self.preview_summary

	def _code_taken(self, new_code, rename_set):
		"""True if new_code collides with an item that is NOT being renamed,
		or with an existing alias."""
		if new_code in rename_set:
			# It's an existing item, but it's in our batch and will move away.
			return False
		if frappe.db.exists("Item", new_code):
			return True
		if frappe.db.exists("Item Code Alias", new_code):
			return True
		return False

	# ------------------------------------------------------------------ #
	# Run
	# ------------------------------------------------------------------ #
	@frappe.whitelist()
	def run_changes(self, run_now: int = 0):
		if self.status not in ("Previewed", "Failed"):
			frappe.throw(_("Generate a preview first."))
		if not any(r.status == "OK" for r in self.preview_items):
			frappe.throw(_("Nothing to rename. No rows with status OK."))

		self.status = "Queued"
		self.save()
		frappe.db.commit()

		if frappe.utils.cint(run_now):
			_run_changes_bg(self.name)
		else:
			frappe.enqueue(
				_run_changes_bg,
				queue="long",
				timeout=3600,
				docname=self.name,
				enqueue_after_commit=True,
			)
		return self.status


def _run_changes_bg(docname):
	from frappe.model.rename_doc import rename_doc

	doc = frappe.get_doc("Item Code Change Tool", docname)
	log = []
	done = errors = 0

	for row in doc.preview_items:
		if row.status != "OK":
			continue
		try:
			rename_doc(
				"Item",
				row.old_code,
				row.new_code,
				force=True,
				show_alert=False,
				rebuild_search=False,
			)
			# alias is captured automatically by the after_rename hook;
			# stamp the tool reference for traceability.
			if frappe.db.exists("Item Code Alias", row.old_code):
				frappe.db.set_value(
					"Item Code Alias",
					row.old_code,
					{"change_tool": doc.name, "source": "Change Tool"},
				)
			row.db_set("status", "Done")
			row.db_set("message", f"Renamed to {row.new_code}")
			done += 1
			log.append(f"OK   {row.old_code} -> {row.new_code}")
		except Exception as e:
			row.db_set("status", "Error")
			row.db_set("message", str(e))
			errors += 1
			log.append(f"FAIL {row.old_code} -> {row.new_code}: {e}")
			frappe.db.rollback()

	doc.reload()
	doc.run_log = (
		f"Finished {now_datetime()}\nRenamed: {done}, Errors: {errors}\n\n" + "\n".join(log)
	)
	doc.status = "Completed" if errors == 0 else "Failed"
	doc.save()
	frappe.db.commit()
