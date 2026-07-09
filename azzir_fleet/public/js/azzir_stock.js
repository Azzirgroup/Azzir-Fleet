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

// Per-warehouse tree breakdown dialog.
azzir_fleet.show_stock_dialog = function (item_code) {
	if (!item_code) return;
	frappe.call({
		method: "azzir_fleet.stock_info.get_stock_tree",
		args: { item_code },
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
				let html = `<div style="display:flex; justify-content:space-between; padding:5px 0;
					border-bottom:1px solid #f0f0f0; padding-left:${depth * 22}px;">
					<span style="font-weight:${weight};">${icon} ${frappe.utils.escape_html(node.warehouse)}</span>
					<span style="font-weight:${weight};">${format_number(node.qty)}</span></div>`;
				(by_parent[node.warehouse] || []).forEach((c) => (html += render(c, depth + 1)));
				return html;
			}

			const roots = by_parent["__root__"] || [];
			let body = roots.map((rt) => render(rt, 0)).join("");
			const total = roots.reduce((s, x) => s + flt(x.qty), 0);
			if (!body) body = `<p class="text-muted">${__("No stock in any warehouse.")}</p>`;

			const d = new frappe.ui.Dialog({
				title: __("Stock by Warehouse — {0}", [item_code]),
				size: "large",
			});
			d.$body.html(`<div style="max-height:420px; overflow:auto; font-size:13px;">
				${body}
				<div style="display:flex; justify-content:space-between; padding:8px 0;
					border-top:2px solid #000; font-weight:700; margin-top:6px;">
					<span>${__("Total")}</span><span>${format_number(total)}</span></div>
			</div>`);
			d.show();
		},
	});
};

// Click any "Stock (All WH)" grid cell (any doctype) -> the tree dialog.
$(document).on("click", '.grid-row [data-fieldname="azzir_all_stock"]', function () {
	const cdn = $(this).closest("[data-name]").attr("data-name");
	const wrapper = $(this).closest(".frappe-control").get(0);
	const grid_field = wrapper && wrapper.fieldobj;
	const child_dt = grid_field && grid_field.df && grid_field.df.options;
	const row = child_dt && cdn && locals[child_dt] && locals[child_dt][cdn];
	if (row && row.item_code) azzir_fleet.show_stock_dialog(row.item_code);
});

$('<style>.grid-row [data-fieldname="azzir_all_stock"]{cursor:pointer;color:#1a73e8;text-decoration:underline;}</style>').appendTo("head");
