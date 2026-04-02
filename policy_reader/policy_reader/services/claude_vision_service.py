# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import base64
import os

import frappe
import requests

from policy_reader.policy_reader.services.common_service import CommonService


class ClaudeVisionService:
	"""Service for handling Claude Vision API interactions"""

	@staticmethod
	def process_pdf(file_path, api_key, settings, policy_type):
		"""
		Process PDF directly with Claude API using native PDF support
		"""
		try:
			# Read and encode PDF file directly
			pdf_data = ClaudeVisionService._encode_pdf_file(file_path)

			# Get extraction prompt from settings
			prompt_text = ClaudeVisionService._get_vision_extraction_prompt(settings, policy_type)

			# Prepare Claude API request with direct PDF support
			headers = ClaudeVisionService._prepare_headers(api_key)

			content = ClaudeVisionService._build_content_array(pdf_data, prompt_text)
			payload = ClaudeVisionService._build_payload(settings, content)

			# Make API call
			response = ClaudeVisionService._make_api_call(headers, payload, settings)

			# Process response
			return ClaudeVisionService._process_api_response(response)

		except Exception as e:
			frappe.log_error(f"Claude vision processing error: {str(e)}", frappe.get_traceback())
			return {"success": False, "error": f"Claude vision processing failed: {str(e)}"}

	@staticmethod
	def _encode_pdf_file(file_path):
		"""Encode PDF file to base64"""
		CommonService.validate_file_access(file_path)
		with open(file_path, "rb") as pdf_file:
			return base64.standard_b64encode(pdf_file.read()).decode("utf-8")

	@staticmethod
	def _get_vision_extraction_prompt(settings, policy_type):
		"""Get extraction prompt optimized for Claude Vision API"""
		try:
			# Get field mapping from settings
			policy_reader_settings = CommonService.get_policy_reader_settings()
			mapping = policy_reader_settings.get_cached_field_mapping(policy_type.lower()) or {}

			# Get canonical fields (fields that map to themselves)
			canonical_fields = [k for k, v in mapping.items() if k == v]
			canonical_fields = sorted(set(canonical_fields))
			if canonical_fields:
				fields_list = "\n".join([f"- {field}" for field in canonical_fields])

				prompt = f"""Analyze this {policy_type.lower()} insurance policy PDF and extract the following information as a flat JSON object:

Required fields to extract:
{fields_list}

EXTRACTION RULES:
- Dates: DD/MM/YYYY format only
- Currency/Amounts: Extract exact numeric value including decimals, remove currency symbols and commas only
- Text: Extract exact text as it appears
- Numbers: Extract as strings unless specified otherwise
- If a field is not found, use null
- Return ONLY valid JSON, no explanations or markdown
- Vehicle/Registration No, Chassis No, Engine No: Remove ALL spaces, hyphens, and special characters — return ONLY the raw alphanumeric string. Example: "BR - 26 - M - 4619" → "BR26M4619"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VEHICLE NUMBER — LABEL ALIASES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The field `vehicle_no` may appear under ANY of these labels:
  → "Registration Number"
  → "Registration No."
  → "Reg. No."
  → "Regd. No."
  → "Vehicle No."

CRITICAL: If a short alphanumeric code like "AS11J7259" appears next
to any of these labels — even in a customer details section — that is
vehicle_no. Do NOT map it to customer_code or any other field.
customer_code is a separate insurer-assigned identifier and will have
its own distinct label like "Customer ID" or "Partner Code".
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INSURANCE COMPANY NAME
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The field `insurance_company_name` is the name of the insurer that
issued this policy — NOT the policyholder/customer name.

It may appear under labels such as:
  → "Insurer" / "Insurance Company" / "Underwritten by" / "Issued by"
  → Company name in the document header or letterhead

RULES:
  - Extract the full legal name as printed
    (e.g. "HDFC ERGO General Insurance Company Limited")
  - Do NOT abbreviate or shorten
  - Do NOT confuse with the insured person's name
  - Prefer the most prominent/official occurrence (header or labelled field)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INSURER BRANCH CODE — CONDITIONAL EXTRACTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The field `insurer_branch_code` must ONLY be extracted if the
insurance_company_name is one of these 4 public sector insurers:

  1. NATIONAL INSURANCE CO. LTD.
  2. THE NEW INDIA ASSURANCE CO. LTD.
  3. THE ORIENTAL INSURANCE CO. LTD.
  4. UNITED INDIA INSURANCE CO. LTD.

IF the company IS one of the above 4:
  - Look for a branch/office code in the document
  - It may appear under labels like:
      → "Branch Code"
      → "Office Code"
      → "Issuing Office Code"
      → "DO Code" / "Divisional Office Code"
      → "Branch No" / "Branch ID"
  - Extract the exact alphanumeric code as printed
  - Example: "Branch Code: 050300" → insurer_branch_code = "050300"

IF the company is ANY OTHER insurer (private or otherwise):
  - Set insurer_branch_code = null
  - Do NOT search for or guess any branch code value

DECISION FLOW:
  insurance_company_name == one of the 4 public insurers above?
    YES → extract insurer_branch_code from the document
    NO  → insurer_branch_code = null
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMBINED MODEL/VARIANT COLUMN — GO DIGIT & SIMILAR FORMATS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Some insurers use a single column labeled:
  "Model/Vehicle Variant (Sub-Type)"
  "Model/Variant"
  "Vehicle Model & Variant"

Treat this exactly like a "Make/Model" column but for model+variant:
  - First segment (before /) → model
  - Remaining segments       → apply STEP 3 rules for variant

  Example: Make=MARUTI SUZUKI, "Model/Vehicle Variant"=GYPSY/King MPI BSIV
  → make=Maruti Suzuki, model=GYPSY, variant=King MPI BSIV

  Do NOT put the entire string into variant and leave model as null.
MAKE, MODEL, AND VARIANT — LABEL-DRIVEN EXTRACTION:

You are an expert at reading Indian motor insurance policy documents.
Extract make, model, and variant ONLY based on what the document
explicitly labels or what the model string itself tells you.
Never guess. Never infer from unrelated fields.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — IDENTIFY THE COLUMN/LABEL FIRST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Before reading any value, look at what the column header/label says:

  → "Make/Model" or "Make & Model" or "Make - Model"
      Extract make and model.
      Then apply STEP 2 to check if variant is embedded in the model string.

  → "Make/Model/Variant" or "Make/Model & Variant"
      Extract all three segments directly.

  → Separate columns "Make" | "Model" | "Variant"
      Extract each from its own column only.
      If Variant column is blank / dash / NA / not present → variant = null
      Do NOT extract variant from the model column in this case.

  → "Make" | "Model" columns only (no Variant column exists)
      Extract make and model.
      Then apply STEP 2 to check if variant is embedded in model string.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — SPLITTING MAKE FROM MODEL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Combined columns may use these separators between make and model:
  /  (slash)
  -  (hyphen/dash)
  newline (next line in same cell)

  Segment before separator → make (manufacturer name)
  Segment after separator  → model string (apply STEP 3 next)

  IMPORTANT — Full manufacturer names:
  Some policies write the full registered company name as make:
    "HONDA MOTORCYCLE AND SCOOTER INDIA (P) LTD"
    "TVSMOTORCOMPANY LTD"
    "BAJAJ AUTO LTD"
    "HERO MOTOCORP LTD"
    "ROYAL ENFIELD"
  Treat the entire name before the separator as make.
  Do not split the manufacturer name itself.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 3 — EXTRACTING MODEL AND VARIANT FROM MODEL STRING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
After isolating the model string (everything after the make separator),
apply these rules to split model vs variant:

RULE A — NUMBERS ARE ALWAYS PART OF THE MODEL:
  Numbers (standalone or attached to letters) are NEVER variant.
  They are part of the model name.
    "CD 110"      → model = CD 110     (110 is the model number)
    "SP125"       → model = SP125      (125 is part of model code)
    "PULSAR 150"  → model = PULSAR 150
    "FZ 25"       → model = FZ 25
    "Classic 350" → model = Classic 350
    "INTRA V30"   → model = INTRA V30  (V30 is alphanumeric code)

  NEVER do this:
    "CD 110"  → model = CD, variant = 110   ← WRONG
    "FZ 25"   → model = FZ, variant = 25    ← WRONG
    "V30"     → model = V, variant = 30     ← WRONG

RULE B — VARIANT IS THE FIRST PURELY ALPHABETIC WORD
         AFTER THE LAST NUMERIC/ALPHANUMERIC TOKEN:
  If a purely alphabetic descriptive word appears AFTER
  the model code (after all numbers/alphanumeric codes are done),
  that word is the variant.

    "SP125 DISC"           → model = SP125,      variant = DISC
    "CD 110 DREAM"         → model = CD 110,     variant = DREAM
    "ACTIVA 6G DLX"        → model = ACTIVA 6G,  variant = DLX
    "PULSAR NS200 ABS"     → model = PULSAR NS200, variant = ABS
    "CLASSIC 350 SIGNALS"  → model = CLASSIC 350, variant = SIGNALS
    "FZ S VERSION 2.0"     → model = FZ,         variant = S VERSION 2.0
    "CB SHINE SP"          → model = CB SHINE,   variant = SP

  If NO alphabetic descriptor follows the last numeric token → variant = null
    "CD 110"       → model = CD 110,   variant = null
    "SP125"        → model = SP125,    variant = null
    "INTRA V30"    → model = INTRA V30, variant = null
    "ACTIVA 6G"    → model = ACTIVA 6G, variant = null

RULE C — REPEATED MODEL SEGMENTS ARE NOT VARIANT:
  Some policies write the model twice (alternate spelling or spacing):
    "INTRA V30 / INTRA V 30"  → model = INTRA V30, variant = null
    "i20 / I 20"              → model = i20,        variant = null
  If the segment after the model looks like the same model
  with different spacing/casing → discard it, variant = null

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 4 — THINGS THAT ARE NEVER VARIANT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Even if they appear after the model string, set variant = null for:

  Body Type:   CAGE, TIPPER, TANKER, TRUCK, BUS, VAN,
               CHASSIS, PICK UP, FLAT BED, DUMPER, FULL BODY
  Fuel Type:   PETROL, DIESEL, CNG, EV, ELECTRIC, LPG, HYBRID
  Category:    GCV, PCV, PCO, LCV, HCV, TAXI, PRIVATE, PUBLIC
  Generic:     NEW, USED, OLD, STANDARD, BASIC, REGULAR, N.A

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPLETE EXAMPLES ACROSS ALL FORMATS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  "HONDA - SP125 DISC"
  → make=Honda, model=SP125, variant=DISC

  "HONDA MOTORCYCLE AND SCOOTER INDIA (P) LTD / CD 110 DREAM"
  → make=Honda Motorcycle And Scooter India (P) Ltd, model=CD 110, variant=DREAM

  "Tata Motors / INTRA V30 / INTRA V 30"
  → make=Tata Motors, model=INTRA V30, variant=null (third segment repeats model)

  "Maruti Suzuki / Swift / VXI"
  → make=Maruti Suzuki, model=Swift, variant=VXI (label was Make/Model/Variant)

  "BAJAJ / PULSAR NS200 ABS"
  → make=Bajaj, model=PULSAR NS200, variant=ABS

  "HERO MOTOCORP / SPLENDOR PLUS"
  → make=Hero Motocorp, model=Splendor, variant=Plus

  "ROYAL ENFIELD / CLASSIC 350"
  → make=Royal Enfield, model=Classic 350, variant=null

  "TVS / APACHE RTR 160 4V"
  → make=TVS, model=Apache RTR 160 4V, variant=null (4V is alphanumeric)

  "YAMAHA / MT15 VERSION 2"
  → make=Yamaha, model=MT15, variant=Version 2

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FINAL RULE — WHEN IN DOUBT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  variant = null

  A null variant is always correct.
  A wrong variant is always a data corruption error.

RESPOND WITH VALID FLAT JSON ONLY - NO EXPLANATIONS, NO MARKDOWN, NO CODE BLOCKS."""

				# Add health-specific insured persons extraction instructions
				if policy_type.lower() == "health":
					prompt += """

INSURED PERSONS TABLE EXTRACTION:
This policy may contain a table listing multiple insured members/dependents.
Look for tables with headers like: Name, Relation, DOB, Gender, Sum Insured, Employee Code, Member Code, etc.

For each row in the insured persons table:
- Row 1 (usually Self/Proposer) maps to: insured_1_name, insured_1_relation, insured_1_dob, insured_1_gender, insured_1_sum_insured, insured_1_emp_code
- Row 2 (usually Spouse) maps to: insured_2_name, insured_2_relation, insured_2_dob, insured_2_gender, insured_2_sum_insured, insured_2_emp_code
- Row 3 maps to insured_3_*, Row 4 to insured_4_*, and so on up to Row 8 (insured_8_*)

IMPORTANT:
- Extract each insured person's data into the numbered fields based on their row position
- The "Self" or "Proposer" is typically insured_1_*
- Relations like "Spouse", "Son", "Daughter", "Father", "Mother" indicate family members
- Dates of Birth should be in DD/MM/YYYY format
- Gender: Use "Male", "Female", or "Other"
- Relation: Use "Self", "Spouse", "Wife", "Husband", "Son", "Daughter", "Father", "Mother", or "Other"
"""

				return prompt
			else:
				# Fallback prompt if no mapping available
				return f"Extract key information from this {policy_type.lower()} insurance policy as JSON."

		except Exception as e:
			frappe.log_error(f"Error building vision prompt: {str(e)}", frappe.get_traceback())
			return f"Extract key information from this {policy_type.lower()} insurance policy as JSON."

	@staticmethod
	def _prepare_headers(api_key):
		"""Prepare headers for Claude API request"""
		return {"Content-Type": "application/json", "X-API-Key": api_key, "anthropic-version": "2023-06-01"}

	@staticmethod
	def _build_content_array(pdf_data, prompt_text):
		"""Build content array with PDF document and text prompt"""
		return [
			{
				"type": "document",
				"source": {"type": "base64", "media_type": "application/pdf", "data": pdf_data},
			},
			{"type": "text", "text": prompt_text},
		]

	@staticmethod
	def _build_payload(settings, content):
		"""Build payload for Claude API request"""
		return {
			"model": getattr(settings, "claude_model", "claude-sonnet-4-20250514"),
			"max_tokens": 4000,
			"messages": [{"role": "user", "content": content}],
		}

	@staticmethod
	def _make_api_call(headers, payload, settings):
		"""Make API call to Claude"""
		return requests.post(
			"https://api.anthropic.com/v1/messages",
			headers=headers,
			json=payload,
			timeout=settings.timeout or 180,
		)

	@staticmethod
	def _process_api_response(response):
		"""Process Claude API response"""
		if response.status_code == 200:
			return ClaudeVisionService._handle_successful_response(response)
		elif response.status_code == 429:
			return ClaudeVisionService._handle_rate_limit_response(response)
		elif response.status_code == 401:
			return ClaudeVisionService._handle_auth_error_response()
		else:
			return ClaudeVisionService._handle_error_response(response)

	@staticmethod
	def _handle_successful_response(response):
		"""Handle successful API response"""
		response_data = response.json()

		# Log the full response for debugging
		frappe.logger().info(f"Claude API Response: {response_data}")

		content = response_data.get("content", [{}])[0].get("text", "")

		# Extract JSON from Claude's response
		extracted_fields = CommonService.extract_json_from_text(content)

		# Get token usage from response
		usage = response_data.get("usage", {})
		input_tokens = usage.get("input_tokens", 0)
		output_tokens = usage.get("output_tokens", 0)
		tokens_used = input_tokens + output_tokens

		frappe.logger().info(
			f"Token Usage - Input: {input_tokens}, Output: {output_tokens}, Total: {tokens_used}"
		)

		return {
			"success": True,
			"extracted_fields": extracted_fields,
			"tokens_used": tokens_used,
			"input_tokens": input_tokens,
			"output_tokens": output_tokens,
		}

	@staticmethod
	def _handle_rate_limit_response(response):
		"""Handle rate limit response"""
		error_data = response.json() if response.text else {}
		error_message = error_data.get("error", {}).get("message", response.text)
		return {
			"success": False,
			"error": f"API Rate Limit or Insufficient Balance: {error_message}",
			"error_type": "rate_limit",
		}

	@staticmethod
	def _handle_auth_error_response():
		"""Handle authentication error response"""
		return {
			"success": False,
			"error": "API Authentication Failed - Check your API key",
			"error_type": "auth_error",
		}

	@staticmethod
	def _handle_error_response(response):
		"""Handle general error response"""
		error_data = response.json() if response.text else {}
		error_message = error_data.get("error", {}).get("message", response.text[:200])
		return {
			"success": False,
			"error": f"Claude API error: HTTP {response.status_code} - {error_message}",
			"error_type": "api_error",
		}
