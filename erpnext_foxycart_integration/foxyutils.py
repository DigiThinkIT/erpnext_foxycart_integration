"""
Utilities for decrypting and parsing a FoxyCart datafeed.
"""
import frappe
import urllib
import xmltodict
import json

# Thanks, Wikipedia: http://en.wikipedia.org/wiki/RC4#Implementation
class ARC4:
	def __init__(self, key = None):
		self.state = range(256) # Initialize state array with values 0 .. 255
		self.x = self.y = 0 # Our indexes. x, y instead of i, j

		if key is not None:
			self.init(key)

	# KSA
	def init(self, key):
		for i in range(256):
			self.x = (ord(key[i % len(key)]) + self.state[i] + self.x) & 0xFF
			self.state[i], self.state[self.x] = self.state[self.x], self.state[i]
		self.x = 0

	# PRGA
	def crypt(self, input):
		output = [None]*len(input)
		for i in xrange(len(input)):
			self.x = (self.x + 1) & 0xFF
			self.y = (self.state[self.x] + self.y) & 0xFF
			self.state[self.x], self.state[self.y] = self.state[self.y], self.state[self.x]
			r = self.state[(self.state[self.x] + self.state[self.y]) & 0xFF]
			output[i] = chr(ord(input[i]) ^ r)
		return ''.join(output)


def decrypt_str(data_str, crypt_key):
	a = ARC4(crypt_key)
	return a.crypt(data_str)


def decrypt_data(encrypted_data, key=None):
	API_KEY = key or frappe.get_single("Foxycart Settings").get_password("api_key")

	if not API_KEY:
		frappe.throw("API Key is not set, please check Foxycart Settings")
	decrypted_data = decrypt_str(urllib.unquote_plus(encrypted_data), API_KEY)
	# First parse the XML into a Ordered Dict and then into a normal Dict
	foxycart_data = json.loads(json.dumps(xmltodict.parse(decrypted_data).get("foxydata").get("transactions").get("transaction")))
	return foxycart_data
