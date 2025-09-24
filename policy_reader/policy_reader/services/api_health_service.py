# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import time
from policy_reader.policy_reader.services.common_service import CommonService


class APIHealthService:
    """Service for checking API health and connectivity"""
    
    @staticmethod
    def test_claude_api_health():
        """
        Test Claude API connectivity using Anthropic Python SDK
        """
        try:
            # Get API key using common service
            settings = CommonService.get_policy_reader_settings()
            api_key = CommonService.get_api_key(settings)
            
            # Import Anthropic SDK
            try:
                from anthropic import Anthropic
            except ImportError:
                return {
                    "success": False,
                    "error": "Anthropic Python SDK not installed. Please install with: pip install anthropic"
                }
            
            # Initialize Anthropic client
            client = Anthropic(api_key=api_key)
            
            # Simple health check with minimal token usage
            start_time = time.time()
            
            try:
                response = client.messages.create(
                    model=getattr(settings, 'claude_model', 'claude-3-5-sonnet-20241022'),
                    max_tokens=10,
                    messages=[
                        {"role": "user", "content": "Hi"}
                    ],
                    timeout=10.0
                )
                
                response_time = int((time.time() - start_time) * 1000)  # Convert to ms
                
                # Extract token usage
                tokens_used = 0
                if hasattr(response, 'usage') and response.usage:
                    tokens_used = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)
                
                return {
                    "success": True,
                    "response_time": response_time,
                    "message": "API is healthy and responsive",
                    "tokens_used": tokens_used,
                    "model": getattr(settings, 'claude_model', 'claude-3-5-sonnet-20241022')
                }
                
            except Exception as api_error:
                return APIHealthService._handle_api_error(api_error)
                
        except Exception as e:
            CommonService.log_processing_error("testing Claude API health", e)
            return {
                "success": False,
                "error": f"Health check failed: {str(e)}"
            }
    
    @staticmethod
    def _handle_api_error(error):
        """Handle specific API errors and return appropriate messages"""
        error_str = str(error).lower()
        
        # Rate limit or insufficient credits
        if "rate limit" in error_str or "insufficient" in error_str or "quota" in error_str:
            return {
                "success": False,
                "error": "Rate limit exceeded or insufficient credits. Please check your Anthropic account balance."
            }
        
        # Authentication errors
        if "unauthorized" in error_str or "invalid" in error_str or "authentication" in error_str:
            return {
                "success": False,
                "error": "Authentication failed. Please check your API key."
            }
        
        # Timeout errors
        if "timeout" in error_str:
            return {
                "success": False,
                "error": "Request timeout. The API took too long to respond."
            }
        
        # Connection errors
        if "connection" in error_str or "network" in error_str:
            return {
                "success": False,
                "error": "Connection failed. Cannot reach Claude API."
            }
        
        # Model errors
        if "model" in error_str:
            return {
                "success": False,
                "error": f"Model error: {str(error)}"
            }
        
        # Generic error
        return {
            "success": False,
            "error": f"API error: {str(error)}"
        }
    
    @staticmethod
    def get_api_status():
        """
        Get basic API status without making a request
        """
        try:
            settings = CommonService.get_policy_reader_settings()
            api_key = CommonService.get_api_key(settings)
            
            if not api_key:
                return {
                    "configured": False,
                    "message": "API key not configured"
                }
            
            # Check if API key looks valid
            if api_key.startswith('sk-ant-'):
                key_preview = api_key[:10] + "..." + api_key[-4:]
                return {
                    "configured": True,
                    "message": f"Configured ({key_preview})"
                }
            else:
                return {
                    "configured": False,
                    "message": "Invalid format - API key should start with 'sk-ant-'"
                }
                
        except Exception as e:
            return {
                "configured": False,
                "message": f"Error checking API key: {str(e)}"
            }
