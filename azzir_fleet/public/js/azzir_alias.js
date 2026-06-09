// Azzir Fleet — alias-aware item search feedback.
//
// The server search middleware (azzir_fleet.alias.search_link) makes every
// Link-to-Item field resolve old codes to the current item and tags the
// dropdown entry with "↺ old code: <old>". This script raises a loud toast the
// moment such an entry is picked — in normal forms AND in child-table grids
// (Sales Invoice items, etc.), which use the same Awesomplete under the hood.

frappe.provide("azzir_fleet");

azzir_fleet._handle_select = function (e) {
	const native = e.originalEvent || e;
	const picked = native && native.text; // the chosen Awesomplete suggestion
	if (!picked) return;

	const desc = picked.description || "";
	const marker = desc.indexOf("↺ old code:");
	if (marker === -1) return; // not an alias hit — ignore

	// Extract the old code: text after "↺ old code:" up to the " · " separator.
	let old_code = desc.slice(marker + "↺ old code:".length);
	const sep = old_code.indexOf(" · ");
	if (sep !== -1) old_code = old_code.slice(0, sep);
	old_code = old_code.trim();

	const current = picked.value;
	frappe.show_alert(
		{
			message: __('Old code "{0}" — same item, now {1}', [old_code, current]),
			indicator: "orange",
		},
		8
	);
};

// Awesomplete dispatches a bubbling event on the <input>; a delegated handler on
// document catches it for every link field, in forms and in grid rows alike.
$(document).on("awesomplete-selectcomplete", "input", azzir_fleet._handle_select);

// --------------------------------------------------------------------------- //
// POS — same behaviour inside Point of Sale (its own search engine).
// The server override (azzir_fleet.pos.get_items) resolves old codes and tags
// the returned items; here we patch the POS item selector to toast on a hit.
// --------------------------------------------------------------------------- //
azzir_fleet._patch_pos = function () {
	if (azzir_fleet._pos_patched) return;
	if (
		typeof erpnext === "undefined" ||
		!erpnext.PointOfSale ||
		!erpnext.PointOfSale.ItemSelector
	) {
		return;
	}
	const proto = erpnext.PointOfSale.ItemSelector.prototype;
	const orig_get_items = proto.get_items;
	proto.get_items = function (opts) {
		const promise = orig_get_items.call(this, opts);
		const term = (opts && opts.search_term) || "";
		if (term && promise && promise.then) {
			promise.then(({ message }) => {
				const items = (message && message.items) || [];
				const hit = items.find((i) => i.azzir_old_code);
				if (hit) {
					frappe.show_alert(
						{
							message: __('Old code "{0}" — same item, now {1}', [
								hit.azzir_old_code,
								hit.azzir_current_code || hit.item_code,
							]),
							indicator: "orange",
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

// The POS bundle loads lazily when the page opens. Poll persistently until the
// class exists, then patch its prototype and stop. This does NOT depend on any
// route/startup event firing (POS is a page route — those events are unreliable).
azzir_fleet._pos_poll_started = false;
azzir_fleet._start_pos_poller = function () {
	if (azzir_fleet._pos_poll_started) return;
	azzir_fleet._pos_poll_started = true;
	let tries = 0;
	const timer = setInterval(() => {
		azzir_fleet._patch_pos();
		// stop once patched, or after ~10 min as a safety backstop
		if (azzir_fleet._pos_patched || ++tries > 1200) clearInterval(timer);
	}, 500);
};

azzir_fleet._start_pos_poller();
