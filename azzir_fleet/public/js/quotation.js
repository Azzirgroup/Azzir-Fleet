// Copyright (c) 2026, Azzir and contributors
// For license information, please see license.txt
//
// Live stock on the Quotation items grid:
//  - "Stock (This WH)"  = item stock in the row's warehouse
//  - "Stock (All WH)"   = total across all warehouses; click it for a per-warehouse
//                         breakdown grouped by the warehouse tree.

frappe.provide("azzir_fleet");

frappe.ui.form.on("Quotation Item", {
	item_code(frm, cdt, cdn) {
		azzir_fleet.fetch_row_stock(cdt, cdn);
	},
	warehouse(frm, cdt, cdn) {
		azzir_fleet.fetch_row_stock(cdt, cdn);
	},
});

azzir_fleet.fetch_row_stock = function (cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !row.item_code) return;
	frappe.call({
		method: "azzir_fleet.stock_info.get_item_stock",
		args: { item_code: row.item_code, warehouse: row.warehouse || "" },
		callback(r) {
			if (!r.message) return;
			frappe.model.set_value(cdt, cdn, "azzir_wh_stock", r.message.wh_stock);
			frappe.model.set_value(cdt, cdn, "azzir_all_stock", r.message.all_stock);
		},
	});
};

// Click the "Stock (All WH)" cell -> per-warehouse breakdown dialog.
$(document).on("click", '.grid-row [data-fieldname="azzir_all_stock"]', function () {
	const cdn = $(this).closest("[data-name]").attr("data-name");
	const row = cdn && locals["Quotation Item"] && locals["Quotation Item"][cdn];
	if (row && row.item_code) azzir_fleet.show_stock_dialog(row.item_code);
});

azzir_fleet.show_stock_dialog = function (item_code) {
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

// Visual cue that the All-WH cell is clickable.
$('<style>.grid-row [data-fieldname="azzir_all_stock"]{cursor:pointer;color:#1a73e8;text-decoration:underline;}</style>').appendTo("head");
