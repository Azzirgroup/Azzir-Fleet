(() => {
  // ../azzir_fleet/azzir_fleet/public/js/portal_redirect.js
  (function() {
    function onDesk() {
      const p = (window.location.pathname || "/app").replace(/\/+$/, "") || "/app";
      return /^\/(app|apps|desk)(\/|$)/.test(p);
    }
    function roles() {
      try {
        return window.frappe && frappe.boot && frappe.boot.user && frappe.boot.user.roles || window.frappe && frappe.user_roles || [];
      } catch (e) {
        return [];
      }
    }
    function maybeRedirect() {
      try {
        const r = roles();
        if (!r.length)
          return false;
        const bypass = window.frappe && frappe.session && frappe.session.user === "Administrator" || r.includes("System Manager");
        if (r.includes("Sales Portal") && !bypass && onDesk()) {
          window.location.replace("/sales");
          return true;
        }
      } catch (e) {
      }
      return false;
    }
    if (!onDesk())
      return;
    if (maybeRedirect())
      return;
    try {
      if (window.frappe && frappe.ready)
        frappe.ready(maybeRedirect);
    } catch (e) {
    }
    setTimeout(maybeRedirect, 300);
    setTimeout(maybeRedirect, 1200);
    try {
      window.addEventListener("popstate", maybeRedirect);
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
  azzir_fleet.toggle_sister_columns = function(frm) {
    if (!frm.fields_dict.items)
      return;
    const grid = frm.fields_dict.items.grid;
    const cols = ["azzir_row_from_sister", "azzir_supply_company", "azzir_supply_warehouse"];
    const apply = (can) => {
      cols.forEach((f) => {
        if (frappe.meta.has_field(grid.doctype, f))
          grid.update_docfield_property(f, "hidden", can ? 0 : 1);
      });
      grid.refresh();
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
    if (!frm.fields_dict.items)
      return;
    frm.set_query("azzir_supply_warehouse", "items", function(doc, cdt, cdn) {
      const row = locals[cdt][cdn] || {};
      return {
        query: "azzir_fleet.intercompany_sale.supply_warehouse_link_query",
        filters: {
          company: row.azzir_supply_company || "",
          item_codes: row.item_code ? [row.item_code] : []
        }
      };
    });
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

  // ../azzir_fleet/azzir_fleet/public/js/azzir_purchase.js
  frappe.provide("azzir_fleet");
  azzir_fleet.set_target_wh_query = function(frm) {
    if (!frm.fields_dict.items)
      return;
    frm.set_query("azzir_target_warehouse", "items", function(doc, cdt, cdn) {
      const row = locals[cdt][cdn] || {};
      return {
        filters: { company: row.azzir_target_company || "", is_group: 0, disabled: 0 }
      };
    });
  };
  azzir_fleet.autofill_purchase_warehouse = function(frm, cdt, cdn) {
    const row = locals[cdt] && locals[cdt][cdn];
    if (!row || !row.item_code || row.warehouse)
      return;
    frappe.call({
      method: "azzir_fleet.stock_info.last_warehouse",
      args: { item_code: row.item_code, company: frm.doc.company },
      callback(r) {
        if (r.message && locals[cdt][cdn] && !locals[cdt][cdn].warehouse) {
          frappe.model.set_value(cdt, cdn, "warehouse", r.message);
        }
      }
    });
  };
  ["Purchase Order", "Purchase Receipt", "Purchase Invoice"].forEach(function(dt) {
    frappe.ui.form.on(dt, {
      onload: azzir_fleet.set_target_wh_query,
      refresh(frm) {
        azzir_fleet.set_target_wh_query(frm);
        if (frm.doc.doctype === "Purchase Order") {
          const drop = () => frm.remove_custom_button(__("Purchase Receipt"), __("Create"));
          drop();
          setTimeout(drop, 500);
        }
      }
    });
  });
  ["Purchase Order Item", "Purchase Invoice Item"].forEach(function(dt) {
    frappe.ui.form.on(dt, {
      item_code(frm, cdt, cdn) {
        azzir_fleet.autofill_purchase_warehouse(frm, cdt, cdn);
      }
    });
  });
  ["Purchase Order Item", "Purchase Receipt Item", "Purchase Invoice Item"].forEach(function(dt) {
    frappe.ui.form.on(dt, {
      azzir_row_to_target(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row && !row.azzir_row_to_target) {
          frappe.model.set_value(cdt, cdn, "azzir_target_company", "");
          frappe.model.set_value(cdt, cdn, "azzir_target_warehouse", "");
        }
      },
      azzir_target_company(frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, "azzir_target_warehouse", "");
      }
    });
  });

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

  // ../azzir_fleet/azzir_fleet/public/js/azzir_whatsapp_approve.js
  var AZZIR_WA_DOCTYPES = ["Quotation", "Sales Invoice", "Delivery Note"];
  function azzir_wa_available() {
    try {
      if (frappe.boot && frappe.boot.versions)
        return !!frappe.boot.versions.whatsapp_integration;
    } catch (e) {
    }
    return true;
  }
  function azzir_wa_pending(frm) {
    return frm.doc.docstatus === 0 && /pending/i.test(frm.doc.workflow_state || "");
  }
  function azzir_wa_doc_phone(doc) {
    return doc.contact_mobile || doc.customer_mobile_no || doc.mobile_no || doc.phone || doc.contact_phone || "";
  }
  function azzir_wa_open_dialog(frm) {
    frappe.call({
      method: "whatsapp_integration.api.whatsapp.whatsapp.get_whatsapp_senders",
      callback(r) {
        const senders = r.message || [];
        const phone = azzir_wa_doc_phone(frm.doc);
        if (phone)
          return azzir_wa_dialog(frm, senders, phone);
        if (frm.doc.customer) {
          frappe.db.get_value("Customer", frm.doc.customer, "mobile_no").then((res) => {
            azzir_wa_dialog(frm, senders, res && res.message && res.message.mobile_no || "");
          });
        } else {
          azzir_wa_dialog(frm, senders, "");
        }
      }
    });
  }
  function azzir_wa_dialog(frm, senders, phone) {
    const fields = [];
    if (senders.length) {
      fields.push({
        label: __("Send From"),
        fieldname: "sender",
        fieldtype: "Select",
        options: senders.map((s) => s.value),
        default: (senders.find((s) => s.is_default) || senders[0]).value,
        reqd: 1
      });
    }
    fields.push(
      {
        label: __("WhatsApp Number"),
        fieldname: "phone_number",
        fieldtype: "Data",
        default: phone,
        reqd: 1,
        description: __("Include the country code, e.g. 255\u2026")
      },
      {
        label: __("Note (optional)"),
        fieldname: "note",
        fieldtype: "Small Text",
        default: __("This {0} is below buying price and needs your approval.", [frm.doc.doctype])
      }
    );
    const d = new frappe.ui.Dialog({
      title: __("Send for Approval on WhatsApp"),
      fields,
      primary_action_label: __("Send"),
      primary_action(values) {
        d.hide();
        frappe.dom.freeze(__("Sending on WhatsApp\u2026"));
        frappe.call({
          method: "azzir_fleet.whatsapp_approve.send_with_approve",
          args: {
            doctype: frm.doc.doctype,
            docname: frm.doc.name,
            phone_number: values.phone_number,
            sender: values.sender || null,
            note: values.note || null
          },
          always: () => frappe.dom.unfreeze(),
          callback() {
            frappe.show_alert({ message: __("Sent on WhatsApp with an approve link."), indicator: "green" });
          }
        });
      }
    });
    d.show();
  }
  AZZIR_WA_DOCTYPES.forEach((dt) => {
    frappe.ui.form.on(dt, {
      refresh(frm) {
        if (frm.is_new() || !azzir_wa_available() || !azzir_wa_pending(frm))
          return;
        frm.add_custom_button(
          __("Send for Approval (WhatsApp)"),
          () => azzir_wa_open_dialog(frm),
          __("WhatsApp")
        );
      }
    });
  });
})();
//# sourceMappingURL=azzir_fleet.bundle.E7ME7JLA.js.map
