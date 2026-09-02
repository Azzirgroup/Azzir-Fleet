(() => {
  // ../azzir_fleet/azzir_fleet/public/js/portal_redirect.js
  (function() {
    try {
      const roles = frappe.boot && frappe.boot.user && frappe.boot.user.roles || [];
      const isPortal = roles.includes("Sales Portal");
      const bypass = roles.includes("System Manager") || roles.includes("Azzir Sales Overseer") || frappe.session.user === "Administrator";
      const onDesk = /^\/app(\/|$)/.test(window.location.pathname.replace(/\/+$/, "") || "/app");
      if (isPortal && !bypass && onDesk) {
        window.location.replace("/sales");
      }
    } catch (e) {
    }
  })();

  // ../azzir_fleet/azzir_fleet/public/js/azzir_compat.js
  frappe.provide("frappe.model");
  (function() {
    const _with_doctype = frappe.model.with_doctype;
    if (!_with_doctype || _with_doctype.__azzir_guarded)
      return;
    frappe.model.with_doctype = function(doctype, callback, async) {
      if (!doctype) {
        callback && callback();
        return Promise.resolve();
      }
      return _with_doctype.call(this, doctype, callback, async);
    };
    frappe.model.with_doctype.__azzir_guarded = true;
  })();

  // ../azzir_fleet/azzir_fleet/public/js/azzir_alias.js
  frappe.provide("azzir_fleet");
  azzir_fleet.DEBUG = true;
  azzir_fleet._handle_select = function(e) {
    const native = e.originalEvent || e;
    const value = native && native.text && native.text.value;
    if (azzir_fleet.DEBUG)
      console.info("[Azzir Fleet] selectcomplete value=", value);
    if (!value)
      return;
    const wrapper = $(this).closest(".frappe-control").get(0);
    const field = wrapper && wrapper.fieldobj;
    if (azzir_fleet.DEBUG)
      console.info(
        "[Azzir Fleet] field=",
        field && field.df && field.df.fieldname,
        "options=",
        field && field.df && field.df.options,
        "doctype=",
        field && field.doctype
      );
    if (!field || !field.df || field.df.options !== "Item" || !field.awesomplete)
      return;
    const data = field.awesomplete.get_item(value) || {};
    const desc = data.description || "";
    const marker = desc.indexOf("\u21BA old code:");
    if (azzir_fleet.DEBUG)
      console.info("[Azzir Fleet] description=", JSON.stringify(desc));
    const can_store = field.doctype && field.docname && frappe.meta.has_field(field.doctype, "azzir_old_code");
    if (marker === -1) {
      if (can_store) {
        frappe.model.set_value(field.doctype, field.docname, "azzir_old_code", "");
      }
      return;
    }
    let old_code = desc.slice(marker + "\u21BA old code:".length);
    const sep = old_code.indexOf(" \xB7 ");
    if (sep !== -1)
      old_code = old_code.slice(0, sep);
    old_code = old_code.trim();
    if (can_store) {
      frappe.model.set_value(field.doctype, field.docname, "azzir_old_code", old_code);
    }
    frappe.show_alert(
      {
        message: __('Old code "{0}" \u2014 same item, now {1}', [old_code, value]),
        indicator: "orange"
      },
      8
    );
  };
  $(document).on("awesomplete-selectcomplete", function(e) {
    azzir_fleet._handle_select.call(e.target, e);
  });
  azzir_fleet._patch_pos = function() {
    if (azzir_fleet._pos_patched)
      return;
    if (typeof erpnext === "undefined" || !erpnext.PointOfSale || !erpnext.PointOfSale.ItemSelector) {
      return;
    }
    const proto = erpnext.PointOfSale.ItemSelector.prototype;
    const orig_get_items = proto.get_items;
    proto.get_items = function(opts) {
      const promise = orig_get_items.call(this, opts);
      const term = opts && opts.search_term || "";
      if (term && promise && promise.then) {
        promise.then(({ message }) => {
          const items = message && message.items || [];
          const hit = items.find((i) => i.azzir_old_code);
          if (hit) {
            frappe.show_alert(
              {
                message: __('Old code "{0}" \u2014 same item, now {1}', [
                  hit.azzir_old_code,
                  hit.azzir_current_code || hit.item_code
                ]),
                indicator: "orange"
              },
              8
            );
          }
        });
      }
      return promise;
    };
    azzir_fleet._pos_patched = true;
    console.info("[Azzir Fleet] POS alias patch applied");
  };
  azzir_fleet._pos_poll_started = false;
  azzir_fleet._start_pos_poller = function() {
    if (azzir_fleet._pos_poll_started)
      return;
    azzir_fleet._pos_poll_started = true;
    let tries = 0;
    const timer = setInterval(() => {
      azzir_fleet._patch_pos();
      if (azzir_fleet._pos_patched || ++tries > 1200)
        clearInterval(timer);
    }, 500);
  };
  azzir_fleet._start_pos_poller();

  // ../azzir_fleet/azzir_fleet/public/js/azzir_stock.js
  frappe.provide("azzir_fleet");
  azzir_fleet.fetch_row_stock = function(cdt, cdn) {
    const row = locals[cdt] && locals[cdt][cdn];
    if (!row || !row.item_code)
      return;
    frappe.call({
      method: "azzir_fleet.stock_info.get_item_stock",
      args: { item_code: row.item_code, warehouse: row.warehouse || "" },
      callback(r) {
        if (!r.message)
          return;
        if (frappe.meta.has_field(cdt, "azzir_wh_stock")) {
          frappe.model.set_value(cdt, cdn, "azzir_wh_stock", r.message.wh_stock);
        }
        if (frappe.meta.has_field(cdt, "azzir_all_stock")) {
          frappe.model.set_value(cdt, cdn, "azzir_all_stock", r.message.all_stock);
        }
      }
    });
  };
  azzir_fleet.set_warehouse_cc_query = function(frm, table) {
    table = table || "items";
    if (!frm.fields_dict[table])
      return;
    frm.set_query("warehouse", table, function(doc) {
      return {
        query: "azzir_fleet.warehouse_cc.warehouse_query",
        filters: { company: doc.company }
      };
    });
  };
  azzir_fleet._can_buy_sister = null;
  azzir_fleet.toggle_buy_from_sister = function(frm) {
    if (!frm.fields_dict.azzir_buy_from_sister)
      return;
    const apply = (can) => {
      frm.toggle_display("azzir_buy_from_sister", !!can);
      if (!can && frm.doc.azzir_buy_from_sister)
        frm.set_value("azzir_buy_from_sister", 0);
      if (can && frm.is_new() && !frm.doc.azzir_buy_from_sister)
        frm.set_value("azzir_buy_from_sister", 1);
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
      }
    });
  };
  azzir_fleet.set_supply_wh_query = function(frm) {
    frm.set_query("azzir_supply_warehouse", () => ({
      query: "azzir_fleet.intercompany_sale.supply_warehouse_link_query",
      filters: {
        company: frm.doc.azzir_supply_company || "",
        item_codes: (frm.doc.items || []).map((i) => i.item_code).filter(Boolean)
      }
    }));
    frm.set_query("azzir_supply_warehouse", "items", function(doc, cdt, cdn) {
      const row = locals[cdt][cdn] || {};
      return {
        query: "azzir_fleet.intercompany_sale.supply_warehouse_link_query",
        filters: {
          company: row.azzir_supply_company || doc.azzir_supply_company || "",
          item_codes: row.item_code ? [row.item_code] : []
        }
      };
    });
  };
  azzir_fleet.populate_row_supply = function(frm, field) {
    const val = frm.doc[field];
    if (!val)
      return;
    (frm.doc.items || []).forEach((r) => frappe.model.set_value(r.doctype, r.name, field, val));
  };
  azzir_fleet.autoset_cc_warehouse = function(frm, cdt, cdn) {
    const row = locals[cdt] && locals[cdt][cdn];
    if (!row || !row.item_code)
      return;
    setTimeout(() => {
      const r2 = locals[cdt] && locals[cdt][cdn];
      if (!r2 || !r2.item_code)
        return;
      frappe.call({
        method: "azzir_fleet.warehouse_cc.user_warehouse_for_item",
        args: { item_code: r2.item_code, company: frm.doc.company },
        callback(r) {
          if (r.message && locals[cdt] && locals[cdt][cdn]) {
            frappe.model.set_value(cdt, cdn, "warehouse", r.message);
          }
        }
      });
    }, 800);
  };
  azzir_fleet.show_stock_dialog = function(item_code, on_select) {
    if (!item_code)
      return;
    const exclude_invoice = typeof cur_frm !== "undefined" && cur_frm && cur_frm.doc && cur_frm.doc.name || "";
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
          const icon = node.is_group ? "\u{1F4C1}" : "\u2022";
          const weight = node.is_group ? "600" : "400";
          const wh = frappe.utils.escape_html(node.warehouse);
          const locked = on_select && !node.is_group && node.selectable === false;
          let pick = "";
          if (on_select) {
            if (node.is_group) {
              pick = '<span style="display:inline-block; width:22px;"></span>';
            } else if (locked) {
              pick = '<span style="display:inline-block; width:22px;">\u{1F512}</span>';
            } else {
              pick = `<input type="radio" name="azzir-wh-pick" class="azzir-wh-pick"
							data-wh="${wh}" style="margin-right:8px; cursor:pointer;">`;
            }
          }
          const clickable = on_select && !node.is_group && !locked;
          const incoming = flt(node.incoming);
          const incoming_html = incoming ? ` <span style="color:#888; font-weight:400;">(+${format_number(incoming)} ${__("incoming")})</span>` : "";
          let html = `<div class="azzir-wh-row" data-wh="${wh}"
					data-group="${node.is_group ? 1 : 0}" data-locked="${locked ? 1 : 0}"
					title="${locked ? __("Not in your cost center \u2014 view only") : ""}"
					style="display:flex; align-items:center; justify-content:space-between; padding:5px 0;
					border-bottom:1px solid #f0f0f0; padding-left:${depth * 22}px;
					${locked ? "opacity:0.5;" : ""}${clickable ? "cursor:pointer;" : ""}">
					<span style="font-weight:${weight};">${pick}${icon} ${wh}</span>
					<span style="font-weight:${weight};">${format_number(node.qty)}${incoming_html}</span></div>`;
          (by_parent[node.warehouse] || []).forEach((c) => html += render(c, depth + 1));
          return html;
        }
        const roots = by_parent["__root__"] || [];
        const companies = [...new Set(roots.map((x) => x.company || ""))].sort();
        let body = "";
        companies.forEach((co) => {
          if (companies.length > 1 || co) {
            body += `<div style="font-weight:700; background:#f4f6f8; padding:6px 8px;
						margin-top:6px; border-bottom:2px solid #000;">\u{1F3E2} ${frappe.utils.escape_html(co || __("Company"))}</div>`;
          }
          roots.filter((rt) => (rt.company || "") === co).forEach((rt) => body += render(rt, 0));
        });
        const total = roots.reduce((s, x) => s + flt(x.qty), 0);
        const total_incoming = roots.reduce((s, x) => s + flt(x.incoming), 0);
        if (!body)
          body = `<p class="text-muted">${__("No available stock in any warehouse.")}</p>`;
        const d = new frappe.ui.Dialog({
          title: __("Available Stock by Warehouse \u2014 {0}", [item_code]),
          size: "large"
        });
        const hint = on_select ? `<p class="text-muted" style="margin:0 0 8px;">${__("Select a warehouse to set it on this row.")}</p>` : "";
        d.$body.html(`<div style="max-height:440px; overflow:auto; font-size:13px;">
				${hint}${body}
				<div style="display:flex; justify-content:space-between; padding:8px 0;
					border-top:2px solid #000; font-weight:700; margin-top:6px;">
					<span>${__("Total")}</span><span>${format_number(total)}${total_incoming ? ` <span style="color:#888; font-weight:400;">(+${format_number(total_incoming)} ${__("incoming")})</span>` : ""}</span></div>
			</div>`);
        if (on_select) {
          const pick = (wh) => {
            if (!wh)
              return;
            on_select(wh);
            d.hide();
          };
          d.$body.on("click", ".azzir-wh-pick", function(e) {
            e.stopPropagation();
            pick($(this).attr("data-wh"));
          });
          d.$body.on("click", ".azzir-wh-row", function() {
            if ($(this).attr("data-group") === "0" && $(this).attr("data-locked") !== "1")
              pick($(this).attr("data-wh"));
          });
        }
        d.show();
      }
    });
  };
  document.addEventListener(
    "click",
    function(e) {
      const cell = e.target && e.target.closest && e.target.closest('.grid-row [data-fieldname="azzir_all_stock"]');
      if (!cell)
        return;
      e.stopPropagation();
      e.preventDefault();
      const nameEl = cell.closest("[data-name]");
      const cdn = nameEl && nameEl.getAttribute("data-name");
      const wrapper = cell.closest(".frappe-control");
      const grid_field = wrapper && wrapper.fieldobj;
      const child_dt = grid_field && grid_field.df && grid_field.df.options;
      const row = child_dt && cdn && locals[child_dt] && locals[child_dt][cdn];
      if (row && row.item_code) {
        const on_select = frappe.meta.has_field(child_dt, "warehouse") ? (wh) => frappe.model.set_value(child_dt, cdn, "warehouse", wh) : void 0;
        azzir_fleet.show_stock_dialog(row.item_code, on_select);
      }
    },
    true
  );
  $('<style>.grid-row [data-fieldname="azzir_all_stock"]{cursor:pointer;color:#1a73e8;text-decoration:underline;}</style>').appendTo("head");

  // ../azzir_fleet/azzir_fleet/public/js/azzir_vat.js
  ["Sales Invoice", "Sales Order", "Quotation", "Delivery Note"].forEach(function(dt) {
    frappe.ui.form.on(dt, {
      azzir_apply_vat(frm) {
        if (!frm.doc.azzir_apply_vat) {
          frm.clear_table("taxes");
          if (frm.fields_dict.taxes_and_charges) {
            frm.set_value("taxes_and_charges", null);
          }
          frm.refresh_field("taxes");
          frm.trigger("calculate_taxes_and_totals");
          return;
        }
        if ((frm.doc.taxes || []).length)
          return;
        frappe.call({
          method: "azzir_fleet.vat.get_vat_row",
          args: { company: frm.doc.company },
          callback(r) {
            if (!r.message || !r.message.account_head) {
              frappe.show_alert({
                message: __("No VAT account found for this company."),
                indicator: "orange"
              });
              return;
            }
            const row = frm.add_child("taxes", r.message);
            frm.refresh_field("taxes");
            frm.trigger("calculate_taxes_and_totals");
          }
        });
      }
    });
  });

  // ../azzir_fleet/azzir_fleet/public/js/azzir_tax.js
  frappe.provide("azzir_fleet");
  azzir_fleet.split_tax = function(base, type, rate) {
    base = flt(base);
    rate = flt(rate);
    if (!type || !rate || !base)
      return [0, base];
    if (type === "Inclusive") {
      const net = base / (1 + rate / 100);
      return [flt(base - net), flt(net)];
    }
    return [flt(base * rate / 100), flt(base)];
  };
  function apply_calc(frm, cdt, cdn, base) {
    const r = locals[cdt][cdn];
    const [tax, net] = azzir_fleet.split_tax(base, r.azzir_tax_type, r.azzir_tax_rate);
    frappe.model.set_value(cdt, cdn, "azzir_tax_amount", tax);
    frappe.model.set_value(cdt, cdn, "azzir_net_amount", net);
  }
  frappe.ui.form.on("Expense Entry Account", {
    amount: (frm, cdt, cdn) => apply_calc(frm, cdt, cdn, locals[cdt][cdn].amount),
    azzir_tax_type: (frm, cdt, cdn) => apply_calc(frm, cdt, cdn, locals[cdt][cdn].amount),
    azzir_tax_rate: (frm, cdt, cdn) => apply_calc(frm, cdt, cdn, locals[cdt][cdn].amount)
  });
  function je_base(cdt, cdn) {
    const r = locals[cdt][cdn];
    return flt(r.debit_in_account_currency) || flt(r.credit_in_account_currency);
  }
  frappe.ui.form.on("Journal Entry Account", {
    debit_in_account_currency: (frm, cdt, cdn) => apply_calc(frm, cdt, cdn, je_base(cdt, cdn)),
    credit_in_account_currency: (frm, cdt, cdn) => apply_calc(frm, cdt, cdn, je_base(cdt, cdn)),
    azzir_tax_type: (frm, cdt, cdn) => apply_calc(frm, cdt, cdn, je_base(cdt, cdn)),
    azzir_tax_rate: (frm, cdt, cdn) => apply_calc(frm, cdt, cdn, je_base(cdt, cdn))
  });
})();
//# sourceMappingURL=azzir_fleet.bundle.333RFOUV.js.map
