
import json
import frappe
from foxyutils import decrypt_str
from xml.etree import ElementTree
import urllib
import xmltodict
from frappe.utils.response import build_response
from werkzeug.wrappers import Response

from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

@frappe.whitelist(allow_guest=True)
def process_new_order():
	API_KEY = frappe.db.get_single_value('ICLOAK Customization Settings', 'foxy_api_key')
	encrypted_data = frappe.local.request.form.get("FoxyData")
	decrypted_data = decrypt_str(urllib.unquote_plus(encrypted_data), API_KEY)
	foxy_data = json.loads(json.dumps(xmltodict.parse(decrypted_data).get("foxydata").get("transactions").get("transaction")))
	customer = find_customer(foxy_data.get("customer_email"))
	address = None
	if not customer:
		customer = make_customer(foxy_data)
		address = make_address(customer, foxy_data)
	else:
		address = find_address(customer, foxy_data)
		if not address:
			address = make_address(customer, foxy_data)

	sales_order = make_sales_order(customer, foxy_data)
	sales_invoice = make_sales_invoice(sales_order, ignore_permissions=True)
	sales_invoice.save()
	sales_invoice.submit()
	frappe.db.commit()
	payment_entry = get_payment_entry("Sales Invoice", sales_invoice.name)
	payment_entry.reference_no = foxy_data.get("id")
	payment_entry.reference_date = foxy_data.get("transaction_date")
	payment_entry.flags.ignore_permissions= True
	payment_entry.save()
	payment_entry.submit()
	frappe.db.commit()

	response = Response()
	response.data = "foxy"
	return response




def find_customer(customer_email):
	customer = frappe.get_all("Customer", filters={"customer_email": customer_email})
	if customer:
		return customer[0].name
	else:
		return None

def make_customer(foxy_data):
	customer = frappe.new_doc("Customer")
	customer.update({
		"customer_name": (foxy_data.get("customer_first_name") + " " + foxy_data.get("customer_last_name")).title(),
		"customer_email": foxy_data.get("customer_email"),
		"customer_type": "Individual",
		"customer_group": "Individual",
		"territory": "All Territories"
	})
	customer.flags.ignore_permissions=True
	customer.save()
	frappe.db.commit()
	return customer.name

def make_sales_order(customer, foxy_data):
	sales_order = frappe.new_doc("Sales Order")
	sales_order.update({
		"customer": customer,
		"order_type": "Shopping Cart"
	})
	sales_items = []
	foxy_items = foxy_data.get("transaction_details").get("transaction_detail")
	if type(foxy_items) == dict:
		foxy_items = [foxy_items]
	for item in foxy_items:
		sales_items.append({
			"item_code": item.get("product_name"),
			"item_name": item.get("product_name"),
			"description": item.get("product_name"),
			"qty": item.get("product_quantity"),
			"uom": "Nos",
			"conversion_factor": 1,
			"rate": item.get("product_price")
		})
	sales_order.set("items", sales_items)
	sales_order.flags.ignore_permissions=True
	sales_order.save()
	sales_order.submit()
	frappe.db.commit()
	return sales_order.name

def find_address(customer, foxy_data):
	address = frappe.get_all("Address", filters={
		"address_title": '%s %s' % (foxy_data.get("shipping_first_name"), foxy_data.get("shipping_last_name")),
		"address_line1": foxy_data.get("shipping_address1"),
		"address_line2": foxy_data.get("shipping_address2"),
		"address_type": "Shipping",
		"city": foxy_data.get("shipping_city"),
		"state": foxy_data.get("shipping_state"),
		"pincode": foxy_data.get("shipping_postal_code")
	})
	if address:
		return address[0].name

def make_address(customer, foxy_data):
	address = frappe.new_doc("Address")
	country = frappe.get_all("Country", filters={"code":foxy_data.get("shipping_country")})[0].name
	address.update({
		"address_title": '%s %s' % (foxy_data.get("shipping_first_name"), foxy_data.get("shipping_last_name")),
		"address_line1": foxy_data.get("shipping_address1"),
		"address_line2": foxy_data.get("shipping_address2"),
		"address_type": "Shipping",
		"city": foxy_data.get("shipping_city"),
		"state": foxy_data.get("shipping_state"),
		"country": country,
		"pincode": foxy_data.get("shipping_postal_code"),
		"email_id": foxy_data.get("customer_email"),
		"phone": foxy_data.get("shipping_phone")
	})
	address.set("links", [{"link_doctype": "Customer", "link_name": customer}])
	address.flags.ignore_permissions= True
	address.save()
