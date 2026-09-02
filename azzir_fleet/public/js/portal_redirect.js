// Confine "Sales Portal" users to the /sales app. The Sales Portal role wins over
// EVERY other role — System Manager included — so a portal user can never slip
// onto the desk. Only the built-in Administrator account is exempt, so a site is
// never left without a way in.
//
// The server-side guard (azzir_fleet.session.redirect_portal_users_off_desk) is
// authoritative and already 302s these requests. This is the safety net for a desk
// shell that is already open in a tab — e.g. the role was assigned mid-session, or
// the SPA routed client-side without a new request hitting the server.
(function () {
	function onDesk() {
		// The desk root AND every page under it: /app, /app/quotation/QTN-0001,
		// /apps, /desk/user … all bounce. No ?desk=1 / cookie escape hatch.
		const p = (window.location.pathname || "/app").replace(/\/+$/, "") || "/app";
		return /^\/(app|apps|desk)(\/|$)/.test(p);
	}
	function roles() {
		try {
			return (
				(window.frappe && frappe.boot && frappe.boot.user && frappe.boot.user.roles) ||
				(window.frappe && frappe.user_roles) ||
				[]
			);
		} catch (e) {
			return [];
		}
	}
	function maybeRedirect() {
		try {
			const r = roles();
			if (!r.length) return false; // boot not ready yet
			const bypass =
				(window.frappe && frappe.session && frappe.session.user === "Administrator") ||
				r.includes("System Manager"); // admins always reach the desk
			if (r.includes("Sales Portal") && !bypass && onDesk()) {
				window.location.replace("/sales");
				return true;
			}
		} catch (e) {
			// never block the desk on an error here
		}
		return false;
	}

	if (!onDesk()) return;
	// Try immediately; if boot isn't ready, retry on frappe.ready and once more shortly.
	if (maybeRedirect()) return;
	try {
		if (window.frappe && frappe.ready) frappe.ready(maybeRedirect);
	} catch (e) {}
	setTimeout(maybeRedirect, 300);
	setTimeout(maybeRedirect, 1200);
	// The desk is a SPA: a client-side route change does not hit the server guard.
	try {
		window.addEventListener("popstate", maybeRedirect);
	} catch (e) {}
})();
