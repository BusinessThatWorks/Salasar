# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
from policy_reader.policy_reader.services.common_service import CommonService


class PromptService:
    """Service for building extraction prompts"""
    
    @staticmethod
    def get_vision_extraction_prompt(policy_type, settings):
        """
        Get extraction prompt optimized for Claude Vision API
        """
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

RESPOND WITH VALID FLAT JSON ONLY - NO EXPLANATIONS, NO MARKDOWN, NO CODE BLOCKS."""
                
                return prompt
            else:
                # Fallback prompt if no mapping available
                return f"Extract key information from this {policy_type.lower()} insurance policy as JSON."
                
        except Exception as e:
            frappe.log_error(f"Error building vision prompt: {str(e)}", frappe.get_traceback())
            return f"Extract key information from this {policy_type.lower()} insurance policy as JSON."
    
    @staticmethod
    def build_prompt_from_mapping(policy_type, extracted_text, settings):
        """Build a full extraction prompt from the active alias→canonical mapping"""
        try:
            truncation_limit = 200000
            ptype = (policy_type or "").lower()
            
            # Get mapping from cache; if empty, build defaults
            mapping = settings.get_cached_field_mapping(ptype) or settings.build_default_field_mapping(ptype)
            if not isinstance(mapping, dict) or not mapping:
                return PromptService._build_fallback_prompt(ptype, extracted_text)
            
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
                    # Show up to 5 aliases per key
                    shown_aliases = aliases[:5]
                    alias_text = ", ".join(shown_aliases)
                    if len(aliases) > 5:
                        alias_text += f" (and {len(aliases) - 5} more)"
                    alias_lines.append(f"- {key}: {alias_text}")
            
            aliases_section = "\n".join(alias_lines) if alias_lines else "No aliases defined"
            
            # Truncate text if too long
            text_to_use = extracted_text
            if len(extracted_text) > truncation_limit:
                text_to_use = extracted_text[:truncation_limit] + "\n... [truncated]"
            
            prompt = f"""Extract the following fields from the {ptype} insurance policy text as a flat JSON object.

REQUIRED FIELDS TO EXTRACT:
{required_keys_section}

FIELD ALIASES (look for these variations):
{aliases_section}

EXTRACTION RULES:
1. Return ONLY valid flat JSON (no nested objects)
2. Use exact field names as keys (from required fields list)
3. Dates: DD/MM/YYYY format only
4. Currency/Amounts: Extract numeric value only, remove currency symbols and commas
5. Text: Extract exact text as it appears
6. Numbers: Extract as strings unless specified otherwise
7. If a field is not found, use null
8. No explanations, no markdown, no code blocks

POLICY TEXT:
{text_to_use}

RESPOND WITH VALID FLAT JSON ONLY - NO EXPLANATIONS, NO MARKDOWN, NO CODE BLOCKS."""
            
            return prompt
            
        except Exception as e:
            frappe.log_error(f"Error building prompt from mapping: {str(e)}", frappe.get_traceback())
            return PromptService._build_fallback_prompt(ptype, extracted_text)
    
    @staticmethod
    def _build_fallback_prompt(policy_type, extracted_text):
        """Build a simple fallback prompt if no specific prompt is available"""
        try:
            truncation_limit = 200000  # Default text truncation limit (200k chars)
        except Exception:
            truncation_limit = 200000
        
        if policy_type.lower() == "motor":
            return f"""Extract motor insurance policy information as FLAT JSON:
PolicyNumber, VehicleNumber, ChasisNo, EngineNo, Make, Model, PolicyStartDate, PolicyExpiryDate, SumInsured, NetODPremium, TPPremium, GST, NCB

EXTRACTION RULES:
- Dates: DD/MM/YYYY format only
- Currency/Amounts: Extract exact numeric value including decimals, remove currency symbols and commas only
- Text: Extract exact text as it appears
- Numbers: Extract as strings unless specified otherwise
- If a field is not found, use null
- Return ONLY valid JSON, no explanations or markdown

POLICY TEXT:
{extracted_text[:truncation_limit]}

RESPOND WITH VALID FLAT JSON ONLY - NO EXPLANATIONS, NO MARKDOWN, NO CODE BLOCKS."""
        
        elif policy_type.lower() == "health":
            return f"""Extract health insurance policy information as FLAT JSON:
PolicyNumber, InsuredName, PolicyStartDate, PolicyExpiryDate, SumInsured, Premium, GST, NCB

EXTRACTION RULES:
- Dates: DD/MM/YYYY format only
- Currency/Amounts: Extract exact numeric value including decimals, remove currency symbols and commas only
- Text: Extract exact text as it appears
- Numbers: Extract as strings unless specified otherwise
- If a field is not found, use null
- Return ONLY valid JSON, no explanations or markdown

POLICY TEXT:
{extracted_text[:truncation_limit]}

RESPOND WITH VALID FLAT JSON ONLY - NO EXPLANATIONS, NO MARKDOWN, NO CODE BLOCKS."""
        
        else:
            return f"""Extract key information from this {policy_type} insurance policy as JSON.

POLICY TEXT:
{extracted_text[:truncation_limit]}

RESPOND WITH VALID FLAT JSON ONLY - NO EXPLANATIONS, NO MARKDOWN, NO CODE BLOCKS."""
