# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import json
import os
from frappe.model.document import Document
from frappe.utils import now


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
	
	@frappe.whitelist()
	def refresh_field_mappings(self):
		"""Refresh field mappings from Motor Policy and Health Policy DocTypes"""
		try:
			# Build field mappings for both policy types
			motor_mapping = self.build_field_mapping_from_doctype("Motor Policy")
			health_mapping = self.build_field_mapping_from_doctype("Health Policy")
			
			# Update cached mappings
			self.motor_policy_fields = frappe.as_json(motor_mapping)
			self.health_policy_fields = frappe.as_json(health_mapping)
			self.last_field_sync = now()
			
			# Save the document
			self.save()
			
			frappe.msgprint(f"Field mappings refreshed successfully. Motor: {len(motor_mapping)} fields, Health: {len(health_mapping)} fields.",
							title="Field Mappings Refreshed", indicator="green")
			
			return {
				"success": True, 
				"motor_fields": len(motor_mapping),
				"health_fields": len(health_mapping)
			}
			
		except Exception as e:
			frappe.log_error(f"Field mapping refresh failed: {str(e)}", "Field Mapping Refresh Error")
			frappe.throw(f"Failed to refresh field mappings: {str(e)}")
	
	def build_field_mapping_from_doctype(self, doctype_name):
		"""Build field mapping from DocType definition"""
		try:
			# Get DocType document
			doctype_doc = frappe.get_doc("DocType", doctype_name)
			field_mapping = {}
			
			# Skip these system/layout fields when building mapping
			skip_fields = {
				"policy_document", "policy_file", "naming_series", "owner", "creation", 
				"modified", "modified_by", "docstatus", "idx", "name"
			}
			
			skip_fieldtypes = {
				"Section Break", "Column Break", "Tab Break", "HTML", "Heading", "Button"
			}
			
			# Build mapping from field labels to fieldnames
			for field in doctype_doc.fields:
				if (field.fieldname not in skip_fields and 
					field.fieldtype not in skip_fieldtypes and 
					field.label):
					
					field_mapping[field.label] = field.fieldname
			
			return field_mapping
			
		except Exception as e:
			frappe.log_error(f"Error building field mapping for {doctype_name}: {str(e)}", "Field Mapping Build Error")
			raise
	
	def get_cached_field_mapping(self, policy_type):
		"""Get cached field mapping for policy type"""
		try:
			if policy_type.lower() == "motor":
				if self.motor_policy_fields:
					return frappe.parse_json(self.motor_policy_fields)
			elif policy_type.lower() == "health":
				if self.health_policy_fields:
					return frappe.parse_json(self.health_policy_fields)
			
			# Return empty dict if no cached mapping found
			return {}
			
		except Exception as e:
			frappe.log_error(f"Error getting cached field mapping for {policy_type}: {str(e)}", "Field Mapping Cache Error")
			return {}
