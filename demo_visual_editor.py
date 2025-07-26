#!/usr/bin/env python3
"""
RanomMappingStudio Visual Editor Demo

Demonstrates the complete Visual DOM-to-Goal Mapping Editor including:
- Interactive HTML interface with three-panel layout
- Real-time DOM element selection and mapping
- AI-powered selector suggestions
- Live preview and comparison with AI results
- Schema save/export functionality
"""

import webbrowser
import time
import subprocess
import sys
from pathlib import Path

def print_section(title: str, char: str = "="):
    """Print a formatted section header"""
    print(f"\n{char * 60}")
    print(f"🎨 {title}")
    print(f"{char * 60}")

def check_system_requirements():
    """Check if system requirements are met"""
    print_section("System Requirements Check")
    
    # Check Python environment
    try:
        import fastapi
        import uvicorn
        print("✅ FastAPI and Uvicorn installed")
    except ImportError:
        print("❌ FastAPI/Uvicorn missing - run: pip install -r requirements.txt")
        return False
    
    # Check if virtual environment is active
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ Virtual environment is active")
    else:
        print("⚠️  Virtual environment not detected - consider activating: source venv/bin/activate")
    
    # Check for required files
    required_files = [
        "api.py",
        "mappingstudio/api/endpoints.py", 
        "mappingstudio/ui/editor.html",
        "mappingstudio/services/ai_suggester.py"
    ]
    
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path} exists")
        else:
            print(f"❌ {file_path} missing")
            return False
    
    return True

def start_api_server():
    """Start the API server in the background"""
    print_section("Starting API Server")
    
    try:
        # Start uvicorn server
        print("🚀 Starting RanomEngine API server with Visual Editor...")
        print("   Server will be available at: http://localhost:8000")
        print("   Visual Editor at: http://localhost:8000/mappingstudio/editor")
        print("   API Documentation: http://localhost:8000/docs")
        print()
        print("   Press Ctrl+C to stop the server when done")
        print()
        
        # Run the server (this will block)
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "api:app", 
            "--host", "0.0.0.0", 
            "--port", "8000",
            "--reload"
        ])
        
    except KeyboardInterrupt:
        print("\n⛔ Server stopped by user")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return False
    
    return True

def show_usage_instructions():
    """Show detailed usage instructions"""
    print_section("Visual Editor Usage Guide", "🎯")
    
    print("""
🎨 RanomMappingStudio Visual Editor - Complete Guide:

📋 GETTING STARTED:
   1. The server will start automatically
   2. Your browser will open to the Visual Editor
   3. Enter a car listing URL (e.g., Cars.com URL)
   4. Click "Load Page" to preview the website

🖱️  MAPPING WORKFLOW:
   1. LEFT PANEL - Field Mapper:
      • Shows all goal.json fields (VIN, price, year, etc.)
      • Each field has description and type information
      • Input box for CSS selector or XPath

   2. CENTER PANEL - Website Preview:
      • Live iframe showing the target website
      • Click elements to capture selectors (when in picking mode)
      • Real-time visual feedback

   3. RIGHT PANEL - Output Preview:
      • Live goal.json preview
      • Statistics (fields mapped, confidence score)
      • AI comparison results

🎯 MAPPING METHODS:
   
   Method 1: Manual Selection
   • Click "Pick from page" next to any field
   • Click on the corresponding element in the webpage
   • Selector is automatically generated and applied
   
   Method 2: AI Suggestions
   • Click "AI Suggest" for intelligent recommendations
   • AI analyzes the page and suggests optimal selectors
   • Click "Get AI Suggestions" for all fields at once
   
   Method 3: Manual Entry
   • Type CSS selectors or XPath directly into input boxes
   • Supports complex selectors and nested elements

🧪 TESTING & VALIDATION:
   • "Test Mapping" - Preview extracted goal.json
   • "Compare with AI" - Side-by-side accuracy comparison
   • Real-time field validation and error reporting
   • Confidence scores and success indicators

💾 SAVING & EXPORT:
   • "Save Schema" - Store mapping for reuse
   • Version control and metadata tracking
   • Export for use in production systems

⚡ PRO TIPS:
   • Start with AI suggestions, then refine manually
   • Use specific selectors for better accuracy
   • Test your mapping before saving
   • Compare with AI to find missing fields
   • Save schemas for reuse across similar sites
    """)

