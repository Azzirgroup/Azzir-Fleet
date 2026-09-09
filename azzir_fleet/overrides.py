# Copyright (c) 2026, Azzir and contributors
# For license information, please see license.txt
"""Sales Invoice override so Product Bundle components are kept even with
Update Stock OFF.

ERPNext's SalesInvoice.update_packing_list() wipes packed_items when the invoice
doesn't move stock. We always build them instead — make_packing_list() preserves
any component warehouse the user already picked, so their picks survive save and
the components power reservation + the pickup print. No stock moves from the
invoice; that stays on the Delivery Note.
"""

from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from erpnext.buying.doctype.purchase_order.purchase_order import PurchaseOrder
from erpnext.stock.doctype.packed_item.packed_item import make_packing_list


class AzzirSalesInvoice(SalesInvoice):
	def update_packing_list(self):
		make_packing_list(self)


class AzzirPurchaseOrder(PurchaseOrder):
	"""Ordering below an item's Minimum Order Qty is ALLOWED. ERPNext's
	validate_minimum_order_qty would throw; instead qty_limits.flag_below_min_qty
	marks the order and the approval workflow takes over."""

	def validate_minimum_order_qty(self):
		return

