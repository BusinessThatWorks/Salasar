# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import time
from datetime import datetime, timedelta


def monitor_stuck_policy_documents():
    """Monitor and retry stuck Policy Documents every 3 minutes"""
    try:
        # Find documents stuck in Processing status for more than 5 minutes
        five_minutes_ago = datetime.now() - timedelta(minutes=5)
        
        stuck_documents = frappe.get_all(
            "Policy Document",
            filters={
                "status": "Processing",
                "modified": ["<", five_minutes_ago]
            },
            fields=["name", "title", "modified", "owner"]
        )
        
        if stuck_documents:
            frappe.logger().info(f"Found {len(stuck_documents)} stuck Policy Documents, attempting retry")
            
            for doc_info in stuck_documents:
                try:
                    # Get the full document
                    doc = frappe.get_doc("Policy Document", doc_info.name)
                    
                    # Check if required fields are still present
                    if not doc.policy_file or not doc.policy_type:
                        frappe.logger().warning(f"Skipping retry for {doc.name}: missing policy_file or policy_type")
                        continue
                    
                    # Reset status and retry processing
                    doc.status = "Draft"
                    doc.error_message = ""
                    doc.save()
                    frappe.db.commit()
                    
                    # Re-enqueue the job with a new timestamp
                    timestamp = int(time.time())
                    frappe.enqueue(
                        method="policy_reader.policy_reader.doctype.policy_document.policy_document.process_policy_background",
                        queue='short',
                        timeout=180,
                        is_async=True,
                        job_name=f"policy_ocr_retry_{doc.name}_{timestamp}",
                        doc_name=doc.name
                    )
                    
                    frappe.logger().info(f"Retrying stuck Policy Document: {doc.name}")
                    
                    # Notify the document owner
                    frappe.publish_realtime(
                        event="policy_processing_retry",
                        message={
                            "doc_name": doc.name,
                            "message": "Processing was stuck and has been automatically retried",
                            "retry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        },
                        user=doc.owner
                    )
                    
                except Exception as e:
                    frappe.log_error(
                        f"Failed to retry stuck Policy Document {doc_info.name}: {str(e)}", 
                        "Policy Document Retry Error"
                    )
                    continue
        
        # Also check for very old stuck documents (>30 minutes) and mark them as failed
        thirty_minutes_ago = datetime.now() - timedelta(minutes=30)
        
        very_old_stuck = frappe.get_all(
            "Policy Document",
            filters={
                "status": "Processing",
                "modified": ["<", thirty_minutes_ago]  
            },
            fields=["name", "title", "owner"]
        )
        
        for doc_info in very_old_stuck:
            try:
                doc = frappe.get_doc("Policy Document", doc_info.name)
                doc.status = "Failed"
                doc.error_message = "Processing timed out after 30 minutes. Please try processing again."
                doc.save()
                frappe.db.commit()
                
                # Notify user
                frappe.publish_realtime(
                    event="policy_processing_failed",
                    message={
                        "doc_name": doc.name,
                        "message": "Processing timed out and was marked as failed",
                        "status": "Failed"
                    },
                    user=doc.owner
                )
                
                frappe.logger().warning(f"Marked very old stuck Policy Document as failed: {doc.name}")
                
            except Exception as e:
                frappe.log_error(
                    f"Failed to mark old stuck Policy Document as failed {doc_info.name}: {str(e)}", 
                    "Policy Document Timeout Error"
                )
        
    except Exception as e:
        frappe.log_error(
            f"Error in monitor_stuck_policy_documents: {str(e)}", 
            "Policy Document Monitor Error"
        )


def check_runpod_health():
    """Check RunPod API health every 10 minutes"""
    try:
        # Get Policy Reader Settings
        settings = frappe.get_single("Policy Reader Settings")
        if not settings:
            return
        
        # Only check if RunPod is configured
        if not (settings.runpod_pod_id and settings.runpod_port and settings.runpod_api_secret):
            frappe.logger().info("RunPod not configured, skipping health check")
            return
        
        # Perform health check
        health_result = settings._check_runpod_health()
        
        # Update health status
        settings.update_runpod_health_status(health_result)
        
        # Log health status
        if health_result.get("status") == "healthy":
            frappe.logger().info(f"RunPod API health check passed: {health_result.get('response_time', 0):.2f}s")
        else:
            frappe.logger().warning(f"RunPod API health check failed: {health_result.get('error', 'Unknown error')}")
        
    except Exception as e:
        frappe.log_error(
            f"Error in check_runpod_health: {str(e)}", 
            "RunPod Health Check Error"
        )


def cleanup_old_processing_jobs():
    """Cleanup function to remove very old jobs - can be called manually if needed"""
    try:
        # Find documents in Processing status older than 1 hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        
        old_processing = frappe.get_all(
            "Policy Document",
            filters={
                "status": "Processing",
                "modified": ["<", one_hour_ago]
            },
            fields=["name", "title", "owner"]
        )
        
        for doc_info in old_processing:
            doc = frappe.get_doc("Policy Document", doc_info.name)
            doc.status = "Failed"
            doc.error_message = "Processing job was abandoned due to system issues. Please try again."
            doc.save()
            frappe.db.commit()
            
            frappe.logger().info(f"Cleaned up abandoned processing job: {doc.name}")
            
    except Exception as e:
        frappe.log_error(
            f"Error in cleanup_old_processing_jobs: {str(e)}", 
            "Policy Document Cleanup Error"
        )