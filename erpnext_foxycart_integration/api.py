from __future__ import unicode_literals

import json
import frappe
from foxyutils import decrypt_str
from xml.etree import ElementTree
import urllib
import xmltodict

@frappe.whitelist(allow_guest=True)
def process_new_order():
	API_KEY = frappe.db.get_value('ICLOAK Customization Settings', None, 'foxy_api_key')
	foxy_data = frappe.local.request.form.get("FoxyData")
	data = decrypt_str(urllib.unquote_plus(foxy_data), API_KEY)
	data_dict = xmltodict.parse(data)

	customer = find_customer()
	if not customer:
		customer = make_customer()
	make_sales_order()
	make_sales_invoice()
	make_payment_entry()

	return "foxy"


def find_customer():
	return "None"

def make_customer():
	return "None"

def make_sales_order():
	pass

def make_sales_invoice():
	pass

def make_payment_entry():
	pass
