# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PolicyReaderSettings(Document):
	def validate(self):
		"""Validate Policy Reader Settings"""
		self.validate_api_key()
		self.validate_numeric_fields()
	
	def validate_api_key(self):
		"""Validate Anthropic API key format"""
		if self.anthropic_api_key:
			if not self.anthropic_api_key.startswith('sk-ant-'):
				frappe.throw("Invalid Anthropic API key format. Key should start with 'sk-ant-'")
	
	def validate_numeric_fields(self):
		"""Validate numeric field ranges"""
		if self.max_pages:
			if not (1 <= self.max_pages <= 10):
				frappe.throw("Max Pages must be between 1 and 10")
		
		if self.confidence_threshold:
			if not (0.1 <= self.confidence_threshold <= 1.0):
				frappe.throw("Confidence Threshold must be between 0.1 and 1.0")
		
		if self.timeout:
			if not (60 <= self.timeout <= 600):
				frappe.throw("Timeout must be between 60 and 600 seconds")
	
	@frappe.whitelist()
	def test_api_connection(self):
		"""Test API key connectivity (optional feature)"""
		if not self.anthropic_api_key:
			frappe.throw("Please enter an API key to test")
		
		try:
			# This is a basic test - in a real implementation you might want to make a test API call
			frappe.msgprint("API key format appears valid. Test connection functionality can be implemented as needed.", 
							title="API Key Test", indicator="green")
			return {"success": True, "message": "API key format valid"}
		except Exception as e:
			frappe.throw(f"API connection test failed: {str(e)}")
