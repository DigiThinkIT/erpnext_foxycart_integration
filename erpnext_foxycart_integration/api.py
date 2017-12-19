
import frappe
from foxyutils import decrypt_data
from werkzeug.wrappers import Response

from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe.utils import cint

@frappe.whitelist(allow_guest=True)
def push():
	encrypted_data = frappe.local.request.form.get("FoxyData")
	foxycart_data = decrypt_data(encrypted_data)
	process_new_order(foxycart_data)

	response = Response()
	response.data = "foxy"
	return response

def process_new_order(foxycart_data):
	foxycart_settings = frappe.get_single("Foxycart Settings")
	customer = find_customer(foxycart_data.get("customer_email"))

	# Hack to prevent permission issues
	if frappe.session.user == "Guest":
		frappe.set_user("Administrator")

	address = None
	if not customer:
		customer = make_customer(foxycart_data, foxycart_settings)
		address = make_address(customer, foxycart_data)
	else:
		address = find_address(customer, foxycart_data)
		if not address:
			address = make_address(customer, foxycart_data)

	sales_order = make_sales_order(customer, foxycart_data, foxycart_settings)
	sales_invoice = make_sales_invoice(sales_order, ignore_permissions=True)
	sales_invoice.save()
	sales_invoice.submit()
	frappe.db.commit()
	payment_entry = get_payment_entry("Sales Invoice", sales_invoice.name)
	payment_entry.reference_no = foxycart_data.get("id")
	payment_entry.reference_date = foxycart_data.get("transaction_date")
	payment_entry.flags.ignore_permissions= True
	payment_entry.save()
	payment_entry.submit()
	frappe.db.commit()



def find_customer(customer_email):
	customer = frappe.get_all("Customer", filters={"customer_email": customer_email})
	if customer:
		return customer[0].name
	else:
		return None


def make_customer(foxycart_data, foxycart_settings):
	customer = frappe.new_doc("Customer")
	customer.update({
		"customer_name": (foxycart_data.get("customer_first_name") + " " + foxycart_data.get("customer_last_name")).title(),
		"customer_email": foxycart_data.get("customer_email"),
		"customer_type": foxycart_settings.customer_type or "Individual",
		"customer_group": foxycart_settings.customer_group or "Individual",
		"territory": foxycart_settings.territory or "All Territories"
	})
	customer.flags.ignore_permissions=True
	customer.save()
	frappe.db.commit()
	return customer.name


def make_sales_order(customer, foxycart_data, foxycart_settings):
	sales_order = frappe.new_doc("Sales Order")
	sales_order.update({
		"customer": customer,
		"order_type": "Shopping Cart"
	})
	sales_items = []
	foxy_items = foxycart_data.get("transaction_details").get("transaction_detail")
	if type(foxy_items) == dict:
		foxy_items = [foxy_items]
	for item in foxy_items:
		product_name = item.get("product_name")
		if not frappe.db.exists("Item", {"item_code" : product_name}):
			frappe.get_doc({"doctype" : "Item",
							"item_code" : product_name,
							"item_group" : foxycart_settings.item_group or "All Item Groups",
							"stock_uom" : foxycart_settings.uom,
							"standard_rate" : item.get("product_price")
			}).insert()
		sales_items.append({
			"item_code": product_name,
			"item_name": product_name,
			"description": frappe.db.get_value("Item", {"item_code" : product_name}, "description") or product_name,
			"qty": item.get("product_quantity"),
			"uom": foxycart_settings.uom or "Nos",
			"conversion_factor": foxycart_settings.conversion_factor or 1,
			"rate": item.get("product_price")
		})
	sales_order.set("items", sales_items)
	taxes = []
	if cint(foxycart_data.get("shipping_total")) or foxycart_data.get("shipto_shipping_service_description"):
		taxes.append({
			"charge_type": "Actual",
			"account_head": foxycart_settings.shipping_account_head,
			"description": foxycart_data.get("shipto_shipping_service_description", "Shipping Charges"),
			"tax_amount": cint(foxycart_data.get("shipping_total"))
		})

	if cint(foxycart_data.get("tax_total")) > 0:
		taxes.append({
			"charge_type": "Actual",
			"account_head": foxycart_settings.tax_account_head,
			"description": "Tax",
			"tax_amount": cint(foxycart_data.get("tax_total"))
		})
	sales_order.set("taxes", taxes)

	sales_order.flags.ignore_permissions=True
	sales_order.save()
	sales_order.submit()
	frappe.db.commit()
	return sales_order.name

def find_address(customer, foxycart_data):
	address = frappe.get_all("Address", filters={
		"address_title": '%s %s' % (foxycart_data.get("shipping_first_name"), foxycart_data.get("shipping_last_name")),
		"address_line1": foxycart_data.get("shipping_address1"),
		"address_line2": foxycart_data.get("shipping_address2"),
		"address_type": "Shipping",
		"city": foxycart_data.get("shipping_city"),
		"state": foxycart_data.get("shipping_state"),
		"pincode": foxycart_data.get("shipping_postal_code")
	})
	if address:
		return address[0].name

def make_address(customer, foxycart_data):
	address = frappe.new_doc("Address")
	country = frappe.get_all("Country", filters={"code":foxycart_data.get("shipping_country")})[0].name
	address.update({
		"address_title": '%s %s' % (foxycart_data.get("shipping_first_name"), foxycart_data.get("shipping_last_name")),
		"address_line1": foxycart_data.get("shipping_address1"),
		"address_line2": foxycart_data.get("shipping_address2"),
		"address_type": "Shipping",
		"city": foxycart_data.get("shipping_city"),
		"state": foxycart_data.get("shipping_state"),
		"country": country,
		"pincode": foxycart_data.get("shipping_postal_code"),
		"email_id": foxycart_data.get("customer_email"),
		"phone": foxycart_data.get("shipping_phone")
	})
	address.set("links", [{"link_doctype": "Customer", "link_name": customer}])
	address.flags.ignore_permissions= True
	address.save()