def show_demo_scenarios():
    """Show example demo scenarios"""
    print_section("Demo Scenarios", "💡")
    
    print("""
🚗 DEMO SCENARIOS TO TRY:

1. CARS.COM LISTING:
   URL: https://www.cars.com/vehicledetail/detail/12345/
   • Perfect for testing all features
   • Rich structured data
   • Good for AI comparison

2. CARFAX LISTING:
   URL: https://www.carfax.com/vehicle/12345
   • Different DOM structure
   • Test mapping flexibility
   • Vehicle history data

3. AUTOTRADER LISTING:
   URL: https://www.autotrader.com/cars-for-sale/12345
   • Complex page layout
   • Multiple data sources
   • Advanced mapping challenge

4. CUSTOM DEALER WEBSITE:
   • Use any local dealer website
   • Test generic mapping capabilities
   • Create custom schemas

🎯 WORKFLOW DEMO:
   1. Load Cars.com URL
   2. Click "Get AI Suggestions" → See automatic mapping
   3. Test mapping → View goal.json preview
   4. Compare with AI → See accuracy metrics
   5. Refine selectors manually
   6. Save as custom schema
   7. Test with different URLs
    """)

def open_browser():
    """Open the visual editor in browser"""
    print("🌐 Opening Visual Editor in your default browser...")
    
    try:
        # Wait a moment for server to start
        print("   Waiting for server to initialize...")
        time.sleep(3)
        
        # Open the visual editor
        editor_url = "http://localhost:8000/mappingstudio/editor"
        webbrowser.open(editor_url)
        
        print(f"✅ Browser opened to: {editor_url}")
        
        # Also show other useful URLs
        print(f"   📚 API Docs: http://localhost:8000/docs")
        print(f"   🔍 Health Check: http://localhost:8000/health")
        
    except Exception as e:
        print(f"❌ Failed to open browser: {e}")
        print(f"   Please manually navigate to: http://localhost:8000/mappingstudio/editor")

def main():
    """Run the visual editor demo"""
    print("🎨 RanomMappingStudio - Visual DOM-to-Goal Mapping Editor")
    print("=" * 80)
    
    print("""
🚀 REVOLUTIONARY VISUAL MAPPING TOOL:
  • 🖱️  Click-to-map DOM elements to goal.json fields
  • 🧠 AI-powered selector suggestions with confidence scores
  • 👁️  Real-time preview and live goal.json generation
  • ⚔️  AI vs mapping comparison with similarity metrics
  • 💾 Schema save/export with version control
  • 🎯 Professional UI accessible to non-programmers
    """)
    
    # Check requirements
    if not check_system_requirements():
        print("\n❌ System requirements not met. Please fix the issues above.")
        return
    
    print("\n✅ All requirements met! Ready to start.")
    
    # Show usage guide
    show_usage_instructions()
    show_demo_scenarios()
    
    print_section("Starting Demo", "🚀")
    
    # Confirm start
    try:
        input("\nPress Enter to start the Visual Editor server (or Ctrl+C to cancel)...")
    except KeyboardInterrupt:
        print("\n⛔ Demo cancelled by user")
        return
    
    # Open browser in background
    import threading
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    # Start server (this will block until Ctrl+C)
    start_api_server()
    
    print_section("Demo Complete", "✨")
    print("""
🎉 Thank you for trying RanomMappingStudio Visual Editor!

Key achievements:
• ✅ Interactive visual mapping interface
• ✅ Real-time DOM element selection  
• ✅ AI-powered intelligent suggestions
• ✅ Live preview and comparison tools
• ✅ Professional production-ready UI
• ✅ Complete API integration

Next steps:
• Use saved schemas in production
• Integrate with your car listing workflow  
• Build custom extensions and integrations
• Share mappings with your team

For support and updates:
• Documentation: README.md and docs/API.md
• API Reference: http://localhost:8000/docs
• Source code: mappingstudio/ directory
    """)

if __name__ == "__main__":
    main() 