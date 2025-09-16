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
		
		if self.text_truncation_limit:
			if not (1000 <= self.text_truncation_limit <= 100000):
				frappe.throw("Text Truncation Limit must be between 1,000 and 100,000 characters")
		
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
	
	def get_runpod_ocr_url(self):
		"""Get RunPod OCR-only API URL"""
		base_url = self.get_runpod_base_url()
		if not base_url:
			return None
		# Use OCR endpoint if configured, otherwise use the configured endpoint
		endpoint = self.runpod_endpoint or "/ocr-detailed"
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
	
	@frappe.whitelist()
	def refresh_extraction_prompts(self):
		"""Refresh extraction prompts from Motor Policy and Health Policy DocTypes"""
		try:
			# Build dynamic extraction prompts
			sample_text = "Sample policy document text for prompt generation"
			motor_prompt = self._build_motor_extraction_prompt(sample_text)
			health_prompt = self._build_health_extraction_prompt(sample_text)
			
			# Update cached prompts
			self.motor_extraction_prompt = motor_prompt
			self.health_extraction_prompt = health_prompt
			self.last_prompt_sync = now()
			
			# Save the document
			self.save()
			
			frappe.msgprint(f"Extraction prompts refreshed successfully. Motor prompt: {len(motor_prompt)} chars, Health prompt: {len(health_prompt)} chars.",
							title="Extraction Prompts Refreshed", indicator="green")
			
			return {
				"success": True,
				"motor_prompt_length": len(motor_prompt),
				"health_prompt_length": len(health_prompt)
			}
			
		except Exception as e:
			frappe.log_error(f"Extraction prompt refresh failed: {str(e)}", "Extraction Prompt Refresh Error")
			frappe.throw(f"Failed to refresh extraction prompts: {str(e)}")
	
	def get_cached_extraction_prompt(self, policy_type, extracted_text):
		"""Get cached extraction prompt or build dynamically if not cached"""
		try:
			truncation_limit = self.text_truncation_limit or 50000
			if policy_type.lower() == "motor":
				if self.motor_extraction_prompt:
					# Replace the sample text with actual extracted text
					return self.motor_extraction_prompt.replace("Sample policy document text for prompt generation", extracted_text[:truncation_limit])
			elif policy_type.lower() == "health":
				if self.health_extraction_prompt:
					# Replace the sample text with actual extracted text
					return self.health_extraction_prompt.replace("Sample policy document text for prompt generation", extracted_text[:truncation_limit])
			
			# Fallback to dynamic generation if not cached
			return self.build_dynamic_extraction_prompt(policy_type, extracted_text)
			
		except Exception as e:
			frappe.log_error(f"Error getting cached extraction prompt for {policy_type}: {str(e)}", "Cached Prompt Error")
			return self.build_dynamic_extraction_prompt(policy_type, extracted_text)
	
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
			
			# Build mapping from field labels to fieldnames (with aliases)
			for field in doctype_doc.fields:
				if (field.fieldname not in skip_fields and 
					field.fieldtype not in skip_fieldtypes and 
					field.label):
					
					# Add primary field label
					field_mapping[field.label] = field.fieldname
					
					# Add common aliases for natural language variations
					aliases = self._get_field_aliases(field.fieldname, field.label)
					for alias in aliases:
						field_mapping[alias] = field.fieldname
			
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
	
	def build_dynamic_extraction_prompt(self, policy_type, extracted_text):
		"""Build dynamic extraction prompt based on DocType fields"""
		try:
			if policy_type.lower() == "motor":
				return self._build_motor_extraction_prompt(extracted_text)
			elif policy_type.lower() == "health":
				return self._build_health_extraction_prompt(extracted_text)
			else:
				return self._build_generic_extraction_prompt(policy_type, extracted_text)
				
		except Exception as e:
			frappe.log_error(f"Error building dynamic extraction prompt for {policy_type}: {str(e)}", "Dynamic Prompt Error")
			return self._build_fallback_prompt(policy_type, extracted_text)
	
	def _build_motor_extraction_prompt(self, extracted_text):
		"""Build dynamic motor policy extraction prompt from DocType fields"""
		try:
			# Get Motor Policy DocType metadata
			meta = frappe.get_meta("Motor Policy")
			
			# Group fields by category
			policy_fields = []
			financial_fields = []
			vehicle_fields = []
			business_fields = []
			
			# Skip these system/layout fields
			skip_fields = {
				"policy_document", "policy_file", "naming_series", "owner", "creation", 
				"modified", "modified_by", "docstatus", "idx", "name"
			}
			
			skip_fieldtypes = {
				"Section Break", "Column Break", "Tab Break", "HTML", "Heading", "Button"
			}
			
			# Categorize fields based on fieldname patterns
			for field in meta.fields:
				if (field.fieldname not in skip_fields and 
					field.fieldtype not in skip_fieldtypes and 
					field.label):
					
					field_info = self._build_field_prompt_info(field)
					
					# Categorize by field patterns
					if any(keyword in field.fieldname.lower() for keyword in ['policy', 'date']):
						policy_fields.append(field_info)
					elif any(keyword in field.fieldname.lower() for keyword in ['premium', 'sum', 'gst', 'ncb', 'amount']):
						financial_fields.append(field_info)
					elif any(keyword in field.fieldname.lower() for keyword in ['vehicle', 'make', 'model', 'engine', 'chassis', 'fuel', 'cc', 'rto']):
						vehicle_fields.append(field_info)
					elif any(keyword in field.fieldname.lower() for keyword in ['customer', 'payment', 'bank', 'branch']):
						business_fields.append(field_info)
					else:
						policy_fields.append(field_info)  # Default to policy fields
			
			# Build categorized prompt
			prompt_sections = []
			
			if policy_fields:
				prompt_sections.append("POLICY INFORMATION:\n" + "\n".join(policy_fields))
			
			if financial_fields:
				prompt_sections.append("FINANCIAL DETAILS:\n" + "\n".join(financial_fields))
			
			if vehicle_fields:
				prompt_sections.append("VEHICLE INFORMATION:\n" + "\n".join(vehicle_fields))
			
			if business_fields:
				prompt_sections.append("BUSINESS INFORMATION:\n" + "\n".join(business_fields))
			
			# Get truncation limit from settings
			truncation_limit = self.text_truncation_limit or 50000
			
			# Build complete prompt
			prompt = f"""Extract these motor insurance policy fields as JSON:

{chr(10).join(prompt_sections)}

EXTRACTION RULES:
- Dates: DD/MM/YYYY format only (clean "FROM 15/03/2024" to "15/03/2024")
- Currency: Extract digits only (remove ₹, Rs., commas, /-)
- Numbers: Digits only (remove descriptive text like "seater")
- Text: Clean format (remove extra prefixes/suffixes)
- Select: Match exact options (case-insensitive)
- Missing fields: null

EXAMPLES:
- "FROM 15/03/2024" → "15/03/2024"
- "Rs. 25,000/-" → "25000"
- "5 seater capacity" → "5"
- "DL-01-AA-1234 (Vehicle)" → "DL-01-AA-1234"

Document: {extracted_text[:truncation_limit]}

Return only valid JSON:"""
			
			return prompt
			
		except Exception as e:
			frappe.log_error(f"Error building motor extraction prompt: {str(e)}", "Motor Prompt Build Error")
			return self._build_fallback_prompt("motor", extracted_text)
	
	def _build_health_extraction_prompt(self, extracted_text):
		"""Build dynamic health policy extraction prompt from DocType fields"""
		try:
			# Get Health Policy DocType metadata
			meta = frappe.get_meta("Health Policy")
			
			# Group fields by category
			policy_fields = []
			personal_fields = []
			financial_fields = []
			
			# Skip these system/layout fields
			skip_fields = {
				"policy_document", "policy_file", "naming_series", "owner", "creation", 
				"modified", "modified_by", "docstatus", "idx", "name"
			}
			
			skip_fieldtypes = {
				"Section Break", "Column Break", "Tab Break", "HTML", "Heading", "Button"
			}
			
			# Categorize fields based on fieldname patterns
			for field in meta.fields:
				if (field.fieldname not in skip_fields and 
					field.fieldtype not in skip_fieldtypes and 
					field.label):
					
					field_info = self._build_field_prompt_info(field)
					
					# Categorize by field patterns
					if any(keyword in field.fieldname.lower() for keyword in ['policy', 'date', 'period']):
						policy_fields.append(field_info)
					elif any(keyword in field.fieldname.lower() for keyword in ['insured', 'name', 'birth', 'relationship', 'nominee']):
						personal_fields.append(field_info)
					elif any(keyword in field.fieldname.lower() for keyword in ['premium', 'sum', 'gst', 'amount']):
						financial_fields.append(field_info)
					else:
						policy_fields.append(field_info)  # Default to policy fields
			
			# Build categorized prompt
			prompt_sections = []
			
			if policy_fields:
				prompt_sections.append("POLICY INFORMATION:\n" + "\n".join(policy_fields))
			
			if personal_fields:
				prompt_sections.append("PERSONAL INFORMATION:\n" + "\n".join(personal_fields))
			
			if financial_fields:
				prompt_sections.append("FINANCIAL DETAILS:\n" + "\n".join(financial_fields))
			
			# Get truncation limit from settings
			truncation_limit = self.text_truncation_limit or 50000
			
			# Build complete prompt
			prompt = f"""Extract these health insurance policy fields as JSON:

{chr(10).join(prompt_sections)}

EXTRACTION RULES:
- Dates: DD/MM/YYYY format only
- Currency: Extract digits only (remove currency symbols)
- Text: Clean format (core information only)
- Missing fields: null

Document: {extracted_text[:truncation_limit]}

Return only valid JSON:"""
			
			return prompt
			
		except Exception as e:
			frappe.log_error(f"Error building health extraction prompt: {str(e)}", "Health Prompt Build Error")
			return self._build_fallback_prompt("health", extracted_text)
	
	def _build_field_prompt_info(self, field):
		"""Build prompt information for a specific field using natural field labels"""
		# Use the natural field label as the extraction field name
		field_name = field.label.strip()
		
		# Build field description with format hints
		if field.fieldtype == "Date":
			return f"- {field_name}: Date in DD/MM/YYYY format"
		elif field.fieldtype in ["Currency", "Float"]:
			return f"- {field_name}: Numeric amount (digits only)"
		elif field.fieldtype == "Int":
			return f"- {field_name}: Integer number"
		elif field.fieldtype == "Select" and field.options:
			options_list = [opt.strip() for opt in field.options.split('\n') if opt.strip()]
			return f"- {field_name}: Select from [{', '.join(options_list)}]"
		else:
			return f"- {field_name}: Text format"
	
	
	def _build_generic_extraction_prompt(self, policy_type, extracted_text):
		"""Build generic extraction prompt for unknown policy types"""
		truncation_limit = self.text_truncation_limit or 50000
		return f"""Extract relevant information from this {policy_type} insurance policy document.
		
Return clean, structured data as JSON format.
- Dates: DD/MM/YYYY format
- Numbers: Digits only
- Text: Clean format

Document: {extracted_text[:truncation_limit]}

Return only valid JSON:"""
	
	def _build_fallback_prompt(self, policy_type, extracted_text):
		"""Build simple fallback prompt if dynamic generation fails"""
		truncation_limit = self.text_truncation_limit or 50000
		return f"""Extract information from this {policy_type} insurance policy document.
		
Document: {extracted_text[:truncation_limit]}

Return data as valid JSON:"""
	
	def _get_field_aliases(self, fieldname, field_label):
		"""Get common aliases for field names to handle natural language variations"""
		aliases = []
		
		# Common field name variations based on fieldname and label patterns
		field_aliases = {
			# Policy fields
			'policy_no': ['Policy Number', 'PolicyNumber', 'Policy Num', 'PolicyNo', 'policyNo', 'policyNumber'],
			'policy_type': ['PolicyType', 'policyType'],
			'policy_issuance_date': ['Policy Issuance Date', 'Issuance Date', 'PolicyIssuanceDate', 'policyIssuanceDate'],
			'policy_start_date': ['Policy Start Date', 'Start Date', 'PolicyStartDate', 'From Date', 'policyStartDate'],
			'policy_expiry_date': ['Policy Expiry Date', 'Expiry Date', 'PolicyExpiryDate', 'To Date', 'End Date', 'policyExpiryDate'],
			'policy_biz_type': ['PolicyBiz Type', 'policyBizType', 'policyBizType'],
			'new_renewal': ['New/Renewal', 'newRenewal'],
			
			# Vehicle fields
			'vehicle_no': ['Vehicle Number', 'VehicleNumber', 'VehicleNo', 'Registration Number', 'Registration No', 'vehicleNo', 'vehicleNumber'],
			'make': ['Make', 'Vehicle Make', 'make'],
			'model': ['Model', 'Vehicle Model', 'model'],
			'variant': ['Variant', 'Vehicle Variant', 'variant'],
			'year_of_man': ['Year of Manufacture', 'Manufacturing Year', 'YearOfManufacture', 'Year', 'Model Year', 'yearOfManufacture'],
			
			# Engine/Chassis fields (handle the typo in DocType)
			'chasis_no': ['Chassis Number', 'ChassisNumber', 'Chasis Number', 'ChasisNumber', 'Chassis No', 'Chasis No', 'chasisNo', 'chassisNo', 'ChasisNo'],
			'engine_no': ['Engine Number', 'EngineNumber', 'Engine No', 'EngineNo', 'engineNo'],
			'cc': ['CC', 'Engine Capacity', 'Cubic Capacity', 'cc'],
			'fuel': ['Fuel', 'Fuel Type', 'FuelType', 'fuel'],
			
			# Financial fields
			'sum_insured': ['Sum Insured', 'SumInsured', 'Insured Amount', 'Coverage Amount', 'sumInsured'],
			'net_od_premium': ['Net Premium', 'NetPremium', 'Net OD Premium', 'NetODPremium', 'OD Premium', 'netOdPremium'],
			'tp_premium': ['TP Premium', 'TPPremium', 'Third Party Premium', 'tpPremium'],
			'gst': ['GST', 'Tax', 'Service Tax', 'gst'],
			'ncb': ['NCB', 'No Claim Bonus', 'ncb'],
			
			# Registration fields
			'rto_code': ['RTO Code', 'RTOCode', 'RTO', 'rtoCode'],
			'vehicle_category': ['Vehicle Category', 'VehicleCategory', 'Vehicle Class', 'Category', 'vehicleCategory'],
			'passenger_gvw': ['Passenger GVW', 'PassengerGVW', 'GVW', 'passengerGvw'],
			
			# Business/Customer fields (from your extracted data)
			'customer_code': ['Customer Code', 'CustomerCode', 'customerCode'],
			'insurer_branch_code': ['Insurer Branch Code', 'InsurerBranchCode', 'insurerBranchCode'],
			'payment_mode': ['Payment Mode', 'PaymentMode', 'paymentMode'],
			'bank_name': ['Bank Name', 'BankName', 'bankName'],
			'payment_transaction_no': ['Payment Transaction No', 'PaymentTransactionNo', 'paymentTransactionNo'],
			'branch_code': ['Branch Code', 'BranchCode', 'branchCode'],
			'customer_group': ['Customer Group', 'CustomerGroup', 'customerGroup'],
			'customer_title': ['Customer Title', 'CustomerTitle', 'customerTitle'],
			'customer_name': ['Customer Name', 'CustomerName', 'customerName'],
			'customer_id': ['Customer ID', 'CustomerID', 'customerId'],
			
			# Health policy fields
			'policy_number': ['Policy Number', 'PolicyNumber', 'Policy No'],
			'insured_name': ['Insured Name', 'InsuredName', 'Name of Insured'],
			'policy_start_date': ['Policy Start Date', 'Start Date', 'From Date'],
			'policy_end_date': ['Policy End Date', 'End Date', 'To Date', 'Expiry Date'],
			'customer_code': ['Customer Code', 'CustomerCode'],
			'net_premium': ['Net Premium', 'NetPremium', 'Premium Amount'],
			'policy_period': ['Policy Period', 'PolicyPeriod', 'Period'],
			'issuing_office': ['Issuing Office', 'IssuingOffice', 'Office'],
			'relationship_to_policyholder': ['Relationship', 'Relation', 'RelationshipToPolicyholder'],
			'date_of_birth': ['Date of Birth', 'DateOfBirth', 'DOB', 'Birth Date'],
			'insured_name_2': ['Insured Name 2', 'Second Insured', 'InsuredName2'],
			'nominee_name': ['Nominee Name', 'NomineeName', 'Nominee'],
			'insured_code': ['Insured Code', 'InsuredCode']
		}
		
		# Get aliases for this specific field
		if fieldname in field_aliases:
			aliases = field_aliases[fieldname]
		
		# Don't add the original label as an alias if it's already the primary key
		aliases = [alias for alias in aliases if alias != field_label]
		
		return aliases

@frappe.whitelist()
def get_runpod_health_info():
	"""Get RunPod health information for JavaScript"""
	try:
		settings = frappe.get_single("Policy Reader Settings")
		
		return {
			"status": settings.runpod_health_status or "unknown",
			"response_time": settings.runpod_response_time or 0.0,
			"last_check": settings.runpod_last_health_check,
			"configured": bool(settings.runpod_pod_id and settings.runpod_port and settings.runpod_api_secret)
		}
	except Exception as e:
		frappe.log_error(f"Error getting RunPod health info: {str(e)}", "RunPod Health Info Error")
		return {
			"status": "error",
			"response_time": 0.0,
			"last_check": None,
			"configured": False
		}
