// Force "Sales Portal" users onto the /sales app whenever they land on the desk
// (covers every login path, including redirect-to=/app). Overseers / managers /
// Administrator are exempt so they can still use the desk.
(function () {
	try {
		const roles = (frappe.boot && frappe.boot.user && frappe.boot.user.roles) || [];
		const isPortal = roles.includes("Sales Portal");
		const bypass =
			roles.includes("System Manager") ||
			roles.includes("Azzir Sales Overseer") ||
			frappe.session.user === "Administrator";
		const onDesk = /^\/app(\/|$)/.test(window.location.pathname.replace(/\/+$/, "") || "/app");
		if (isPortal && !bypass && onDesk) {
			window.location.replace("/sales");
		}
	} catch (e) {
		// never block the desk on an error here
	}
})();
