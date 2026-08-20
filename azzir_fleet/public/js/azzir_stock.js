// Copyright (c) 2026, Azzir and contributors
// Shared stock helpers: fetch per-row stock + per-warehouse tree dialog.
// Used by Quotation, Sales Invoice, Stock Entry, ...

frappe.provide("azzir_fleet");

// Fill azzir_wh_stock (row warehouse) + azzir_all_stock (all warehouses) on a row.
azzir_fleet.fetch_row_stock = function (cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !row.item_code) return;
	frappe.call({
		method: "azzir_fleet.stock_info.get_item_stock",
		args: { item_code: row.item_code, warehouse: row.warehouse || "" },
		callback(r) {
			if (!r.message) return;
			if (frappe.meta.has_field(cdt, "azzir_wh_stock")) {
				frappe.model.set_value(cdt, cdn, "azzir_wh_stock", r.message.wh_stock);
			}
			if (frappe.meta.has_field(cdt, "azzir_all_stock")) {
				frappe.model.set_value(cdt, cdn, "azzir_all_stock", r.message.all_stock);
			}
		},
	});
};

// Sales rows are region-only. ERPNext auto-fills an item's default BIN when the
// item is picked; drop it so the field stays empty until a group (region) is
// chosen. Keeps groups and fetches their stock.
azzir_fleet.on_sales_warehouse = function (cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !row.warehouse) {
		azzir_fleet.fetch_row_stock(cdt, cdn);
		return;
	}
	frappe.db.get_value("Warehouse", row.warehouse, "is_group").then((r) => {
		const is_group = r && r.message ? cint(r.message.is_group) : 1;
		if (!is_group) {
			frappe.model.set_value(cdt, cdn, "warehouse", ""); // strip auto-filled bin
		} else {
			azzir_fleet.fetch_row_stock(cdt, cdn);
		}
	});
};

// Call from a sales row's item_code trigger. ERPNext auto-fills the item's
// default BIN a moment after selection (via get_item_details, which doesn't fire
// the warehouse trigger), so we poll the row and clear it once it lands. Only a
// leaf (bin) is removed — a group (region) the user picked is kept.
azzir_fleet.strip_leaf_after_autofill = function (cdt, cdn) {
	const attempt = (tries) => {
		const row = locals[cdt] && locals[cdt][cdn];
		if (!row) return;
		if (row.warehouse) {
			frappe.db.get_value("Warehouse", row.warehouse, "is_group").then((r) => {
				const is_group = r && r.message ? cint(r.message.is_group) : 1;
				if (!is_group) frappe.model.set_value(cdt, cdn, "warehouse", "");
			});
		} else if (tries > 0) {
			setTimeout(() => attempt(tries - 1), 400); // auto-fill hasn't landed yet
		}
	};
	setTimeout(() => attempt(3), 400);
};

