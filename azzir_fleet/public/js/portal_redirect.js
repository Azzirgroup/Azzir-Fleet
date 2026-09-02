// Force "Sales Portal" users onto the /sales app whenever they land on the desk
// (covers every login path, including /login?redirect-to=/app). The Sales Portal
// role wins over EVERY other role — even System Manager — so a portal user can
// never slip onto the desk. Only the built-in Administrator account is exempt (an
// escape hatch; it is never assigned the portal role in practice).
//
// The primary redirect is server-side (azzir_fleet.session.route_portal_users_on_login
// sets the post-login home_page to "sales"). This is the safety net for the case
// where the login carried a redirect-to=/app that the login page honours first.
(function () {
	function onDesk() {
		const p = (window.location.pathname || "/app").replace(/\/+$/, "") || "/app";
		return /^\/app(\/|$)/.test(p);
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
			const isPortal = r.includes("Sales Portal");
			// Only the Administrator superuser account is exempt — the Sales Portal
			// role overrides every other role (System Manager included).
			const bypass =
				window.frappe && frappe.session && frappe.session.user === "Administrator";
			if (isPortal && !bypass && onDesk()) {
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
})();
