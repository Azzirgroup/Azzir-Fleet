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

// Restrict the item-row Warehouse link to warehouses the user may SELECT
// (attached to a cost center they are assigned). They still see all in the dialog.
azzir_fleet.set_warehouse_cc_query = function (frm, table) {
	table = table || "items";
	if (!frm.fields_dict[table]) return;
	frm.set_query("warehouse", table, function (doc) {
		return {
			query: "azzir_fleet.warehouse_cc.warehouse_query",
			filters: { company: doc.company },
		};
	});
};

// Sell sister-company stock: only users with a Corporate cost center see the
// "Buy Stock From Sister Company" toggle. Cached per session.
azzir_fleet._can_buy_sister = null;
azzir_fleet.toggle_buy_from_sister = function (frm) {
	if (!frm.fields_dict.azzir_buy_from_sister) return;
	const apply = (can) => {
		frm.toggle_display("azzir_buy_from_sister", !!can);
		if (!can && frm.doc.azzir_buy_from_sister) frm.set_value("azzir_buy_from_sister", 0);
	};
	if (azzir_fleet._can_buy_sister !== null) {
		apply(azzir_fleet._can_buy_sister);
		return;
	}
	frappe.call({
		method: "azzir_fleet.intercompany_sale.user_can_buy_from_sister",
		callback(r) {
			azzir_fleet._can_buy_sister = !!r.message;
			apply(azzir_fleet._can_buy_sister);
		},
	});
};
// The supply warehouse: only warehouses in the chosen sister company that HOLD
// stock of the doc's items, showing the qty.
azzir_fleet.set_supply_wh_query = function (frm) {
	frm.set_query("azzir_supply_warehouse", () => ({
		query: "azzir_fleet.intercompany_sale.supply_warehouse_link_query",
		filters: {
			company: frm.doc.azzir_supply_company || "",
			item_codes: (frm.doc.items || []).map((i) => i.item_code).filter(Boolean),
		},
	}));
};

// When an item is picked, override ERPNext's default-warehouse fetch with a
// warehouse in the user's own cost center. We wait a moment so this runs AFTER
// ERPNext has set the item default (otherwise it would clobber ours).
azzir_fleet.autoset_cc_warehouse = function (frm, cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !row.item_code) return;
	setTimeout(() => {
		const r2 = locals[cdt] && locals[cdt][cdn];
		if (!r2 || !r2.item_code) return;
		frappe.call({
			method: "azzir_fleet.warehouse_cc.user_warehouse_for_item",
			args: { item_code: r2.item_code, company: frm.doc.company },
			callback(r) {
				if (r.message && locals[cdt] && locals[cdt][cdn]) {
					frappe.model.set_value(cdt, cdn, "warehouse", r.message);
				}
			},
		});
	}, 800);
};

// Per-warehouse tree breakdown dialog.
// on_select (optional): fn(warehouse) called when a warehouse is picked. When
// given, each ACTUAL (non-group) warehouse gets a radio; picking one calls
// on_select and closes the dialog — used to set the warehouse on the row.
azzir_fleet.show_stock_dialog = function (item_code, on_select) {
	if (!item_code) return;
	// Pass the current doc so the dialog shows AVAILABLE stock (physical minus what
	// other open invoices have reserved). "" for a brand-new unsaved doc.
	const exclude_invoice =
		(typeof cur_frm !== "undefined" && cur_frm && cur_frm.doc && cur_frm.doc.name) || "";
	frappe.call({
		method: "azzir_fleet.stock_info.get_stock_tree",
		args: { item_code, exclude_invoice },
		callback(r) {
			const rows = r.message || [];
			const names = new Set(rows.map((x) => x.warehouse));
			const by_parent = {};
			rows.forEach((x) => {
				const key = x.parent && names.has(x.parent) ? x.parent : "__root__";
				(by_parent[key] = by_parent[key] || []).push(x);
			});

			function render(node, depth) {
				const icon = node.is_group ? "📁" : "•";
				const weight = node.is_group ? "600" : "400";
				const wh = frappe.utils.escape_html(node.warehouse);
				// A leaf the user may not select (cost center not assigned): show it,
				// but no radio, not clickable, greyed with a lock.
				const locked = on_select && !node.is_group && node.selectable === false;
				// Selector column (only when picking an actual warehouse the user may select).
				let pick = "";
				if (on_select) {
					if (node.is_group) {
						pick = '<span style="display:inline-block; width:22px;"></span>';
					} else if (locked) {
						pick = '<span style="display:inline-block; width:22px;">🔒</span>';
					} else {
						pick = `<input type="radio" name="azzir-wh-pick" class="azzir-wh-pick"
							data-wh="${wh}" style="margin-right:8px; cursor:pointer;">`;
					}
				}
				const clickable = on_select && !node.is_group && !locked;
				const incoming = flt(node.incoming);
				const incoming_html = incoming
					? ` <span style="color:#888; font-weight:400;">(+${format_number(incoming)} ${__("incoming")})</span>`
					: "";
				let html = `<div class="azzir-wh-row" data-wh="${wh}"
					data-group="${node.is_group ? 1 : 0}" data-locked="${locked ? 1 : 0}"
					title="${locked ? __("Not in your cost center — view only") : ""}"
					style="display:flex; align-items:center; justify-content:space-between; padding:5px 0;
					border-bottom:1px solid #f0f0f0; padding-left:${depth * 22}px;
					${locked ? "opacity:0.5;" : ""}${clickable ? "cursor:pointer;" : ""}">
					<span style="font-weight:${weight};">${pick}${icon} ${wh}</span>
					<span style="font-weight:${weight};">${format_number(node.qty)}${incoming_html}</span></div>`;
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
			const total_incoming = roots.reduce((s, x) => s + flt(x.incoming), 0);
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
					<span>${__("Total")}</span><span>${format_number(total)}${
						total_incoming ? ` <span style="color:#888; font-weight:400;">(+${format_number(total_incoming)} ${__("incoming")})</span>` : ""
					}</span></div>
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
					if ($(this).attr("data-group") === "0" && $(this).attr("data-locked") !== "1")
						pick($(this).attr("data-wh"));
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
			azzir_fleet.show_stock_dialog(row.item_code, on_select);
		}
	},
	true
);

$('<style>.grid-row [data-fieldname="azzir_all_stock"]{cursor:pointer;color:#1a73e8;text-decoration:underline;}</style>').appendTo("head");
