# Copyright (c) 2026, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SAIBAValidationSettings(Document):
	def validate(self):
		"""Validate SAIBA Validation Settings"""
		self.validate_rules()

	def validate_rules(self):
		"""Ensure no duplicate rules exist"""
		# Check for duplicate Motor rules
		motor_fields = set()
		for rule in self.motor_validation_rules or []:
			key = (rule.saiba_field, rule.doctype_field)
			if key in motor_fields:
				frappe.throw(f"Duplicate Motor rule found: {rule.saiba_field} -> {rule.doctype_field}")
			motor_fields.add(key)

		# Check for duplicate Health rules
		health_fields = set()
		for rule in self.health_validation_rules or []:
			key = (rule.saiba_field, rule.doctype_field)
			if key in health_fields:
				frappe.throw(f"Duplicate Health rule found: {rule.saiba_field} -> {rule.doctype_field}")
			health_fields.add(key)
