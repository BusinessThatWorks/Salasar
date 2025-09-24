# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import json
import os
import time
from frappe.model.document import Document
from frappe.utils import now
from frappe.utils import cstr


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
		"""Refresh field mappings using default, DocType-independent generator"""
		try:
			# Build mapping for both policy types using default generator
			motor_mapping = self.build_default_field_mapping("motor")
			health_mapping = self.build_default_field_mapping("health")
			
			frappe.logger().info(f"Built motor mapping: {len(motor_mapping)} fields")
			frappe.logger().info(f"Built health mapping: {len(health_mapping)} fields")
			frappe.logger().info(f"Sample health mapping: {dict(list(health_mapping.items())[:5])}")
			
			# Update cached mappings
			self.motor_policy_fields = frappe.as_json(motor_mapping)
			self.health_policy_fields = frappe.as_json(health_mapping)
			self.last_field_sync = now()
			
			# Save the document
			self.save()
			
			frappe.logger().info("Field mappings saved to database")
			
			frappe.msgprint(
				f"Field mappings refreshed successfully (DocType-independent). Motor: {len(motor_mapping)} fields, Health: {len(health_mapping)} fields.",
				title="Field Mappings Refreshed", indicator="green"
			)
			
			return {
				"success": True, 
				"motor_fields": len(motor_mapping),
				"health_fields": len(health_mapping)
			}
			
		except Exception as e:
			frappe.log_error(f"Field mapping refresh failed: {str(e)}", "Field Mapping Refresh Error")
			frappe.logger().error(f"Field mapping refresh failed: {str(e)}")
			frappe.throw(f"Failed to refresh field mappings: {str(e)}")

	def build_default_field_mapping(self, policy_type):
		"""Build a default mapping from known aliases to canonical fieldnames without DocType dependency"""
		policy_type_lower = (policy_type or "").lower()
		mapping = {}
		
		# Define canonical fieldnames and their aliases per policy type
		if policy_type_lower == "motor":
			alias_map = {
				# Policy fields
				"policy_no": ["Policy Number", "PolicyNumber", "Policy Num", "PolicyNo", "policyNo", "policyNumber", "policy_no", "Policy_No"],
				"policy_type": ["PolicyType", "policyType", "policy_type", "Policy_Type"],
				"policy_issuance_date": ["Policy Issuance Date", "Issuance Date", "PolicyIssuanceDate", "policyIssuanceDate", "policy_issuance_date", "Policy_Issuance_Date"],
				"policy_start_date": ["Policy Start Date", "Start Date", "PolicyStartDate", "From Date", "policyStartDate", "policy_start_date", "Policy_Start_Date"],
				"policy_expiry_date": ["Policy Expiry Date", "Expiry Date", "PolicyExpiryDate", "To Date", "End Date", "policyExpiryDate", "policy_expiry_date", "Policy_Expiry_Date"],
				"policy_biz_type": ["PolicyBiz Type", "policyBizType", "PolicyBiz_Type"],
				"new_renewal": ["New/Renewal", "newRenewal", "New_Renewal"],
				# Vehicle fields
				"vehicle_no": ["Vehicle Number", "VehicleNumber", "VehicleNo", "Registration Number", "Registration No", "Registration no", "Registration no.", "Registration No.", "Regn No", "Regn No.", "Regn. No", "Regn. No.", "Reg No", "Reg No.", "Reg. No", "Reg. No.", "vehicleNo", "vehicleNumber", "Vehicle_No"],
				"make": ["Make", "Vehicle Make", "make"],
				"model": ["Model", "Vehicle Model", "model"],
				"variant": ["Variant", "Vehicle Variant", "variant"],
				"year_of_man": ["Year of Manufacture", "Manufacturing Year", "YearOfManufacture", "Year", "Model Year", "yearOfManufacture", "Year_of_Manufacture", "Year of Mfg", "Year Of Manufacturing", "Year of Man"],
				# Engine/Chassis
				"chasis_no": ["Chassis Number", "ChassisNumber", "Chasis Number", "ChasisNumber", "Chassis No", "Chasis No", "chasisNo", "chassisNo", "ChasisNo", "chasis_no", "Chasis_No"],
				"engine_no": ["Engine Number", "EngineNumber", "Engine No", "EngineNo", "engineNo", "engine_no", "Engine_No"],
				"cc": ["CC", "Engine Capacity", "Cubic Capacity", "cc", "CC/KW", "Cubic Capcity", "Cubic Capacity/Kilowatt", "Cubic Capcity/Kilowatt", "CCIKW"],
				"fuel": ["Fuel", "Fuel Type", "FuelType", "fuel"],
				# Financial
				"sum_insured": ["Sum Insured", "SumInsured", "Insured Amount", "Coverage Amount", "sumInsured", "sum_insured", "Sum_Insured", "Insured Declared Value", "IDV", "Total Value"],
				"net_od_premium": ["Net Premium", "NetPremium", "Net OD Premium", "NetODPremium", "OD Premium", "netOdPremium", "net_od_premium", "Net_OD_Premium", "Total OD Premium", "Calculated OD Premium"],
				"tp_premium": ["TP Premium", "TPPremium", "Third Party Premium", "tpPremium", "tp_premium", "TP_Premium"],
				"gst": ["GST", "Tax", "Service Tax", "gst"],
				"ncb": ["NCB", "No Claim Bonus", "ncb"],
				# Registration/Category
				"rto_code": ["RTO Code", "RTOCode", "RTO", "rtoCode", "RTO_Code"],
				"vehicle_category": ["Vehicle Category", "VehicleCategory", "Vehicle Class", "Category", "vehicleCategory", "Vehicle_Category"],
				"passenger_gvw": ["Passenger GVW", "PassengerGVW", "GVW", "passengerGvw", "Passenger_GVW"],
				# Business/Customer
				"customer_code": ["Customer Code", "CustomerCode", "customerCode", "customer_code", "Customer_Code"],
				"insurer_branch_code": ["Insurer Branch Code", "InsurerBranchCode", "insurerBranchCode", "insurer_branch_code", "Insurer_Branch_Code"],
				"payment_mode": ["Payment Mode", "PaymentMode", "paymentMode", "payment_mode", "Payment_Mode"],
				"bank_name": ["Bank Name", "BankName", "bankName", "bank_name", "Bank_Name"],
				"payment_transaction_no": ["Payment Transaction No", "PaymentTransactionNo", "paymentTransactionNo", "payment_transaction_no", "Payment_Transaction_No"],
				"branch_code": ["Branch Code", "BranchCode", "branchCode", "branch_code", "Branch_Code"],
				"customer_group": ["Customer Group", "CustomerGroup", "customerGroup", "customer_group", "Customer_Group"],
				"customer_title": ["Customer Title", "CustomerTitle", "customerTitle", "customer_title", "Customer_Title"],
				"customer_name": ["Customer Name", "CustomerName", "customerName", "customer_name", "Customer_Name"],
				"customer_id": ["Customer ID", "CustomerID", "customerId", "Customer_ID"],
				"mobile_no": ["Mobile Number", "MobileNumber", "Mobile No", "MobileNo", "mobile_no", "Mobile_Number"],
				"email_id": ["Email ID", "EmailID", "Email", "email_id", "Email_ID"],
				"dob_doi": ["DOB/DOI", "Date of Birth", "DateOfBirth", "DOB", "dob_doi", "DOB_DOI"],
				"gender": ["Gender", "gender"],
				"cse_id": ["CSE ID", "CSEID", "cse_id", "CSE_ID"],
				"rm_id": ["RM ID", "RMID", "rm_id", "RM_ID"],
				"old_control_number": ["Old Control Number", "OldControlNumber", "old_control_number", "Old_Control_Number"],
			}
		elif policy_type_lower == "health":
			alias_map = {
				# Customer and Policy Info
				"customer_code": ["Customer Code", "CustomerCode", "customer_code"],
				"pos_policy": ["Pos Policy", "POS Policy", "pos_policy"],
				"policy_biz_type": ["PolicyBiz Type", "Policy Biz Type", "PolicyBizType", "policy_biz_type"],
				"insurer_branch_code": ["Insurer Branch Code", "InsurerBranchCode", "insurer_branch_code"],
				
				# Policy Dates
				"policy_issuance_date": ["PolicyIssuanceDate", "Policy Issuance Date", "Issuance Date", "policy_issuance_date"],
				"policy_start_date": ["PolicyStartDate", "Policy Start Date", "Start Date", "From Date", "policy_start_date"],
				"policy_expiry_date": ["PolicyExpiryDate", "Policy Expiry Date", "Expiry Date", "To Date", "End Date", "policy_expiry_date"],
				
				# Policy Details
				"policy_type": ["Policy Type", "PolicyType", "policy_type"],
				"policy_no": ["PolicyNo", "Policy No", "Policy Number", "PolicyNumber", "policy_no"],
				"plan_name": ["Plan Name", "PlanName", "plan_name"],
				"is_renewable": ["IsRenewable", "Is Renewable", "Renewable", "is_renewable"],
				"prev_policy": ["PrevPolicy", "Previous Policy", "Prev Policy", "prev_policy"],
				
				# Insured Person Details
				"insured1name": ["INSURED1NAME", "Insured Name", "Insured 1 Name", "Insured1Name", "insured1name"],
				"insured1gender": ["INSURED1GENDER", "Insured Gender", "Insured 1 Gender", "Gender", "insured1gender"],
				"insured1dob": ["INSURED1DOB", "Insured DOB", "Insured 1 DOB", "Date of Birth", "DOB", "insured1dob"],
				"insured1relation": ["INSURED1RELATION", "Insured Relation", "Insured 1 Relation", "Relationship", "Relation", "insured1relation"],
				
				# Financial Details
				"sum_insured": ["Sum Insured", "SumInsured", "Insured Amount", "Coverage Amount", "sum_insured"],
				"net_od_premium": ["Net/OD Premium", "Net Premium", "NetPremium", "Premium Amount", "net_od_premium"],
				"gst": ["GST", "Tax", "Service Tax", "gst"],
				"stamp_duty": ["StampDuty", "Stamp Duty", "stamp_duty"],
				
				# Payment Details
				"payment_mode": ["Payment Mode", "PaymentMode", "payment_mode"],
				"bank_name": ["Bank Name", "BankName", "bank_name"],
				"payment_transaction_no": ["Payment TransactionNo", "Payment Transaction No", "Transaction No", "payment_transaction_no"],
				
				# Additional Fields
				"remarks": ["Remarks", "Comments", "Notes", "remarks"],
				"policy_status": ["Policy Status", "PolicyStatus", "Status", "policy_status"],
			}
		else:
			alias_map = {}
		
		# Build mapping: include alias → canonical fieldname, and also canonical fieldname as a key to itself
		for canonical_field, aliases in alias_map.items():
			mapping[canonical_field] = canonical_field
			for alias in aliases:
				mapping[alias] = canonical_field
		
		return mapping

	def build_field_mapping_from_doctype(self, doctype_name):
		"""Deprecated: Build field mapping from DocType definition.
		Now delegates to DocType-independent default mapping for compatibility."""
		try:
			policy_type = "motor" if "motor" in (doctype_name or "").lower() else "health"
			return self.build_default_field_mapping(policy_type)
		except Exception as e:
			frappe.log_error(f"Error building default mapping for {doctype_name}: {str(e)}", "Field Mapping Build Error")
			raise
	
	def get_cached_field_mapping(self, policy_type):
		"""Get cached field mapping for policy type"""
		try:
			frappe.logger().info(f"Getting cached field mapping for {policy_type}")
			if policy_type.lower() == "motor":
				frappe.logger().info(f"Motor policy fields exist: {bool(self.motor_policy_fields)}")
				if self.motor_policy_fields:
					mapping = frappe.parse_json(self.motor_policy_fields)
					frappe.logger().info(f"Motor mapping loaded: {len(mapping)} entries")
					return mapping
			elif policy_type.lower() == "health":
				frappe.logger().info(f"Health policy fields exist: {bool(self.health_policy_fields)}")
				if self.health_policy_fields:
					mapping = frappe.parse_json(self.health_policy_fields)
					frappe.logger().info(f"Health mapping loaded: {len(mapping)} entries")
					return mapping
			
			# Return empty dict if no cached mapping found
			frappe.logger().info(f"No cached mapping found for {policy_type}")
			return {}
			
		except Exception as e:
			frappe.log_error(f"Error getting cached field mapping for {policy_type}: {str(e)}", "Field Mapping Cache Error")
			frappe.logger().error(f"Error getting cached field mapping for {policy_type}: {str(e)}")
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
			truncation_limit = 200000  # Use higher limit since text_truncation_limit was removed
			
			# Build complete prompt
			prompt = f"""Extract these motor insurance policy fields as FLAT JSON (field_name: value format):

{chr(10).join(prompt_sections)}

EXTRACTION RULES:
- Dates: DD/MM/YYYY format only (clean "FROM 15/03/2024" to "15/03/2024")
- Currency: Extract digits only (remove ₹, Rs., commas, /-)
- Numbers: Digits only (remove descriptive text like "seater")
- Text: Clean format (remove extra prefixes/suffixes)
- Select: Match exact options (case-insensitive)
- Missing fields: null
- Chassis/Engine Numbers: Extract from combined formats

EXAMPLES:
- "FROM 15/03/2024" → "15/03/2024"
- "Rs. 25,000/-" → "25000"
- "5 seater capacity" → "5"
- "DL-01-AA-1234 (Vehicle)" → "DL-01-AA-1234"
- "Chassis no./Engine no.: MATRC4GGA91 J57810/GG91.76864" → ChasisNo: "MATRC4GGA91", EngineNo: "J57810"

IMPORTANT: Return ONE FLAT JSON object with all fields at the same level. 
DO NOT group fields by categories. DO NOT create nested structures.

REQUIRED FORMAT:
{{
  "policy_no": "value",
  "chasis_no": "value", 
  "engine_no": "value",
  "make": "value",
  ...all fields in one flat structure
}}

Document: {extracted_text[:truncation_limit]}

RESPOND WITH VALID FLAT JSON ONLY - NO EXPLANATIONS, NO MARKDOWN, NO CODE BLOCKS."""
			
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
			truncation_limit = 200000  # Use higher limit since text_truncation_limit was removed
			
			# Build complete prompt
			prompt = f"""Extract these health insurance policy fields as FLAT JSON (field_name: value format):

{chr(10).join(prompt_sections)}

EXTRACTION RULES:
- Dates: DD/MM/YYYY format only
- Currency: Extract digits only (remove currency symbols)
- Text: Clean format (core information only)
- Missing fields: null

IMPORTANT: Return ONE FLAT JSON object with all fields at the same level. 
DO NOT group fields by categories. DO NOT create nested structures.

REQUIRED FORMAT:
{{
  "policy_no": "value",
  "insured_name": "value", 
  "premium": "value",
  "sum_insured": "value",
  ...all fields in one flat structure
}}

Document: {extracted_text[:truncation_limit]}

RESPOND WITH VALID FLAT JSON ONLY - NO EXPLANATIONS, NO MARKDOWN, NO CODE BLOCKS."""
			
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
		truncation_limit = 200000  # Use higher limit since text_truncation_limit was removed
		return f"""Extract relevant information from this {policy_type} insurance policy document.
		
Return clean, structured data as JSON format.
- Dates: DD/MM/YYYY format
- Numbers: Digits only
- Text: Clean format

Document: {extracted_text[:truncation_limit]}

Return only valid JSON:"""
	
	def _build_fallback_prompt(self, policy_type, extracted_text):
		"""Build simple fallback prompt if dynamic generation fails"""
		truncation_limit = 200000  # Use higher limit since text_truncation_limit was removed
		return f"""Extract information from this {policy_type} insurance policy document.
		
Document: {extracted_text[:truncation_limit]}

Return data as valid JSON:"""
	
	def _get_field_aliases(self, fieldname, field_label):
		"""Get common aliases for field names to handle natural language variations"""
		aliases = []
		
		# Common field name variations based on fieldname and label patterns
		field_aliases = {
			# Policy fields
			'policy_no': ['Policy Number', 'PolicyNumber', 'Policy Num', 'PolicyNo', 'policyNo', 'policyNumber', 'policy_no', 'Policy_No'],
			'policy_type': ['PolicyType', 'policyType', 'policy_type', 'Policy_Type'],
			'policy_issuance_date': ['Policy Issuance Date', 'Issuance Date', 'PolicyIssuanceDate', 'policyIssuanceDate', 'policy_issuance_date', 'Policy_Issuance_Date'],
			'policy_start_date': ['Policy Start Date', 'Start Date', 'PolicyStartDate', 'From Date', 'policyStartDate', 'policy_start_date', 'Policy_Start_Date'],
			'policy_expiry_date': ['Policy Expiry Date', 'Expiry Date', 'PolicyExpiryDate', 'To Date', 'End Date', 'policyExpiryDate', 'policy_expiry_date', 'Policy_Expiry_Date'],
			'policy_biz_type': ['PolicyBiz Type', 'policyBizType', 'policyBizType', 'PolicyBiz_Type'],
			'new_renewal': ['New/Renewal', 'newRenewal', 'New_Renewal'],
			
			# Vehicle fields
			'vehicle_no': ['Vehicle Number', 'VehicleNumber', 'VehicleNo', 'Registration Number', 'Registration No', 'Registration no', 'Registration no.', 'Registration No.', 'Regn No', 'Regn No.', 'Regn. No', 'Regn. No.', 'Reg No', 'Reg No.', 'Reg. No', 'Reg. No.', 'vehicleNo', 'vehicleNumber', 'Vehicle_No'],
			'make': ['Make', 'Vehicle Make', 'make'],
			'model': ['Model', 'Vehicle Model', 'model'],
			'variant': ['Variant', 'Vehicle Variant', 'variant'],
			'year_of_man': ['Year of Manufacture', 'Manufacturing Year', 'YearOfManufacture', 'Year', 'Model Year', 'yearOfManufacture', 'Year_of_Manufacture'],
			
			# Engine/Chassis fields (handle the typo in DocType)
			'chasis_no': ['Chassis Number', 'ChassisNumber', 'Chasis Number', 'ChasisNumber', 'Chassis No', 'Chasis No', 'chasisNo', 'chassisNo', 'ChasisNo', 'chasis_no', 'Chasis_No'],
			'engine_no': ['Engine Number', 'EngineNumber', 'Engine No', 'EngineNo', 'engineNo', 'engine_no', 'Engine_No'],
			'cc': ['CC', 'Engine Capacity', 'Cubic Capacity', 'cc'],
			'fuel': ['Fuel', 'Fuel Type', 'FuelType', 'fuel'],
			
			# Financial fields
			'sum_insured': ['Sum Insured', 'SumInsured', 'Insured Amount', 'Coverage Amount', 'sumInsured', 'sum_insured', 'Sum_Insured'],
			'net_od_premium': ['Net Premium', 'NetPremium', 'Net OD Premium', 'NetODPremium', 'OD Premium', 'netOdPremium', 'net_od_premium', 'Net_OD_Premium'],
			'tp_premium': ['TP Premium', 'TPPremium', 'Third Party Premium', 'tpPremium', 'tp_premium', 'TP_Premium'],
			'gst': ['GST', 'Tax', 'Service Tax', 'gst'],
			'ncb': ['NCB', 'No Claim Bonus', 'ncb'],
			
			# Registration fields
			'rto_code': ['RTO Code', 'RTOCode', 'RTO', 'rtoCode', 'RTO_Code'],
			'vehicle_category': ['Vehicle Category', 'VehicleCategory', 'Vehicle Class', 'Category', 'vehicleCategory', 'Vehicle_Category'],
			'passenger_gvw': ['Passenger GVW', 'PassengerGVW', 'GVW', 'passengerGvw', 'Passenger_GVW'],
			
			# Business/Customer fields (from your extracted data)
			'customer_code': ['Customer Code', 'CustomerCode', 'customerCode', 'customer_code', 'Customer_Code'],
			'insurer_branch_code': ['Insurer Branch Code', 'InsurerBranchCode', 'insurerBranchCode', 'insurer_branch_code', 'Insurer_Branch_Code'],
			'payment_mode': ['Payment Mode', 'PaymentMode', 'paymentMode', 'payment_mode', 'Payment_Mode'],
			'bank_name': ['Bank Name', 'BankName', 'bankName', 'bank_name', 'Bank_Name'],
			'payment_transaction_no': ['Payment Transaction No', 'PaymentTransactionNo', 'paymentTransactionNo', 'payment_transaction_no', 'Payment_Transaction_No'],
			'branch_code': ['Branch Code', 'BranchCode', 'branchCode', 'branch_code', 'Branch_Code'],
			'customer_group': ['Customer Group', 'CustomerGroup', 'customerGroup', 'customer_group', 'Customer_Group'],
			'customer_title': ['Customer Title', 'CustomerTitle', 'customerTitle', 'customer_title', 'Customer_Title'],
			'customer_name': ['Customer Name', 'CustomerName', 'customerName', 'customer_name', 'Customer_Name'],
			'customer_id': ['Customer ID', 'CustomerID', 'customerId', 'Customer_ID'],
			'mobile_no': ['Mobile Number', 'MobileNumber', 'Mobile No', 'MobileNo', 'mobile_no', 'Mobile_Number'],
			'email_id': ['Email ID', 'EmailID', 'Email', 'email_id', 'Email_ID'],
			'dob_doi': ['DOB/DOI', 'Date of Birth', 'DateOfBirth', 'DOB', 'dob_doi', 'DOB_DOI'],
			'gender': ['Gender', 'gender'],
			'cse_id': ['CSE ID', 'CSEID', 'cse_id', 'CSE_ID'],
			'rm_id': ['RM ID', 'RMID', 'rm_id', 'RM_ID'],
			'old_control_number': ['Old Control Number', 'OldControlNumber', 'old_control_number', 'Old_Control_Number'],
			
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

	def _normalize_alias_key(self, text):
		"""Normalize alias keys for consistent matching (lowercase, alnum+space)"""
		try:
			if not text:
				return ""
			value = cstr(text).strip().lower()
			import re
			value = re.sub(r"[^a-z0-9]+", " ", value)
			value = " ".join(part for part in value.split() if part)
			return value
		except Exception:
			return cstr(text or "").strip().lower()

	def _get_mapping_container_and_key(self, policy_type):
		"""Return (container_fieldname, mapping_dict) for the given policy_type"""
		ptype = (policy_type or "").lower()
		if ptype == "motor":
			container = "motor_policy_fields"
			data = frappe.parse_json(self.motor_policy_fields) if self.motor_policy_fields else {}
		elif ptype == "health":
			container = "health_policy_fields"
			data = frappe.parse_json(self.health_policy_fields) if self.health_policy_fields else {}
		else:
			container = None
			data = {}
		return container, (data or {})

	@frappe.whitelist()
	def add_alias(self, policy_type, canonical_field, alias):
		"""Add a single alias → canonical mapping and persist it"""
		container, mapping = self._get_mapping_container_and_key(policy_type)
		if not container:
			frappe.throw("Unsupported policy type")
		if not canonical_field or not alias:
			frappe.throw("Both canonical_field and alias are required")
		# Preserve canonical self-mapping
		mapping.setdefault(canonical_field, canonical_field)
		# Add alias mapping
		mapping[alias] = canonical_field
		# Save back
		setattr(self, container, frappe.as_json(mapping))
		self.last_field_sync = now()
		self.save()
		return {"success": True, "canonical": canonical_field, "alias": alias}

	@frappe.whitelist()
	def bulk_add_aliases(self, policy_type, aliases_json):
		"""Bulk add aliases. aliases_json can be:
		- dict of canonical_field -> [aliases]
		- or dict of alias -> canonical_field
		"""
		container, mapping = self._get_mapping_container_and_key(policy_type)
		if not container:
			frappe.throw("Unsupported policy type")
		try:
			data = frappe.parse_json(aliases_json) if isinstance(aliases_json, str) else aliases_json
			if not isinstance(data, dict):
				frappe.throw("aliases_json must be a JSON object")
			added = 0
			# Heuristic: detect format by inspecting first value
			items = list(data.items())
			if items and isinstance(items[0][1], list):
				# canonical -> [aliases]
				for canonical, aliases in data.items():
					mapping.setdefault(canonical, canonical)
					for alias in aliases or []:
						if alias:
							mapping[alias] = canonical
							added += 1
			else:
				# alias -> canonical
				for alias, canonical in data.items():
					if canonical:
						mapping.setdefault(canonical, canonical)
						mapping[alias] = canonical
						added += 1
			setattr(self, container, frappe.as_json(mapping))
			self.last_field_sync = now()
			self.save()
			return {"success": True, "added": added}
		except Exception as e:
			frappe.throw(f"Failed to bulk add aliases: {str(e)}")

	@frappe.whitelist()
	def list_aliases(self, policy_type, canonical_field=None):
		"""List all aliases for a policy type, or for a specific canonical field"""
		_, mapping = self._get_mapping_container_and_key(policy_type)
		if not mapping:
			return {}
		if canonical_field:
			aliases = [k for k, v in mapping.items() if v == canonical_field and k != canonical_field]
			return {canonical_field: sorted(aliases)}
		# Build reverse index: canonical -> [aliases]
		result = {}
		for key, value in mapping.items():
			if key == value:
				result.setdefault(value, [])
			else:
				result.setdefault(value, []).append(key)
		return {k: sorted(v) for k, v in result.items()}

	def build_prompt_from_mapping(self, policy_type, extracted_text):
		"""Build a full extraction prompt from the active alias→canonical mapping.
		Always enumerates all canonical keys and provides alias guidance.
		"""
		try:
			truncation_limit = 200000
			ptype = (policy_type or "").lower()
			# Get mapping from cache; if empty, build defaults
			mapping = self.get_cached_field_mapping(ptype) or self.build_default_field_mapping(ptype)
			if not isinstance(mapping, dict) or not mapping:
				return self._build_fallback_prompt(ptype, extracted_text)
			
			# Canonical set (keys that map to themselves)
			canonical_fields = [k for k, v in mapping.items() if k == v]
			canonical_fields = sorted(set(canonical_fields))
			
			# Reverse index: canonical -> [aliases]
			aliases_by_canonical = {}
			for alias, canonical in mapping.items():
				if alias == canonical:
					aliases_by_canonical.setdefault(canonical, [])
				else:
					aliases_by_canonical.setdefault(canonical, []).append(alias)
			
			# Build sections
			required_keys_section = "\n".join([f"- {key}" for key in canonical_fields])
			
			# Limit alias list lengths per key to keep prompt concise
			alias_lines = []
			for key in canonical_fields:
				aliases = sorted(set(aliases_by_canonical.get(key, [])))
				if aliases:
					# Trim very long alias lists
					alias_preview = aliases[:12]
					more = "" if len(aliases) <= 12 else f", +{len(aliases) - 12} more"
					alias_lines.append(f"- {key}: [" + ", ".join(alias_preview) + "]" + more)
			
			alias_guidance_section = "\n".join(alias_lines) if alias_lines else ""
			
			# Build prompt text
			prompt = f"""Extract {ptype} insurance policy information as FLAT JSON with these canonical keys only:\n\nRequired JSON keys (exact, flat):\n{required_keys_section}\n\nAlias guidance (examples of how these fields may appear in the document):\n{alias_guidance_section}\n\nExtraction rules:\n- Dates: DD/MM/YYYY only (e.g., \"From 12-JUL-2022 15:01(Hrs)\" → \"12/07/2022\")\n- Currency/Amounts: digits only; remove ₹, Rs., commas, /-\n- Numbers: digits only; remove descriptors (e.g., \"5 seater\" → \"5\")\n- Text: clean core value, remove prefixes/suffixes and labels\n- Missing fields: null\n- Return exactly one flat JSON object with ONLY the canonical keys listed above (every key present, null when unknown). No markdown, no comments, no extra keys.\n\nDocument:\n{(extracted_text or '')[:truncation_limit]}\n"""
			return prompt
		except Exception as e:
			frappe.log_error(f"Error building prompt from mapping for {policy_type}: {str(e)}", "Mapping Prompt Build Error")
			return self._build_fallback_prompt(policy_type, extracted_text)