// Per-warehouse tree breakdown dialog.
// on_select (optional): fn(warehouse) called when a warehouse is picked. When
// given, each ACTUAL (non-group) warehouse gets a radio; picking one calls
// on_select and closes the dialog — used to set the warehouse on the row.
azzir_fleet.show_stock_dialog = function (item_code, on_select, opts) {
	if (!item_code) return;
	opts = opts || {};
	// groups_only: show ONLY group (region) warehouses and let the user pick one —
	// the sales view (Quotation / Sales Invoice), where bins must stay hidden.
	const groups_only = !!opts.groups_only;
	// Pass the current doc so the dialog shows AVAILABLE stock (physical minus what
	// other open invoices have reserved). "" for a brand-new unsaved doc.
	const exclude_invoice =
		(typeof cur_frm !== "undefined" && cur_frm && cur_frm.doc && cur_frm.doc.name) || "";
	frappe.call({
		method: "azzir_fleet.stock_info.get_stock_tree",
		args: { item_code, exclude_invoice, groups_only: groups_only ? 1 : 0 },
		callback(r) {
			const rows = r.message || [];
			const names = new Set(rows.map((x) => x.warehouse));
			const by_parent = {};
			rows.forEach((x) => {
				const key = x.parent && names.has(x.parent) ? x.parent : "__root__";
				(by_parent[key] = by_parent[key] || []).push(x);
			});

			// Which rows are selectable: group rows in sales (groups_only) mode,
			// leaf rows otherwise.
			const can_pick = (node) => (groups_only ? !!node.is_group : !node.is_group);

			function render(node, depth) {
				const icon = node.is_group ? "📁" : "•";
				const weight = node.is_group ? "600" : "400";
				const wh = frappe.utils.escape_html(node.warehouse);
				const pickable = can_pick(node);
				// Selector column (only when picking, and only for selectable rows).
				let pick = "";
				if (on_select) {
					pick = pickable
						? `<input type="radio" name="azzir-wh-pick" class="azzir-wh-pick"
							data-wh="${wh}" style="margin-right:8px; cursor:pointer;">`
						: '<span style="display:inline-block; width:22px;"></span>';
				}
				let html = `<div class="azzir-wh-row" data-wh="${wh}" data-pick="${pickable ? 1 : 0}"
					style="display:flex; align-items:center; justify-content:space-between; padding:5px 0;
					border-bottom:1px solid #f0f0f0; padding-left:${depth * 22}px;
					${on_select && pickable ? "cursor:pointer;" : ""}">
					<span style="font-weight:${weight};">${pick}${icon} ${wh}</span>
					<span style="font-weight:${weight};">${format_number(node.qty)}</span></div>`;
				(by_parent[node.warehouse] || []).forEach((c) => (html += render(c, depth + 1)));
				return html;
			}

			const roots = by_parent["__root__"] || [];
			// Group the root warehouses by company. With one company this shows a
			// single header; a "Group Stock" user sees each company (HCL, HPL, …).
			const companies = [...new Set(roots.map((x) => x.company || ""))].sort();
			let body = "";
			companies.forEach((co) => {
				if (companies.length > 1 || co) {
					body += `<div style="font-weight:700; background:#f4f6f8; padding:6px 8px;
						margin-top:6px; border-bottom:2px solid #000;">🏢 ${frappe.utils.escape_html(co || __("Company"))}</div>`;
				}
				roots.filter((rt) => (rt.company || "") === co).forEach((rt) => (body += render(rt, 0)));
			});
			const total = roots.reduce((s, x) => s + flt(x.qty), 0);
			if (!body) body = `<p class="text-muted">${__("No available stock in any warehouse.")}</p>`;

			const d = new frappe.ui.Dialog({
				title: __("Available Stock by Warehouse — {0}", [item_code]),
				size: "large",
			});
			const hint = on_select
				? `<p class="text-muted" style="margin:0 0 8px;">${__("Select a warehouse to set it on this row.")}</p>`
				: "";
			d.$body.html(`<div style="max-height:440px; overflow:auto; font-size:13px;">
				${hint}${body}
				<div style="display:flex; justify-content:space-between; padding:8px 0;
					border-top:2px solid #000; font-weight:700; margin-top:6px;">
					<span>${__("Total")}</span><span>${format_number(total)}</span></div>
			</div>`);

			if (on_select) {
				const pick = (wh) => {
					if (!wh) return;
					on_select(wh);
					d.hide();
				};
				// Clicking the radio, or anywhere on an actual-warehouse row, selects it.
				d.$body.on("click", ".azzir-wh-pick", function (e) {
					e.stopPropagation();
					pick($(this).attr("data-wh"));
				});
				d.$body.on("click", ".azzir-wh-row", function () {
					if ($(this).attr("data-pick") === "1") pick($(this).attr("data-wh"));
				});
			}

			d.show();
		},
	});
};

// Click any "Stock (All WH)" grid cell (any doctype) -> the tree dialog.
// Capture phase + stopPropagation so it fires BEFORE Frappe opens the row editor.
document.addEventListener(
	"click",
	function (e) {
		const cell =
			e.target && e.target.closest && e.target.closest('.grid-row [data-fieldname="azzir_all_stock"]');
		if (!cell) return;
		e.stopPropagation();
		e.preventDefault();
		const nameEl = cell.closest("[data-name]");
		const cdn = nameEl && nameEl.getAttribute("data-name");
		const wrapper = cell.closest(".frappe-control");
		const grid_field = wrapper && wrapper.fieldobj;
		const child_dt = grid_field && grid_field.df && grid_field.df.options;
		const row = child_dt && cdn && locals[child_dt] && locals[child_dt][cdn];
		if (row && row.item_code) {
			const on_select = frappe.meta.has_field(child_dt, "warehouse")
				? (wh) => frappe.model.set_value(child_dt, cdn, "warehouse", wh)
				: undefined;
			// Sales lines pick a region (group); everywhere else picks a bin (leaf).
			const groups_only =
				child_dt === "Quotation Item" || child_dt === "Sales Invoice Item";
			azzir_fleet.show_stock_dialog(row.item_code, on_select, { groups_only });
		}
	},
	true
);

$('<style>.grid-row [data-fieldname="azzir_all_stock"]{cursor:pointer;color:#1a73e8;text-decoration:underline;}</style>').appendTo("head");
