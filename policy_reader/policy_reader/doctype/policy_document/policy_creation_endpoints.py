# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
from policy_reader.policy_reader.services.policy_creation_service import PolicyCreationService


@frappe.whitelist()
def create_policy_entry(policy_document_name):
    """
    Create a policy record (Motor/Health) from the extracted fields
    """
    try:
        # Get the policy document
        policy_doc = frappe.get_doc("Policy Document", policy_document_name)
        
        # Ensure document is saved first
        if not policy_doc.name:
            frappe.throw("Invalid input: Document must be saved before creating policy")
        
        # Validate prerequisites
        policy_creation_service = PolicyCreationService()
        validation = policy_creation_service.validate_policy_creation_prerequisites(str(policy_doc.name))
        
        if not validation["valid"]:
            frappe.msgprint(validation["error"], alert=True)
            return {"success": False, "error": validation["error"]}
        
        # Create policy record using the policy type that was used during extraction
        extraction_policy_type = policy_doc.extraction_policy_type or policy_doc.policy_type
        result = policy_creation_service.create_policy_record(str(policy_doc.name), extraction_policy_type)
        
        if result["success"]:
            frappe.msgprint(
                f"✅ {result['message']}\n"
                f"📊 Mapped {result['mapped_fields']} fields\n"
                f"🔗 Policy: {result['policy_name']}",
                alert=True
            )
            
            # Refresh the form to show the new policy link
            frappe.publish_realtime('policy_created', {
                'policy_document': policy_doc.name,
                'policy_name': result['policy_name'],
                'policy_type': result['policy_type']
            })
        else:
            frappe.msgprint(f"❌ {result['error']}", alert=True)
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Policy creation failed: {str(e)}")
        frappe.msgprint(f"❌ Policy creation failed: {str(e)}", alert=True)
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_policy_creation_status(policy_document_name):
    """
    Get the status of policy creation for this document
    """
    try:
        # Get the policy document
        policy_doc = frappe.get_doc("Policy Document", policy_document_name)
        
        policy_creation_service = PolicyCreationService()
        validation = policy_creation_service.validate_policy_creation_prerequisites(str(policy_doc.name))
        
        extraction_policy_type = policy_doc.extraction_policy_type or policy_doc.policy_type
        return {
            "can_create": validation["valid"],
            "error": validation.get("error"),
            "policy_type": extraction_policy_type,
            "has_extracted_fields": bool(policy_doc.extracted_fields),
            "existing_policy": policy_doc.motor_policy or policy_doc.health_policy
        }
        
    except Exception as e:
        return {
            "can_create": False,
            "error": str(e)
        }
