#!/usr/bin/env python3
"""
Basic test script to verify RanomEngine setup and imports.
Run this to make sure everything is configured correctly.
"""

import sys
import traceback

def test_imports():
    """Test that all modules can be imported"""
    print("🧪 Testing RanomEngine imports...")
    
    try:
        print("  ✓ Importing config...")
        from config import config
        
        print("  ✓ Importing models...")
        from models import VehicleData, ParseResult, SearchTrace
        
        print("  ✓ Importing VIN search...")
        from services.vin_search import VINSearchService, VINValidator
        
        print("  ✓ Importing DOM fetcher...")
        from services.dom_fetcher import DOMFetcherService
        
        print("  ✓ Importing parsers...")
        from parsers.cars_com_parser import CarsComParser
        from parsers.generic_parser import GenericParser
        
        print("  ✓ Importing AI extractor...")
        from ai.goal_extractor import AIGoalExtractor
        
        print("  ✓ Importing goal builder...")
        from services.goal_builder import GoalBuilderService
        
        print("✅ All imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_configuration():
    """Test configuration loading"""
    print("\n🔧 Testing configuration...")
    
    try:
        from config import config
        
        print(f"  ✓ DDGS Max Results: {config.DDGS_MAX_RESULTS}")
        print(f"  ✓ AI Model: {config.AI_MODEL}")
        print(f"  ✓ WebDriver Headless: {config.WEBDRIVER_HEADLESS}")
        print(f"  ✓ Backend URL: {config.BACKEND_URL}")
        print(f"  ✓ Supported Domains: {len(config.SUPPORTED_DOMAINS)} domains")
        
        # Test configuration validation
        config.validate()
        print("✅ Configuration validation passed!")
        return True
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False


def test_vin_validation():
    """Test VIN validation"""
    print("\n🔍 Testing VIN validation...")
    
    try:
        from services.vin_search import VINValidator
        
        # Test valid VINs
        valid_vins = [
            "5TDGZRBHXMS103005",
            "1HGCM82633A123456",
            "WBAFR7C59BC123456"
        ]
        
        for vin in valid_vins:
            if VINValidator.is_valid_vin(vin):
                print(f"  ✓ Valid VIN: {vin}")
            else:
                print(f"  ❌ Expected valid VIN failed: {vin}")
                return False
        
        # Test invalid VINs
        invalid_vins = [
            "123456789",  # Too short
            "123456789012345678",  # Too long
            "5TDGZRBHXMS10I005",  # Contains I
            "5TDGZRBHXMS10O005",  # Contains O
        ]
        
        for vin in invalid_vins:
            if not VINValidator.is_valid_vin(vin):
                print(f"  ✓ Invalid VIN correctly rejected: {vin}")
            else:
                print(f"  ❌ Expected invalid VIN passed: {vin}")
                return False
        
        print("✅ VIN validation tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ VIN validation error: {e}")
        return False


def test_data_models():
    """Test data model creation"""
    print("\n📊 Testing data models...")
    
    try:
        from models import VehicleData
        
        # Test creating a VehicleData object
        sample_data = {
            "vin": "5TDGZRBHXMS103005",
            "make": "Toyota", 
            "model": "Highlander XLE",
            "year": 2021,
            "price": 31650,
            "mileage": 56630,
            "dealer_name": "Test Dealer"
        }
        
        vehicle = VehicleData(**sample_data)
        print(f"  ✓ Created VehicleData: {vehicle.year} {vehicle.make} {vehicle.model}")
        
        # Test goal JSON generation
        goal_json = vehicle.to_goal_json()
        print(f"  ✓ Generated goal: {goal_json['goal']}")
        
        print("✅ Data model tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Data model error: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all basic tests"""
    print("🚀 RanomEngine Basic Test Suite")
    print("=" * 50)
    
    all_passed = True
    
    # Run tests
    tests = [
        test_imports,
        test_configuration,
        test_vin_validation,
        test_data_models
    ]
    
    for test in tests:
        if not test():
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All basic tests passed! RanomEngine is ready to use.")
        print("\nNext steps:")
        print("1. Set up AI model (Ollama or OpenAI)")
        print("2. Install Chrome/Chromium for Selenium")
        print("3. Try: python cli.py config-info")
        print("4. Try: python cli.py validate-vin 5TDGZRBHXMS103005")
    else:
        print("❌ Some tests failed. Check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main() 