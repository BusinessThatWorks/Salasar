#!/usr/bin/env python3
"""
Simple test script for RunPod API integration
Run this from the policy_reader directory to test the RunPod connection
"""

import frappe
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_runpod_integration():
    """Test RunPod API integration"""
    try:
        print("🧪 Testing RunPod API Integration...")
        
        # Get Policy Reader Settings
        settings = frappe.get_single("Policy Reader Settings")
        print(f"✅ Settings loaded: {settings.name}")
        
        # Check RunPod configuration
        if not settings.runpod_pod_id:
            print("❌ RunPod Pod ID not configured")
            return False
            
        if not settings.runpod_port:
            print("❌ RunPod Port not configured")
            return False
            
        if not settings.runpod_api_secret:
            print("❌ RunPod API Secret not configured")
            return False
        
        print(f"✅ RunPod configured: {settings.runpod_pod_id}:{settings.runpod_port}")
        
        # Test health check
        print("🔍 Testing RunPod health check...")
        health_result = settings._check_runpod_health()
        
        print(f"Health Status: {health_result.get('status')}")
        print(f"Response Time: {health_result.get('response_time', 0):.2f}s")
        
        if health_result.get('status') == 'healthy':
            print("✅ RunPod API is healthy!")
            
            # Test URL construction
            base_url = settings.get_runpod_base_url()
            health_url = settings.get_runpod_health_url()
            extract_url = settings.get_runpod_extract_url()
            
            print(f"Base URL: {base_url}")
            print(f"Health URL: {health_url}")
            print(f"Extract URL: {extract_url}")
            
            return True
        else:
            print(f"❌ RunPod API health check failed: {health_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        return False

if __name__ == "__main__":
    # Initialize Frappe
    try:
        frappe.init(site="localhost")
        frappe.connect()
        
        success = test_runpod_integration()
        
        if success:
            print("\n🎉 RunPod integration test passed!")
        else:
            print("\n💥 RunPod integration test failed!")
            
    except Exception as e:
        print(f"❌ Failed to initialize Frappe: {str(e)}")
        print("Make sure you're running this from a Frappe bench environment")
    finally:
        if frappe.db:
            frappe.db.close()
