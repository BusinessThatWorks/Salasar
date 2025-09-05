# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import requests
import time


class RunPodService:
    """Service class for handling RunPod API operations"""
    
    def __init__(self, settings=None):
        """Initialize with policy reader settings"""
        self.settings = settings or frappe.get_single("Policy Reader Settings")
    
    def is_configured(self):
        """Check if RunPod is properly configured"""
        return bool(
            self.settings.runpod_pod_id and 
            self.settings.runpod_port and 
            self.settings.runpod_api_secret
        )
    
    def is_healthy(self):
        """Check if RunPod is healthy and responsive"""
        return (
            self.is_configured() and 
            self.settings.runpod_health_status == "healthy" and
            self.settings.runpod_response_time < 5
        )
    
    def get_base_url(self):
        """Get RunPod base URL"""
        if not self.is_configured():
            return None
        
        return f"https://{self.settings.runpod_pod_id}-{self.settings.runpod_port}.proxy.runpod.net"
    
    def get_health_url(self):
        """Get RunPod health check URL"""
        base_url = self.get_base_url()
        if not base_url:
            return None
        
        return f"{base_url}/health"
    
    def get_extract_url(self):
        """Get RunPod document extraction URL"""
        base_url = self.get_base_url()
        if not base_url:
            return None
        
        endpoint = self.settings.runpod_endpoint or "/extract"
        return f"{base_url}{endpoint}"
    
    def get_ocr_url(self):
        """Get RunPod OCR-only URL"""
        return self.settings.get_runpod_ocr_url()
    
    def check_health(self):
        """Perform health check on RunPod API"""
        try:
            if not self.is_configured():
                return {
                    "status": "unconfigured",
                    "error": "RunPod not configured",
                    "response_time": 0
                }
            
            health_url = self.get_health_url()
            headers = {'Authorization': f'Bearer {self.settings.runpod_api_secret}'}
            
            start_time = time.time()
            response = requests.get(health_url, headers=headers, timeout=10)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "response_time": response_time,
                    "message": "RunPod API is responding normally"
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "response_time": response_time
                }
                
        except requests.exceptions.Timeout:
            return {
                "status": "error",
                "error": "Health check timed out",
                "response_time": 10
            }
        except requests.exceptions.ConnectionError:
            return {
                "status": "error",
                "error": "Cannot connect to RunPod API",
                "response_time": 0
            }
        except Exception as e:
            frappe.log_error(f"RunPod health check error: {str(e)}", "RunPod Health Check Error")
            return {
                "status": "error",
                "error": f"Health check failed: {str(e)}",
                "response_time": 0
            }
    
    def extract_document_text(self, file_path, policy_type, timeout=None):
        """Extract OCR text from document using RunPod API (OCR only, no field extraction)"""
        try:
            if not self.is_healthy():
                return {"success": False, "error": "RunPod API is not available"}
            
            ocr_url = self.get_ocr_url()
            
            # Prepare file for upload
            with open(file_path, 'rb') as file:
                files = {'file': file}
                headers = {'Authorization': f'Bearer {self.settings.runpod_api_secret}'}
                
                # OCR endpoint doesn't need prompt - just extract raw text
                data = {}
                
                # Make request to RunPod OCR API
                start_time = time.time()
                response = requests.post(
                    ocr_url, 
                    files=files, 
                    data=data, 
                    headers=headers, 
                    timeout=timeout or self.settings.timeout or 180
                )
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        extracted_text = result.get('text', '')
                        
                        if extracted_text:
                            # Return in compatible format with local processing
                            return {
                                "success": True,
                                "text": extracted_text,
                                "confidence_data": {
                                    "average_confidence": 0.85,  # RunPod typically high confidence
                                    "enhancement_applied": False,
                                    "processing_method": "runpod_ocr",
                                    "response_time": response_time
                                }
                            }
                        else:
                            return {"success": False, "error": "No text extracted from RunPod OCR API"}
                            
                    except ValueError:
                        # Response is not JSON
                        return {"success": False, "error": f"Invalid JSON response from RunPod OCR API: {response.text}"}
                else:
                    return {"success": False, "error": f"RunPod OCR API error: HTTP {response.status_code} - {response.text}"}
                    
        except requests.exceptions.Timeout:
            return {"success": False, "error": "RunPod OCR API request timed out"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Cannot connect to RunPod OCR API"}
        except Exception as e:
            frappe.log_error(f"RunPod OCR extraction error: {str(e)}", "RunPod OCR Error")
            return {"success": False, "error": f"RunPod OCR API error: {str(e)}"}
    
    def update_health_status(self, health_result):
        """Update the health status in settings"""
        try:
            self.settings.runpod_health_status = health_result.get("status", "error")
            self.settings.runpod_response_time = health_result.get("response_time", 0)
            self.settings.runpod_last_health_check = frappe.utils.now()
            self.settings.save()
            
        except Exception as e:
            frappe.log_error(f"Failed to update RunPod health status: {str(e)}", "RunPod Status Update Error")