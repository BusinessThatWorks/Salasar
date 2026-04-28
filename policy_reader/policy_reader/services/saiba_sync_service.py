# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import re
from datetime import datetime, timedelta

import frappe
import requests
from frappe.utils import cint, cstr, flt, getdate, now


class SaibaSyncService:
	"""Service for syncing policies to SAIBA ERP system"""

	MOTOR_ENDPOINT = "/api/MotorPolicyEntryS"
	HEALTH_ENDPOINT = "/api/HealthPolicyEntryS"
	CUSTOMER_ENDPOINT = "/api/InsertCustomerDetails"
	TOKEN_ENDPOINT = "/GetToken"

	# Token validity duration (23 hours to be safe)
	TOKEN_VALIDITY_HOURS = 23

	def __init__(self):
		self.settings = None
		self._load_settings()

	def _load_settings(self):
		"""Load Policy Reader Settings"""
		self.settings = frappe.get_single("Policy Reader Settings")

	def _is_enabled(self):
		"""Check if SAIBA integration is enabled"""
		return self.settings and self.settings.saiba_enabled

	def _get_base_url(self):
		"""Get SAIBA API base URL"""
		return (self.settings.saiba_base_url or "").rstrip("/")

	def _is_token_valid(self):
		"""Check if the cached token is still valid"""
		if not self.settings.saiba_token or not self.settings.saiba_token_expiry:
			return False

		try:
			expiry = self.settings.saiba_token_expiry
			if isinstance(expiry, str):
				expiry = datetime.fromisoformat(expiry.replace("Z", "+00:00"))

			# Check if token expires within next 5 minutes
			buffer_time = datetime.now() + timedelta(minutes=5)
			return expiry > buffer_time
		except Exception as e:
			frappe.log_error(f"Error checking token validity: {str(e)}", "SAIBA Token Check Error")
			return False

	def _refresh_token(self):
		"""Refresh the authentication token from SAIBA API"""
		if not self._is_enabled():
			frappe.throw("SAIBA integration is not enabled")

		base_url = self._get_base_url()
		if not base_url:
			frappe.throw("SAIBA base URL is not configured")

		username = self.settings.saiba_username
		password = self.settings.get_password("saiba_password")

		if not username or not password:
			frappe.throw("SAIBA credentials are not configured")

		try:
			url = f"{base_url}{self.TOKEN_ENDPOINT}"
			payload = {"userName": username, "password": password}
			response = requests.post(
				url, json=payload, headers={"Content-Type": "application/json"}, timeout=30
			)
			if response.status_code == 200:
				data = response.json()
				token = data.get("token") or data.get("access_token") or data.get("Token")

				if token:
					self._cache_token(token)
					return token
				else:
					frappe.throw(f"No token in response: {data}")
			else:
				frappe.throw(f"Token request failed with status {response.status_code}: {response.text}")

		except requests.exceptions.Timeout:
			frappe.throw("SAIBA API request timed out")
		except requests.exceptions.ConnectionError:
			frappe.throw("Could not connect to SAIBA API")
		except Exception as e:
			frappe.log_error(f"Token refresh error: {str(e)}", "SAIBA Token Refresh Error")
			frappe.throw(f"Failed to refresh token: {str(e)}")

	def _cache_token(self, token):
		"""Cache the token in settings"""
		expiry = datetime.now() + timedelta(hours=self.TOKEN_VALIDITY_HOURS)

		# Update settings directly in DB to avoid validation
		frappe.db.set_value(
			"Policy Reader Settings",
			"Policy Reader Settings",
			{"saiba_token": token, "saiba_token_expiry": expiry},
			update_modified=False,
		)
		frappe.db.commit()

		# Refresh settings instance
		self._load_settings()

	def _get_auth_token(self):
		"""Get valid authentication token, refreshing if needed"""
		if self._is_token_valid():
			return self.settings.saiba_token

		return self._refresh_token()

	def _format_date_for_saiba(self, date_value):
		"""Format date to DD-MM-YYYY for SAIBA API"""
		if not date_value:
			return ""

		try:
			if isinstance(date_value, str):
				date_value = getdate(date_value)
			return date_value.strftime("%d-%m-%Y")
		except Exception:
			return ""

	def _safe_int(self, value, default=0):
		"""Safely convert value to int"""
		try:
			if value is None or value == "":
				return default
			return cint(value)
		except Exception:
			return default

	def _safe_float(self, value, default=0):
		"""Safely convert value to float"""
		try:
			if value is None or value == "":
				return default
			return flt(value)
		except Exception:
			return default

	def _safe_str(self, value, default=""):
		"""Safely convert value to string"""
		if value is None:
			return default
		return cstr(value)

	def _get_required_saiba_fields(self, policy_type):
		"""Get set of required SAIBA field names from validation rules"""
		try:
			validation_settings = frappe.get_single("SAIBA Validation Settings")
			if policy_type.lower() == "motor":
				rules = validation_settings.motor_validation_rules or []
			else:
				rules = validation_settings.health_validation_rules or []
			return {r.saiba_field for r in rules if r.is_required}
		except Exception:
			return set()

	# def _validate_bank_master(self, policy_doc):
	# 	bank_name = self._safe_str(policy_doc.bank_name)
	# 	bank_name_exists = frappe.db.exists("SB Bank Master", bank_name)
	# 	if not bank_name_exists:
	# 		bank_name = "NONE"
	# 		frappe.db.set_value(
	# 			policy_doc.doctype, policy_doc.name, "bank_name", "NONE", update_modified=False
	# 		)
	# 	return bank_name

	def _filter_required_only(self, payload, policy_type):
		"""Filter payload to only required fields if setting is enabled"""
		if not self.settings.saiba_sync_required_only:
			return payload

		required_fields = self._get_required_saiba_fields(policy_type)
		if not required_fields:
			return payload  # Fallback: send everything if no rules found

		return {k: v for k, v in payload.items() if k in required_fields}

	def _extract_error_fields(self, validations):
		if not validations:
			return []

		FIELD_MAP = {
			# "policyno":      "policy_no",
			"rtocode": "rto_code",
			"make": "make",
			"model": "model",
			"variant": "variant",
			"engineno": "engine_no",
			"chasisno": "chasis_no",
			"vehicleno": "vehicle_no",
			"policytype": "policy_type",
			"custcode": "cust_code",
			"suminsured": "sum_insured",
			"insbranchcode": "ins_branch_code",
		}

		detected = []
		for msg in validations:
			first_word = msg.strip().split()[0].lower()
			if first_word in FIELD_MAP:
				detected.append(FIELD_MAP[first_word])
		return detected

	def _build_motor_policy_payload(self, policy_doc):
		"""Build the payload for Motor Policy sync"""
		return {
			"custCode": self._safe_int(policy_doc.customer_code),
			"posPolicy": self._safe_str(policy_doc.pos_misp_ref) or "No",
			"bizType": self._safe_str(policy_doc.biz_type) or "New",
			"insBranchCode": self._safe_int(policy_doc.insurer_branch_code),
			"issuenceDate": self._format_date_for_saiba(policy_doc.policy_issuance_date),
			"busBrokDate": self._format_date_for_saiba(
				policy_doc.bus_brok_date or policy_doc.policy_issuance_date
			),
			"startDate": self._format_date_for_saiba(policy_doc.policy_start_date),
			"expiryDate": self._format_date_for_saiba(policy_doc.policy_expiry_date),
			"policyReceivedDate": self._format_date_for_saiba(policy_doc.receive_date),
			"policyReceivedFormat": self._safe_str(policy_doc.policy_received_format),
			"policyType": self._safe_str(policy_doc.policy_type),
			"department": self._safe_str(policy_doc.department),
			"coverageType": self._safe_str(policy_doc.coverage_type) or "1+1",
			"policyVertical": self._safe_str(policy_doc.customer_vertical),
			"policyNo": self._safe_str(policy_doc.policy_no),
			"isRenewable": "Yes" if policy_doc.is_renewable == "YES" else "No",
			"newRenewal": self._safe_str(policy_doc.new_renewal) or "New",
			"prevPolicy": self._safe_str(policy_doc.prev_policy) or "No",
			"vehicleNo": self._safe_str(policy_doc.vehicle_no),
			"make": self._safe_str(policy_doc.make),
			"model": self._safe_str(policy_doc.model),
			"variant": self._safe_str(policy_doc.variant),
			"registrationDate": self._format_date_for_saiba(
				policy_doc.registration_date or policy_doc.policy_start_date
			),
			"typeofVehicle": self._safe_str(policy_doc.type_of_vehicle) or "Private",
			"yearOfMan": self._safe_int(policy_doc.year_of_man),
			"chasisNo": self._safe_str(policy_doc.chasis_no),
			"engineNo": self._safe_str(policy_doc.engine_no),
			"cc": self._safe_str(policy_doc.cc),
			"seat": self._safe_str(policy_doc.seats),
			"fuel": self._safe_str(policy_doc.fuel),
			"rtocode": self._safe_str(policy_doc.rto_code),
			"ncb": self._safe_int(policy_doc.ncb),
			"odd": self._safe_int(policy_doc.odd),
			"vehicleCategory": self._safe_str(policy_doc.category) or "PCV",
			"passengerGVW": self._safe_str(policy_doc.passenger_gvw),
			"gvw": self._safe_str(policy_doc.gvw_ton_kg),
			"noOfPassenger": self._safe_str(policy_doc.no_of_passenger),
			"sumInsured": self._safe_int(policy_doc.sum_insured),
			"odPremium": self._safe_int(policy_doc.net_od_premium),
			"premRate": self._safe_str(policy_doc.prem_rate),
			"tpPremium": self._safe_int(policy_doc.tp_premium),
			"lpodPremium": self._safe_int(policy_doc.lpod_premium),
			"coverangeOrTP": self._safe_str(policy_doc.coverage_tp),
			"gst": self._safe_int(policy_doc.gst) or 18,
			"stampDuty": self._safe_int(policy_doc.stamp_duty),
			"paymentMode": self._safe_str(policy_doc.payment_mode_1),
			"bankName": self._safe_str(policy_doc.bank_name),
			"paymentTranNo": self._safe_str(policy_doc.payment_tran_no),
			"campaignName": self._safe_str(policy_doc.campaign_name) or "No Campaign",
			"remarks": self._safe_str(policy_doc.policy_enquiry_remarks),
			"policyStatus": self._safe_str(policy_doc.policy_status_na) or "NA",
		}

	def _build_health_policy_payload(self, policy_doc):
		"""Build the payload for Health Policy sync"""
		# bank_name = self._validate_bank_master(policy_doc)
		payload = {
			# "customerCode": self._safe_int(policy_doc.customer_code),
			"CustCode": self._safe_int(policy_doc.customer_code),
			"posPolicy": self._safe_str(policy_doc.pos_policy) or "No",
			# "policyBizType": self._safe_str(policy_doc.biz_type) or "New",
			"bizType":self._safe_str(policy_doc.biz_type) or "New",
			"insurerBranchCode": self._safe_int(policy_doc.insurer_branch_code),
			# "policyIssuanceDate": self._format_date_for_saiba(policy_doc.policy_issuance_date),
			"issuenceDate": self._format_date_for_saiba(policy_doc.policy_issuance_date),
			# "policyStartDate": self._format_date_for_saiba(policy_doc.policy_start_date),
			"startDate": self._format_date_for_saiba(policy_doc.policy_start_date),
			# "policyExpiryDate": self._format_date_for_saiba(policy_doc.policy_expiry_date),
			"expiryDate": self._format_date_for_saiba(policy_doc.policy_expiry_date),
			"policyType": self._safe_str(policy_doc.policy_type),
			"policyNo": self._safe_str(policy_doc.policy_no),
			"planName": self._safe_str(policy_doc.plan_name),
			"isRenewable": "Yes" if policy_doc.is_renewable == "Yes" else "No",
			# "isRenewal":"New",
			# "newRenewal": "Yes" if policy_doc.is_renewable == "Yes" else "No",
			# "coverageType": self._safe_str(policy_doc.coverage_type),
			# "policyVertical": self._safe_str(policy_doc.policy_vertical),
			"prevPolicy": self._safe_str(policy_doc.prev_policy),
			"sumInsured": self._safe_int(policy_doc.sum_insured),
			"netodPremium": self._safe_int(policy_doc.net_od_premium),
			"gst": self._safe_int(policy_doc.gst_tax_percent) or 18,
			"stampDuty": self._safe_int(policy_doc.stamp_duty),
			"paymentMode": self._safe_str(policy_doc.payment_mode),
			"bankName": self._safe_str(policy_doc.bank_name),
			# "paymentTransactionNo": self._safe_str(policy_doc.payment_transaction_no),
			"paymentTranNo": self._safe_str(policy_doc.payment_transaction_no),
			"Chq/DD/Trn No": self._safe_str(policy_doc.payment_transaction_no),
			"remarks": self._safe_str(policy_doc.policy_enquiry_remarks),
			"policyStatus": self._safe_str(policy_doc.policy_status),
		}

		# Add insured persons (1-5 for SAIBA API)
		for i in range(1, 6):
			name_field = f"insured_{i}_name"
			gender_field = f"insured_{i}_gender"
			dob_field = f"insured_{i}_dob"
			relation_field = f"insured_{i}_relation"

			payload[f"insured{i}Name"] = self._safe_str(getattr(policy_doc, name_field, ""))
			payload[f"insured{i}Gender"] = self._safe_str(getattr(policy_doc, gender_field, ""))
			payload[f"insured{i}DOB"] = self._format_date_for_saiba(getattr(policy_doc, dob_field, None))
			payload[f"insured{i}Relation"] = self._safe_str(getattr(policy_doc, relation_field, ""))
		return payload

	def _build_customer_payload(self, customer_doc):
		return {
			"title": self._safe_str(customer_doc.title),
			"name": self._safe_str(customer_doc.customer_name),
			"groupName": self._safe_str(customer_doc.customer_group) if customer_doc.customer_group else "NO GROUP",
			"shortName": self._safe_str(customer_doc.short_name),
			"gender": self._safe_str(customer_doc.gender),
			"dob": self._format_date_for_saiba(customer_doc.dob_doi),
			"address": self._safe_str(customer_doc.address),
			"state": self._safe_str(customer_doc.state),
			"city": self._safe_str(customer_doc.city),
			"custCountry": self._safe_str(customer_doc.country),
			"location": self._safe_str(customer_doc.location),
			"pinCode": self._safe_str(customer_doc.pin),
			"phoneNo": self._safe_str(customer_doc.phone_no),
			"mobileNo": self._safe_str(customer_doc.mobile_no),
			"email": self._safe_str(customer_doc.email),
			"panNo": self._safe_str(customer_doc.customer_pan),
			"aadhaarNo": self._safe_str(customer_doc.customer_aadhaar_no),
			"gstin": self._safe_str(customer_doc.customer_gst),
			"vertical": self._safe_str(customer_doc.vertical),
			"industrySegment": self._safe_str(customer_doc.industry_segment),
			"formOfOrg": self._safe_str(customer_doc.form_of_organization),
			"category": self._safe_str(customer_doc.customer_category),
			"branchCode": self._safe_int(customer_doc.branch_code),
			"rmCode": self._safe_int(customer_doc.rm_code),
			"cscCode": self._safe_int(customer_doc.csc_code),
			"posRefMispCode": self._safe_int(customer_doc.posrefmisp_code),
		}

	def _make_api_request(self, endpoint, payload):
		"""Make API request to SAIBA"""
		base_url = self._get_base_url()
		url = f"{base_url}{endpoint}"
		token = self._get_auth_token()

		headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

		try:
			response = requests.post(url, json=payload, headers=headers, timeout=60)
			# Handle 401/403 - try refreshing token once
			if response.status_code in [401, 403]:
				# Clear token and retry
				frappe.db.set_value(
					"Policy Reader Settings",
					"Policy Reader Settings",
					{"saiba_token": None, "saiba_token_expiry": None},
					update_modified=False,
				)
				frappe.db.commit()
				self._load_settings()

				# Get new token and retry
				token = self._refresh_token()
				headers["Authorization"] = f"Bearer {token}"

				response = requests.post(url, json=payload, headers=headers, timeout=60)

			return response

		except requests.exceptions.Timeout:
			raise Exception("SAIBA API request timed out")
		except requests.exceptions.ConnectionError:
			raise Exception("Could not connect to SAIBA API")

	def _parse_control_number(self, result_text):
		"""Extract control number from 'Successfully Saved with Control No : 398254'"""
		if not result_text:
			return None

		match = re.search(r"Control No\s*:\s*(\d+)", result_text, re.IGNORECASE)
		return match.group(1) if match else None

	# def _parse_customer_code(self,result_text):
	# 	"""Extract customer code from 'Successfully Saved with customer Code :1'"""
	# 	if not result_text:
	# 		return None
	# 	match=re.search(r"customer Code\s*:\s*(\d+)", result_text, re.IGNORECASE)
	# 	return match.group(1) if match else None

	def _handle_api_response(self, response, policy_doc, request_payload=None):
		"""Handle API response and update sync status"""
		try:
			data = response.json()
		except Exception:
			data = {"error": response.text, "status_code": response.status_code}

		if response.status_code == 200 and data.get("status")== "Success":
			customer_code = None
			control_no = None
			if policy_doc.doctype == "Insurance Customer":
				# customer_code=self._parse_customer_code(data.get("result", ""))
				customer_code = data.get("custCode")
				if customer_code:
					try:
						if policy_doc.name != str(customer_code):
							frappe.rename_doc("Insurance Customer", policy_doc.name, str(customer_code), force=True)
							policy_doc = frappe.get_doc("Insurance Customer", str(customer_code))
					except Exception as e:
						frappe.log_error(f"Rename failed: {str(e)}", "SAIBA Customer Rename Error")

			else:
				control_no = self._parse_control_number(data.get("result", ""))
			self._update_sync_status(
				policy_doc,
				status="Synced",
				control_number=control_no,
				customer_code=customer_code,
				response=data,
				request_payload=request_payload,
			)
			return {
				"success": True,
				"control_number": control_no,
				"customer_code": customer_code,
				"message": data.get("result"),
			}

		else:
			error_msg = (
				data.get("error")
				or data.get("validations")
				or data.get("message")
				or f"HTTP {response.status_code}"
			)
			# Normalize to string
			if isinstance(error_msg, list):
				error_text = " ".join(error_msg)
			else:
				error_text = str(error_msg)

			# Google-Sheet-style regex usage
			match = re.search(
				r"policy\s*no.*already\s*exists\s*in\s*saiba.*control\s*no\s*:\s*(\d+)",
				error_text,
				re.IGNORECASE,
			)

			if match:
				control_no = match.group(1)

				self._update_sync_status(
					policy_doc,
					status="Duplicate Entry",
					control_number=control_no,
					error=error_text,
					response=data,
					request_payload=request_payload,
				)

				return {
					"success": False,
					"control_number": control_no,
					"error": error_text,
					"validations": data.get("validations", []),
					"error_fields": self._extract_error_fields(data.get("validations", [])),
				}
			self._update_sync_status(
				policy_doc,
				status="Failed",
				error=str(error_msg),
				response=data,
				request_payload=request_payload,
			)
			# return {"success": False, "error": str(error_msg)}
			validations = data.get("validations", [])
			return {
				"success": False,
				"error": str(error_msg),
				"validations": validations,
				"error_fields": self._extract_error_fields(validations),
			}

	def _update_sync_status(
		self,
		policy_doc,
		status,
		error=None,
		control_number=None,
		response=None,
		request_payload=None,
		customer_code=None,
	):
		"""Update the sync status fields on the policy document"""
		doctype = policy_doc.doctype
		docname = policy_doc.name

		update_data = {"saiba_sync_status": status, "saiba_sync_datetime": now()}

		if error:
			update_data["saiba_sync_error"] = error
		else:
			update_data["saiba_sync_error"] = None

		if control_number:
			update_data["saiba_control_number"] = control_number
		if customer_code:
			update_data["saiba_customer_code"] = customer_code

		# Store both request and response for debugging
		if response or request_payload:
			sync_data = {}
			if request_payload:
				sync_data["request"] = request_payload
			if response:
				sync_data["response"] = response
			update_data["saiba_sync_response"] = frappe.as_json(sync_data)

		frappe.db.set_value(doctype, docname, update_data, update_modified=False)
		frappe.db.commit()

	def sync_motor_policy(self, policy_name):
		"""Sync a Motor Policy to SAIBA"""
		if not self._is_enabled():
			return {"success": False, "error": "SAIBA integration is not enabled"}

		payload = None
		try:
			policy_doc = frappe.get_doc("Motor Policy", policy_name)
			# Build payload
			payload = self._build_motor_policy_payload(policy_doc)
			payload = self._filter_required_only(payload, "Motor")
			# Make API request
			response = self._make_api_request(self.MOTOR_ENDPOINT, payload)
			# Handle response (pass payload for debugging)
			return self._handle_api_response(response, policy_doc, request_payload=payload)

		except Exception as e:
			frappe.log_error(f"Motor Policy sync error: {str(e)}", "SAIBA Sync Error")

			# Try to update status if we have the doc
			try:
				policy_doc = frappe.get_doc("Motor Policy", policy_name)
				self._update_sync_status(policy_doc, status="Failed", error=str(e), request_payload=payload)
			except Exception:
				pass

			return {"success": False, "error": str(e)}

	def sync_health_policy(self, policy_name):
		"""Sync a Health Policy to SAIBA"""
		if not self._is_enabled():
			return {"success": False, "error": "SAIBA integration is not enabled"}

		payload = None
		try:
			policy_doc = frappe.get_doc("Health Policy", policy_name)

			# Mark as pending
			self._update_sync_status(policy_doc, status="Pending")

			# Build payload
			payload = self._build_health_policy_payload(policy_doc)
			payload = self._filter_required_only(payload, "Health")

			# Make API request
			response = self._make_api_request(self.HEALTH_ENDPOINT, payload)

			# Handle response (pass payload for debugging)
			return self._handle_api_response(response, policy_doc, request_payload=payload)

		except Exception as e:
			frappe.log_error(f"Health Policy sync error: {str(e)}", "SAIBA Sync Error")

			# Try to update status if we have the doc
			try:
				policy_doc = frappe.get_doc("Health Policy", policy_name)
				self._update_sync_status(policy_doc, status="Failed", error=str(e), request_payload=payload)
			except Exception:
				pass

			return {"success": False, "error": str(e)}

	def sync_customer_details(self, doc):
		if not self._is_enabled():
			return {"success": False, "error": "SAIBA integration is not enabled"}

		payload = None
		try:
			policy_doc = frappe.get_doc("Insurance Customer", doc)
			self._update_sync_status(policy_doc, status="Pending")
			# need to update the status
			payload = self._build_customer_payload(policy_doc)
			response = self._make_api_request(self.CUSTOMER_ENDPOINT, payload)
			return self._handle_api_response(response, policy_doc, request_payload=payload)
		except Exception as e:
			frappe.log_error(f"Customer Insertion error :{str(e)}", "SAIBA sync error")
			try:
				policy_doc = frappe.get_doc("Insurance Customer", policy_doc)
				self._update_sync_status(policy_doc, status="Failed", error=str(e), request_payload=payload)
			except Exception:
				pass

			return {"success": False, "error": str(e)}

	@staticmethod
	def test_connection():
		"""Test SAIBA API connectivity"""
		service = SaibaSyncService()

		if not service._is_enabled():
			return {"success": False, "error": "SAIBA integration is not enabled"}

		try:
			# Try to get a token
			token = service._get_auth_token()

			if token:
				return {"success": True, "message": "Successfully connected to SAIBA API"}
			else:
				return {"success": False, "error": "Failed to obtain authentication token"}

		except Exception as e:
			return {"success": False, "error": str(e)}


# Whitelisted API methods
@frappe.whitelist()
def sync_motor_policy(policy_name):
	"""Whitelisted method to sync a Motor Policy to SAIBA"""
	service = SaibaSyncService()
	return service.sync_motor_policy(policy_name)


@frappe.whitelist()
def sync_health_policy(policy_name):
	"""Whitelisted method to sync a Health Policy to SAIBA"""
	service = SaibaSyncService()
	return service.sync_health_policy(policy_name)


@frappe.whitelist()
def test_saiba_connection():
	"""Whitelisted method to test SAIBA API connectivity"""
	return SaibaSyncService.test_connection()


@frappe.whitelist()
def sync_customer_details(customer_name):
	"""Whitelisted method to sync an Insurance Customer to SAIBA"""
	service = SaibaSyncService()
	return service.sync_customer_details(customer_name)
