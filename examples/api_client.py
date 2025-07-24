#!/usr/bin/env python3
"""
RanomEngine API Client Example

Example Python client showing how to interact with the RanomEngine REST API.
Demonstrates all major endpoints and error handling.
"""

import requests
import json
import time
from typing import Dict, Any, Optional


class RanomEngineClient:
    """Python client for RanomEngine API"""
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timeout"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Connection error - is the API server running?"}
        except requests.exceptions.HTTPError as e:
            try:
                error_data = response.json()
                return {"success": False, "error": error_data.get("detail", str(e))}
            except:
                return {"success": False, "error": f"HTTP {response.status_code}: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health status"""
        return self._make_request("GET", "/health")
    
    def get_config(self) -> Dict[str, Any]:
        """Get API configuration"""
        return self._make_request("GET", "/config")
    
    def validate_vin(self, vin: str) -> Dict[str, Any]:
        """Validate VIN format"""
        return self._make_request("POST", "/validate/vin", json={"vin": vin})
    
    def search_vin(self, vin: str, limit: int = 5, prioritize_supported: bool = True) -> Dict[str, Any]:
        """Search for VIN listings"""
        return self._make_request("POST", "/search/vin", json={
            "vin": vin,
            "limit": limit,
            "prioritize_supported": prioritize_supported
        })
    
    def fetch_page(self, url: str, wait_for_element: Optional[str] = None, save_html: bool = False) -> Dict[str, Any]:
        """Fetch webpage content"""
        return self._make_request("POST", "/fetch/page", json={
            "url": url,
            "wait_for_element": wait_for_element,
            "save_html": save_html
        })
    
    def parse_page(self, url: str, parser: str = "auto") -> Dict[str, Any]:
        """Parse vehicle listing page"""
        return self._make_request("POST", "/parse/page", json={
            "url": url,
            "parser": parser
        })
    
    def extract_ai(self, html_content: str, url: str, existing_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract vehicle data using AI"""
        return self._make_request("POST", "/extract/ai", json={
            "html_content": html_content,
            "url": url,
            "existing_data": existing_data
        })
    
    def process_complete(self, input_value: str, input_type: Optional[str] = None, create_case: bool = True) -> Dict[str, Any]:
        """Process VIN or URL through complete pipeline"""
        return self._make_request("POST", "/process/complete", json={
            "input_value": input_value,
            "input_type": input_type,
            "create_case": create_case
        })
    
    def process_vin(self, vin: str, create_case: bool = True) -> Dict[str, Any]:
        """Convenience method to process VIN"""
        return self._make_request("POST", f"/process/vin?vin={vin}&create_case={create_case}")
    
    def process_url(self, url: str, create_case: bool = True) -> Dict[str, Any]:
        """Convenience method to process URL"""
        return self._make_request("POST", f"/process/url?url={url}&create_case={create_case}")


def print_result(title: str, result: Dict[str, Any]):
    """Pretty print API result"""
    print(f"\n{'='*60}")
    print(f"📊 {title}")
    print('='*60)
    
    if result.get("success"):
        print("✅ Success!")
        if "processing_time" in result:
            print(f"⏱️  Processing time: {result['processing_time']:.2f}s")
        
        if result.get("data"):
            print("\n📋 Data:")
            print(json.dumps(result["data"], indent=2, default=str))
    else:
        print("❌ Failed!")
        if result.get("error"):
            print(f"🚫 Error: {result['error']}")


def main():
    """Demonstrate RanomEngine API usage"""
    print("🚀 RanomEngine API Client Demo")
    
    # Initialize client
    client = RanomEngineClient()
    
    # 1. Health check
    print_result("Health Check", client.health_check())
    
    # 2. Get configuration
    print_result("Configuration", client.get_config())
    
    # 3. Validate VIN
    test_vin = "5TDGZRBHXMS103005"
    print_result(f"VIN Validation: {test_vin}", client.validate_vin(test_vin))
    
    # 4. Search for VIN (this will make real web requests)
    print(f"\n⚠️  The following operations will make real web requests...")
    user_input = input("Continue with VIN search? (y/N): ").lower()
    
    if user_input == 'y':
        print_result(f"VIN Search: {test_vin}", client.search_vin(test_vin, limit=3))
        
        # 5. Process VIN (complete pipeline - no case creation)
        print_result(f"Process VIN: {test_vin}", client.process_vin(test_vin, create_case=False))
    
    print(f"\n{'='*60}")
    print("✨ Demo completed!")
    print("💡 Check the API documentation at: http://localhost:8000/docs")
    print("📖 Full documentation: docs/API.md")


if __name__ == "__main__":
    main() 