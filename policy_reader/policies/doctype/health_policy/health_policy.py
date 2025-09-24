# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import getdate, cstr
from policy_reader.policy_reader.services.policy_creation_service import PolicyCreationService


class HealthPolicy(Document):
	def validate(self):
		"""Basic validation for Health Policy"""
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
		"""Validate critical Health Policy fields"""
		# Allow document creation without all fields for flexibility
		pass
	
	@frappe.whitelist()
	def populate_fields_from_policy_document(self, policy_document_name):
		"""
		Populate Health Policy fields from the linked Policy Document's extracted fields
		Uses the existing PolicyCreationService to avoid code duplication
		"""
		try:
			# Get the Policy Document
			policy_doc = frappe.get_doc("Policy Document", policy_document_name)
			
			# Check if extracted fields exist
			if not policy_doc.extracted_fields:
				return {
					"success": False,
					"error": "No extracted fields found in Policy Document. Please process the document first."
				}
			
			# Use the existing PolicyCreationService
			policy_service = PolicyCreationService()
			
			# Parse extracted data using existing service method
			extracted_data = frappe.parse_json(policy_doc.extracted_fields)
			parsed_data = policy_service.parse_nested_extracted_data(extracted_data)
			
			# Refresh field mappings to include latest aliases
			try:
				settings = frappe.get_single("Policy Reader Settings")
				settings.refresh_field_mappings()
				frappe.db.commit()
				frappe.logger().info("Health Policy field mappings refreshed successfully")
			except Exception as e:
				frappe.logger().warning(f"Could not refresh health policy field mappings: {str(e)}")
			
			# Get field mapping for Health policy type
			field_mapping = policy_service.get_field_mapping_for_policy_type("Health")
			
			if not field_mapping:
				return {
					"success": False,
					"error": "No field mapping found for Health policy. Please check Policy Reader Settings."
				}
			
			# Map fields using existing service method
			mapping_results = policy_service.map_fields_dynamically(
				parsed_data, field_mapping, self, "Health"
			)
			
			# Save the Health Policy with populated fields
			self.save()
			
			return {
				"success": True,
				"populated_fields": mapping_results["mapped_count"],
				"unmapped_fields": mapping_results["unmapped_fields"],
				"message": f"Successfully populated {mapping_results['mapped_count']} fields from Policy Document.",
				"debug_matches": mapping_results.get("suggestions", {}),
				"debug_parsed_keys": list(parsed_data.keys())[:10],
				"debug_unmapped": mapping_results["unmapped_fields"]
			}
			
		except Exception as e:
			frappe.log_error(f"Error populating Health Policy fields: {str(e)}", "Health Policy Population Error")
			return {
				"success": False,
				"error": str(e)
			}
