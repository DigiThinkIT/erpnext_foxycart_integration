import frappe
import json
import hashlib
import hmac

from .foxyutils import decrypt_data
from werkzeug.wrappers import Response

from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe.utils import cint

@frappe.whitelist(allow_guest=True)
def push():
	

	# Get API key and validate the signature of the request
	api_key = frappe.get_single("Foxycart Settings").get_password("api_key")
	signature = hmac.new(api_key.encode("utf-8"), frappe.request.data, hashlib.sha256).hexdigest()

	# If the signature matches, we can assume it's a payload from Foxy.io
	if signature == frappe.request.headers.get("Foxy-Webhook-Signature") and frappe.request.method == "POST":
		response = Response()

		# Try creating a sales order and connected models with the payload
		try:
			fd = json.loads(frappe.request.data)
			process_new_order(fd)
			response.data = {"status": "ok"}
		except Exception as e:
			fd = "no data"
			response.data = {"error": str(e)}
		return response

	# Otherwise, treat the incoming request as invalid
	else:
		print("Invalid request")
		response = Response()
		response.status = 500
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

	sales_order = make_sales_order(
		customer, address, foxycart_data, foxycart_settings)
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
		"territory": foxycart_data.get("customer_country") or foxycart_data.get("country") or foxycart_settings.territory or "All Territories"
	})
	customer.flags.ignore_permissions=True
	customer.save()
	frappe.db.commit()
	return customer.name


def make_sales_order(customer, address, foxycart_data, foxycart_settings):
	sales_order = frappe.new_doc("Sales Order")
	sales_order.update({
		"customer": customer,
		"order_type": "Shopping Cart"
	})
	sales_items = []
	
	foxy_items = foxycart_data.get("_embedded").get("fx:items")
	if type(foxy_items) == dict:
		foxy_items = [foxy_items]

	for item in foxy_items:
		product_name = item.get("name")

		if not frappe.db.exists("Item", {"name" : product_name}):
			print(f"Product: {product_name} not found")

		else:
			sales_items.append({
				"item_code": product_name,
				"item_name": product_name,
				"qty": item.get("quantity"),
				"uom": foxycart_settings.uom or "Nos",
				"conversion_factor": foxycart_settings.conversion_factor or 1,
				"rate": item.get("price")
			})

	sales_order.set("sales_order_details", sales_items)
	
	# taxes = []
	# if cint(foxycart_data.get("shipping_total")) or foxycart_data.get("shipto_shipping_service_description"):
	# 	taxes.append({
	# 		"charge_type": "Actual",
	# 		"account_head": foxycart_settings.shipping_account_head,
	# 		"description": foxycart_data.get("shipto_shipping_service_description", "Shipping Charges"),
	# 		"tax_amount": cint(foxycart_data.get("shipping_total"))
	# 	})

	# if cint(foxycart_data.get("tax_total")) > 0:
	# 	taxes.append({
	# 		"charge_type": "Actual",
	# 		"account_head": foxycart_settings.tax_account_head,
	# 		"description": "Tax",
	# 		"tax_amount": cint(foxycart_data.get("tax_total"))
	# 	})
	sales_order.set("taxes", [])

	sales_order.customer_address = address
	sales_order.shipping_address_name = address
	# sales_order.status = "Draft"
	sales_order.flags.ignore_permissions = True
	sales_order.save()
	# sales_order.submit()

	frappe.db.commit()

	return sales_order.name

def find_address(customer, foxycart_data):
	address = frappe.get_all("Address", filters={
		"address_title": '%s %s' % (foxycart_data.get("first_name"), foxycart_data.get("last_name")),
		"address_line1": foxycart_data.get("address1"),
		"address_line2": foxycart_data.get("address2"),
		"address_type": "Shipping",
		"city": foxycart_data.get("city"),
		"state": foxycart_data.get("region"),
		"pincode": foxycart_data.get("postal_code")
	})
	if address:
		return address[0].name

def make_address(customer, foxycart_data):

	print(foxycart_data)
	address = frappe.new_doc("Address")

	billing_data = foxycart_data.get('_embedded').get("fx:billing_addresses")[0]
	customer_data = foxycart_data.get('_embedded').get("fx:customer")

	if billing_data:
		country_code = billing_data.get("customer_country")

		country = frappe.get_all("Country", filters={"code": country_code})[0]
		
		territory = frappe.get_all("Territory", filters={"id": country_code.strip().lower()})
		if territory:
			territory_name = territory[0].name
		else:
			territory_name = "All Territories"

		address.update({
			"address_title": '%s %s' % (foxycart_data.get("first_name"), foxycart_data.get("last_name")),
			"address_line1": billing_data.get("address1"),
			"address_line2": billing_data.get("address2"),
			"address_type": "Shipping",
			"city": billing_data.get("city"),
			"state": billing_data.get("region"),
			"country": country.name,
			"pincode": billing_data.get("postal_code"),
			"email_id": customer_data.get("email"),
			"phone": billing_data.get("customer_phone"),
			"territory": territory_name
		})

		address.set("links", [{"link_doctype": "Customer", "link_name": customer}])
		address.flags.ignore_permissions= True
		address.save()
