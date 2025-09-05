# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class MotorPolicy(Document):
	def validate(self):
		"""Basic validation for SAIBA ERP compliance"""
		self.validate_policy_dates()
		self.validate_required_fields()
	
	def validate_policy_dates(self):
		"""Validate policy date logic"""
		if self.policy_start_date and self.policy_expiry_date:
			start_date = getdate(self.policy_start_date)
			expiry_date = getdate(self.policy_expiry_date)
			
			if start_date >= expiry_date:
				frappe.throw("Policy start date must be before expiry date")
	
	def validate_required_fields(self):
		"""Validate critical SAIBA fields with better error messages"""
		if not self.policy_no:
			frappe.throw("Policy Number is mandatory for SAIBA integration")
		
		# Customer code is required for manual creation, but can be 0 for automated creation
		# This allows policy document processing to create records that can be completed manually
		if self.customer_code is None:
			frappe.throw("Customer Code is mandatory for SAIBA integration")
