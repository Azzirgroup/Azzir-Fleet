// Copyright (c) 2026, Azzir and contributors
// Customer Statement — a self-contained desk page (does NOT use the query-report
// framework, which is broken on Frappe 17-dev). Filters -> table -> print.

frappe.pages["customer-statement"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Customer Statement"),
		single_column: true,
	});

	const company = page.add_field({
		fieldname: "company",
		label: __("Company"),
		fieldtype: "Link",
		options: "Company",
		default: frappe.defaults.get_user_default("Company"),
		reqd: 1,
	});
	const customer = page.add_field({
		fieldname: "customer",
		label: __("Customer"),
		fieldtype: "Link",
		options: "Customer",
		reqd: 1,
	});
	const from_date = page.add_field({
		fieldname: "from_date",
		label: __("From Date"),
		fieldtype: "Date",
		default: frappe.datetime.year_start(),
	});
	const to_date = page.add_field({
		fieldname: "to_date",
		label: __("To Date"),
		fieldtype: "Date",
		default: frappe.datetime.get_today(),
	});

	const $result = $('<div class="cs-result" style="margin-top:20px;"></div>').appendTo(page.main);
	$result.html(`<p class="text-muted">${__("Pick a company and customer, then click Show.")}</p>`);

	let last = null; // last rendered payload, for printing

	function money(v) {
		if (v === undefined || v === null || v === "") return "";
		return format_currency(v, last ? last.currency : null);
	}

	function show() {
		const c = company.get_value();
		const cust = customer.get_value();
		if (!c || !cust) {
			frappe.msgprint(__("Please select both Company and Customer."));
			return;
		}
		$result.html(`<p class="text-muted">${__("Loading...")}</p>`);
		frappe.call({
			method: "azzir_fleet.customer_statement.get_statement",
			args: {
				company: c,
				customer: cust,
				from_date: from_date.get_value() || "",
				to_date: to_date.get_value() || "",
			},
			callback(r) {
				if (!r.message) {
					$result.html(`<p class="text-muted">${__("No data.")}</p>`);
					return;
				}
				last = {
					data: r.message.data || [],
					customer: cust,
					customer_name: r.message.customer_name || "",
					company: c,
					from_date: from_date.get_value(),
					to_date: to_date.get_value(),
					currency: r.message.currency || null,
				};
				render();
			},
		});
	}

	function statement_html(forPrint) {
		const rows = (last.data || [])
			.map((row) => {
				const bold =
					row.voucher_type === __("Opening Balance") ||
					row.voucher_type === __("Closing Balance");
				const style = bold ? ' style="font-weight:700;"' : "";
				return `<tr${style}>
					<td>${row.posting_date ? frappe.datetime.str_to_user(row.posting_date) : ""}</td>
					<td>${frappe.utils.escape_html(row.voucher_type || "")}</td>
					<td>${frappe.utils.escape_html(row.voucher_no || "")}</td>
					<td>${frappe.utils.escape_html(row.remarks || "")}</td>
					<td class="text-right">${money(row.debit)}</td>
					<td class="text-right">${money(row.credit)}</td>
					<td class="text-right">${money(row.balance)}</td>
				</tr>`;
			})
			.join("");

		const header = `
			<div style="text-align:center; margin-bottom:12px;">
				<h3 style="margin:0;">${__("Customer Statement")}</h3>
				<div><b>${frappe.utils.escape_html(last.customer_name || last.customer)}</b></div>
				<div>${frappe.utils.escape_html(last.company || "")}</div>
				<div>${__("Period")}: ${last.from_date ? frappe.datetime.str_to_user(last.from_date) : ""} &mdash; ${last.to_date ? frappe.datetime.str_to_user(last.to_date) : ""}</div>
			</div>`;

		return `${forPrint ? header : ""}
			<table class="table table-bordered" style="font-size:13px;">
				<thead>
					<tr>
						<th style="width:11%;">${__("Date")}</th>
						<th style="width:15%;">${__("Voucher Type")}</th>
						<th style="width:19%;">${__("Voucher No")}</th>
						<th style="width:23%;">${__("Remarks")}</th>
						<th class="text-right" style="width:10%;">${__("Debit")}</th>
						<th class="text-right" style="width:10%;">${__("Credit")}</th>
						<th class="text-right" style="width:12%;">${__("Balance")}</th>
					</tr>
				</thead>
				<tbody>${rows}</tbody>
			</table>`;
	}

	function render() {
		$result.html(statement_html(false));
	}

	function print_statement() {
		if (!last) {
			frappe.msgprint(__("Show the statement first."));
			return;
		}
		const w = window.open("", "_blank");
		w.document.write(`<html><head><title>${__("Customer Statement")}</title>
			<style>
				body{font-family:sans-serif; padding:20px; color:#000;}
				table{width:100%; border-collapse:collapse;}
				th,td{border:1px solid #999; padding:5px 7px;}
				.text-right{text-align:right;}
				thead th{background:#f5f5f5;}
			</style></head><body>${statement_html(true)}</body></html>`);
		w.document.close();
		w.focus();
		setTimeout(() => w.print(), 300);
	}

	page.set_primary_action(__("Show"), show, "octicon octicon-search");
	page.add_button(__("Print"), print_statement, "octicon octicon-file-pdf");
};
