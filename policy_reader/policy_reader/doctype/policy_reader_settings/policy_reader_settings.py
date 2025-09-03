# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import json
import os
import time
from frappe.model.document import Document
from frappe.utils import now


class PolicyReaderSettings(Document):
	def validate(self):
		"""Validate Policy Reader Settings"""
		self.validate_api_key()
		self.validate_runpod_config()
		self.validate_numeric_fields()
	
	def validate_api_key(self):
		"""Validate Anthropic API key format"""
		if self.anthropic_api_key:
			if not self.anthropic_api_key.startswith('sk-ant-'):
				frappe.throw("Invalid Anthropic API key format. Key should start with 'sk-ant-'")
	
	def validate_runpod_config(self):
		"""Validate RunPod configuration"""
		if self.runpod_pod_id and self.runpod_port:
			# Validate pod ID format (alphanumeric and hyphens only)
			if not self.runpod_pod_id.replace('-', '').replace('_', '').isalnum():
				frappe.throw("Invalid RunPod Pod ID format. Use only letters, numbers, hyphens, and underscores.")
			
			# Validate port range
			if not (1 <= self.runpod_port <= 65535):
				frappe.throw("Invalid RunPod port. Port must be between 1 and 65535.")
			
			# Validate endpoint format
			if self.runpod_endpoint and not self.runpod_endpoint.startswith('/'):
				frappe.throw("RunPod endpoint must start with '/' (e.g., '/extract')")
	
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
	def test_runpod_connection(self):
		"""Test RunPod API connection and health"""
		if not self.runpod_pod_id or not self.runpod_port or not self.runpod_api_secret:
			frappe.throw("Please configure RunPod Pod ID, Port, and API Secret first")
		
		try:
			# Perform health check
			health_result = self._check_runpod_health()
			
			# Update health status
			self.update_runpod_health_status(health_result)
			
			# Show result to user
			if health_result.get("status") == "healthy":
				frappe.msgprint(
					f"✅ RunPod API is healthy! Response time: {health_result.get('response_time', 0):.2f}s",
					title="RunPod Connection Test",
					indicator="green"
				)
			else:
				frappe.msgprint(
					f"❌ RunPod API is unhealthy: {health_result.get('error', 'Unknown error')}",
					title="RunPod Connection Test",
					indicator="red"
				)
			
			return health_result
			
		except Exception as e:
			frappe.log_error(f"RunPod connection test failed: {str(e)}", "RunPod Test Error")
			frappe.throw(f"RunPod connection test failed: {str(e)}")
	
	def _check_runpod_health(self):
		"""Check RunPod API health status"""
		try:
			import requests
			
			health_url = self.get_runpod_health_url()
			start_time = time.time()
			
			response = requests.get(health_url, timeout=10)
			response_time = time.time() - start_time
			
			if response.status_code == 200:
				try:
					health_data = response.json()
					return {
						"status": "healthy",
						"response_time": response_time,
						"details": health_data,
						"status_code": response.status_code
					}
				except ValueError:
					# Response is not JSON, but status is 200
					return {
						"status": "healthy",
						"response_time": response_time,
						"details": {"raw_response": response.text},
						"status_code": response.status_code
					}
			else:
				return {
					"status": "unhealthy",
					"response_time": response_time,
					"status_code": response.status_code,
					"error": f"HTTP {response.status_code}: {response.text}"
				}
				
		except requests.exceptions.Timeout:
			return {
				"status": "error",
				"error": "Request timeout - API took too long to respond",
				"response_time": 10.0
			}
		except requests.exceptions.ConnectionError:
			return {
				"status": "error",
				"error": "Connection failed - cannot reach RunPod API",
				"response_time": 0.0
			}
		except Exception as e:
			return {
				"status": "error",
				"error": f"Unexpected error: {str(e)}",
				"response_time": 0.0
			}
	
	def update_runpod_health_status(self, health_result):
		"""Update stored health status and timestamp"""
		self.runpod_health_status = health_result.get("status", "unknown")
		self.runpod_last_health_check = now()
		self.runpod_response_time = health_result.get("response_time", 0)
		self.runpod_health_details = frappe.as_json(health_result)
		self.save()
	
	def get_runpod_base_url(self):
		"""Get RunPod base URL"""
		if not self.runpod_pod_id or not self.runpod_port:
			return None
		return f"https://{self.runpod_pod_id}-{self.runpod_port}.proxy.runpod.net"
	
	def get_runpod_health_url(self):
		"""Get RunPod health check URL"""
		base_url = self.get_runpod_base_url()
		if not base_url:
			return None
		return f"{base_url}/health"
	
	def get_runpod_extract_url(self):
		"""Get RunPod extract API URL"""
		base_url = self.get_runpod_base_url()
		if not base_url:
			return None
		endpoint = self.runpod_endpoint or "/extract"
		return f"{base_url}{endpoint}"
	
	def is_runpod_available(self):
		"""Check if RunPod is configured and healthy"""
		return (self.runpod_pod_id and 
				self.runpod_port and 
				self.runpod_api_secret and
				self.runpod_health_status == "healthy")
	
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
