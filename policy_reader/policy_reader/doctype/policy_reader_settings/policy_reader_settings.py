# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import json
import os
import time
from frappe.model.document import Document
from frappe.utils import now
from frappe.utils import cstr
from policy_reader.policy_reader.services.common_service import CommonService
from policy_reader.policy_reader.services.prompt_service import PromptService


class PolicyReaderSettings(Document):
	def validate(self):
		"""Validate Policy Reader Settings"""
		self.validate_api_key()
		self.validate_numeric_fields()
	
	def validate_api_key(self):
		"""Validate Anthropic API key format"""
		if self.anthropic_api_key:
			if not self.anthropic_api_key.startswith('sk-ant-'):
				frappe.throw("Invalid input: Anthropic API key format. Key should start with 'sk-ant-'")
	
	def validate_numeric_fields(self):
		"""Validate numeric field ranges"""
		if self.timeout:
			if not (60 <= self.timeout <= 600):
				frappe.throw("Invalid input: timeout must be between 60 and 600 seconds")
	
	@frappe.whitelist()
	def test_api_connection(self):
		"""Test API key connectivity (optional feature)"""
		if not self.anthropic_api_key:
			frappe.throw("Invalid input: please enter an API key to test")
		
		try:
			# This is a basic test - in a real implementation you might want to make a test API call
			frappe.msgprint("API key format appears valid. Test connection functionality can be implemented as needed.", 
							title="API Key Test", indicator="green")
			return {"success": True, "message": "API key format valid"}
		except Exception as e:
			frappe.log_error(f"API connection test failed: {str(e)}", frappe.get_traceback())
			frappe.throw("Unexpected error occurred while testing API connection. Please contact support.")
	
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
			frappe.log_error(f"Unexpected error while refreshing field mappings: {str(e)}", frappe.get_traceback())
			frappe.logger().error(f"Field mapping refresh failed: {str(e)}")
			frappe.throw("Unexpected error occurred while refreshing field mappings. Please contact support.")

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
				
				# Insured Person 1
				"insured_1_relation": ["INSURED1RELATION", "Insured1Relation", "Insured 1 Relation", "insured_1_relation", "insured1relation"],
				"insured_1_emp_code": ["INSURED1EMPCODE", "Insured1EmpCode", "INSURED1FAMILYCODE", "Insured1FamilyCode", "insured_1_emp_code", "insured1empcode"],
				"insured_1_name": ["INSURED1NAME", "Insured1Name", "Insured 1 Name", "insured_1_name", "insured1name"],
				"insured_1_gender": ["INSURED1GENDER", "Insured1Gender", "Insured 1 Gender", "insured_1_gender", "insured1gender"],
				"insured_1_dob": ["INSURED1DOB", "Insured1DOB", "Insured 1 DOB", "insured_1_dob", "insured1dob"],
				"insured_1_sum_insured": ["INSURED1SUMINSURED", "Insured1SumInsured", "Insured 1 Sum Insured", "insured_1_sum_insured", "insured1suminsured"],

				# Insured Person 2
				"insured_2_relation": ["INSURED2RELATION", "Insured2Relation", "Insured 2 Relation", "insured_2_relation", "insured2relation"],
				"insured_2_emp_code": ["INSURED2EMPCODE", "Insured2EmpCode", "INSURED2FAMILYCODE", "Insured2FamilyCode", "insured_2_emp_code", "insured2empcode"],
				"insured_2_name": ["INSURED2NAME", "Insured2Name", "Insured 2 Name", "insured_2_name", "insured2name"],
				"insured_2_gender": ["INSURED2GENDER", "Insured2Gender", "Insured 2 Gender", "insured_2_gender", "insured2gender"],
				"insured_2_dob": ["INSURED2DOB", "Insured2DOB", "Insured 2 DOB", "insured_2_dob", "insured2dob"],
				"insured_2_sum_insured": ["INSURED2SUMINSURED", "Insured2SumInsured", "Insured 2 Sum Insured", "insured_2_sum_insured", "insured2suminsured"],

				# Insured Person 3
				"insured_3_relation": ["INSURED3RELATION", "Insured3Relation", "Insured 3 Relation", "insured_3_relation", "insured3relation"],
				"insured_3_emp_code": ["INSURED3EMPCODE", "Insured3EmpCode", "INSURED3FAMILYCODE", "Insured3FamilyCode", "insured_3_emp_code", "insured3empcode"],
				"insured_3_name": ["INSURED3NAME", "Insured3Name", "Insured 3 Name", "insured_3_name", "insured3name"],
				"insured_3_gender": ["INSURED3GENDER", "Insured3Gender", "Insured 3 Gender", "insured_3_gender", "insured3gender"],
				"insured_3_dob": ["INSURED3DOB", "Insured3DOB", "Insured 3 DOB", "insured_3_dob", "insured3dob"],
				"insured_3_sum_insured": ["INSURED3SUMINSURED", "Insured3SumInsured", "Insured 3 Sum Insured", "insured_3_sum_insured", "insured3suminsured"],

				# Insured Person 4
				"insured_4_relation": ["INSURED4RELATION", "Insured4Relation", "Insured 4 Relation", "insured_4_relation", "insured4relation"],
				"insured_4_emp_code": ["INSURED4EMPCODE", "Insured4EmpCode", "INSURED4FAMILYCODE", "Insured4FamilyCode", "insured_4_emp_code", "insured4empcode"],
				"insured_4_name": ["INSURED4NAME", "Insured4Name", "Insured 4 Name", "insured_4_name", "insured4name"],
				"insured_4_gender": ["INSURED4GENDER", "Insured4Gender", "Insured 4 Gender", "insured_4_gender", "insured4gender"],
				"insured_4_dob": ["INSURED4DOB", "Insured4DOB", "Insured 4 DOB", "insured_4_dob", "insured4dob"],
				"insured_4_sum_insured": ["INSURED4SUMINSURED", "Insured4SumInsured", "Insured 4 Sum Insured", "insured_4_sum_insured", "insured4suminsured"],

				# Insured Person 5
				"insured_5_relation": ["INSURED5RELATION", "Insured5Relation", "Insured 5 Relation", "insured_5_relation", "insured5relation"],
				"insured_5_emp_code": ["INSURED5EMPCODE", "Insured5EmpCode", "INSURED5FAMILYCODE", "Insured5FamilyCode", "insured_5_emp_code", "insured5empcode"],
				"insured_5_name": ["INSURED5NAME", "Insured5Name", "Insured 5 Name", "insured_5_name", "insured5name"],
				"insured_5_gender": ["INSURED5GENDER", "Insured5Gender", "Insured 5 Gender", "insured_5_gender", "insured5gender"],
				"insured_5_dob": ["INSURED5DOB", "Insured5DOB", "Insured 5 DOB", "insured_5_dob", "insured5dob"],
				"insured_5_sum_insured": ["INSURED5SUMINSURED", "Insured5SumInsured", "Insured 5 Sum Insured", "insured_5_sum_insured", "insured5suminsured"],

				# Insured Person 6
				"insured_6_relation": ["INSURED6RELATION", "Insured6Relation", "Insured 6 Relation", "insured_6_relation", "insured6relation"],
				"insured_6_emp_code": ["INSURED6EMPCODE", "Insured6EmpCode", "INSURED6FAMILYCODE", "Insured6FamilyCode", "insured_6_emp_code", "insured6empcode"],
				"insured_6_name": ["INSURED6NAME", "Insured6Name", "Insured 6 Name", "insured_6_name", "insured6name"],
				"insured_6_gender": ["INSURED6GENDER", "Insured6Gender", "Insured 6 Gender", "insured_6_gender", "insured6gender"],
				"insured_6_dob": ["INSURED6DOB", "Insured6DOB", "Insured 6 DOB", "insured_6_dob", "insured6dob"],
				"insured_6_sum_insured": ["INSURED6SUMINSURED", "Insured6SumInsured", "Insured 6 Sum Insured", "insured_6_sum_insured", "insured6suminsured"],

				# Insured Person 7
				"insured_7_relation": ["INSURED7RELATION", "Insured7Relation", "Insured 7 Relation", "insured_7_relation", "insured7relation"],
				"insured_7_emp_code": ["INSURED7EMPCODE", "Insured7EmpCode", "INSURED7FAMILYCODE", "Insured7FamilyCode", "insured_7_emp_code", "insured7empcode"],
				"insured_7_name": ["INSURED7NAME", "Insured7Name", "Insured 7 Name", "insured_7_name", "insured7name"],
				"insured_7_gender": ["INSURED7GENDER", "Insured7Gender", "Insured 7 Gender", "insured_7_gender", "insured7gender"],
				"insured_7_dob": ["INSURED7DOB", "Insured7DOB", "Insured 7 DOB", "insured_7_dob", "insured7dob"],
				"insured_7_sum_insured": ["INSURED7SUMINSURED", "Insured7SumInsured", "Insured 7 Sum Insured", "insured_7_sum_insured", "insured7suminsured"],

				# Insured Person 8
				"insured_8_relation": ["INSURED8RELATION", "Insured8Relation", "Insured 8 Relation", "insured_8_relation", "insured8relation"],
				"insured_8_emp_code": ["INSURED8EMPCODE", "Insured8EmpCode", "INSURED8FAMILYCODE", "Insured8FamilyCode", "insured_8_emp_code", "insured8empcode"],
				"insured_8_name": ["INSURED8NAME", "Insured8Name", "Insured 8 Name", "insured_8_name", "insured8name"],
				"insured_8_gender": ["INSURED8GENDER", "Insured8Gender", "Insured 8 Gender", "insured_8_gender", "insured8gender"],
				"insured_8_dob": ["INSURED8DOB", "Insured8DOB", "Insured 8 DOB", "insured_8_dob", "insured8dob"],
				"insured_8_sum_insured": ["INSURED8SUMINSURED", "Insured8SumInsured", "Insured 8 Sum Insured", "insured_8_sum_insured", "insured8suminsured"],
				
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
		"""Get cached field mapping for policy type with Frappe caching"""
		cache_key = f"field_mapping_{policy_type.lower()}"
		
		# Try to get from Frappe cache first
		cached_mapping = frappe.cache().get_value(cache_key)
		if cached_mapping:
			frappe.logger().info(f"Field mapping cache hit for {policy_type}")
			return cached_mapping
		
		try:
			frappe.logger().info(f"Getting cached field mapping for {policy_type}")
			mapping = {}
			
			if policy_type.lower() == "motor":
				frappe.logger().info(f"Motor policy fields exist: {bool(self.motor_policy_fields)}")
				if self.motor_policy_fields:
					mapping = frappe.parse_json(self.motor_policy_fields)
					frappe.logger().info(f"Motor mapping loaded: {len(mapping)} entries")
			elif policy_type.lower() == "health":
				frappe.logger().info(f"Health policy fields exist: {bool(self.health_policy_fields)}")
				if self.health_policy_fields:
					mapping = frappe.parse_json(self.health_policy_fields)
					frappe.logger().info(f"Health mapping loaded: {len(mapping)} entries")
			
			# Cache for 1 hour
			frappe.cache().set_value(cache_key, mapping, expires_in_sec=3600)
			frappe.logger().info(f"Field mapping cached for {policy_type}")
			return mapping
			
		except Exception as e:
			frappe.log_error(f"Unexpected error while getting cached field mapping for {policy_type}: {str(e)}", frappe.get_traceback())
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
		return PromptService.build_prompt_from_mapping(policy_type, extracted_text, self)

