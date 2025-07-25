#!/usr/bin/env python3
"""
RanomEngine CLI

Command-line interface for testing and operating the VIN search and goal extraction system.
Provides various commands for testing individual components and running the complete pipeline.
"""

import json
import sys
import logging
from pathlib import Path
from typing import Optional

import click
import colorama
from colorama import Fore, Style

# Initialize colorama for cross-platform colored output
colorama.init()

# Add the current directory to Python path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from services.vin_search import VINSearchService
from services.dom_fetcher import DOMFetcherService  
from services.goal_builder import GoalBuilderService
from parsers.cars_com_parser import CarsComParser
from parsers.generic_parser import GenericParser
from ai.goal_extractor import AIGoalExtractor
from mappers.goal_mapper import GoalMapper
from models import VehicleData

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress some verbose loggers
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


def print_success(message: str):
    """Print success message in green"""
    click.echo(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")


def print_error(message: str):
    """Print error message in red"""
    click.echo(f"{Fore.RED}✗ {message}{Style.RESET_ALL}")


def print_warning(message: str):
    """Print warning message in yellow"""
    click.echo(f"{Fore.YELLOW}⚠ {message}{Style.RESET_ALL}")


def print_info(message: str):
    """Print info message in blue"""
    click.echo(f"{Fore.BLUE}ℹ {message}{Style.RESET_ALL}")


def print_json(data: dict, title: Optional[str] = None):
    """Print JSON data with syntax highlighting"""
    if title:
        print_info(title)
    click.echo(json.dumps(data, indent=2, default=str))


@click.group()
@click.version_option(version='1.0.0')
def cli():
    """
    RanomEngine CLI - VIN Search & Smart Goal Builder
    
    Automate car case creation from VIN or URL input using search, parsing, and AI.
    """
    pass


@cli.command()
@click.argument('vin')
@click.option('--limit', '-l', default=5, help='Maximum number of search results')
@click.option('--json', 'output_json', is_flag=True, help='Output results as JSON')
def search_vin(vin: str, limit: int, output_json: bool):
    """Search for vehicle listings using VIN number"""
    try:
        print_info(f"Searching for VIN: {vin}")
        
        search_service = VINSearchService()
        results = search_service.search_vin(vin)
        
        if not results:
            print_error("No search results found")
            return
        
        # Limit results
        results = results[:limit]
        
        if output_json:
            json_results = [
                {
                    'title': r.title,
                    'url': r.href,
                    'domain': r.domain,
                    'supported': r.is_supported,
                    'snippet': r.snippet
                }
                for r in results
            ]
            print_json(json_results, f"Found {len(results)} results:")
        else:
            print_success(f"Found {len(results)} results:")
            for i, result in enumerate(results, 1):
                status = "✓" if result.is_supported else "○"
                click.echo(f"{i}. {status} {result.title}")
                click.echo(f"   {Fore.CYAN}{result.href}{Style.RESET_ALL}")
                click.echo(f"   Domain: {result.domain}")
                if result.snippet:
                    click.echo(f"   {result.snippet[:100]}...")
                click.echo()
                
    except Exception as e:
        print_error(f"Search failed: {e}")


@cli.command()
@click.argument('url')
@click.option('--save-html', help='Save fetched HTML to file')
@click.option('--json', 'output_json', is_flag=True, help='Output results as JSON')
def fetch_page(url: str, save_html: Optional[str], output_json: bool):
    """Fetch and analyze a webpage using Selenium"""
    try:
        print_info(f"Fetching page: {url}")
        
        with DOMFetcherService() as fetcher:
            result = fetcher.fetch_page(url)
            
            if not result.success:
                print_error(f"Fetch failed: {result.error}")
                return
            
            # Save HTML if requested
            if save_html:
                with open(save_html, 'w', encoding='utf-8') as f:
                    f.write(result.html)
                print_success(f"HTML saved to: {save_html}")
            
            # Analyze page
            page_info = fetcher.detect_page_type(result.html)
            
            if output_json:
                json_data = {
                    'url': result.url,
                    'final_url': result.final_url,
                    'success': result.success,
                    'load_time': result.load_time,
                    'html_size': len(result.html),
                    'page_analysis': page_info
                }
                print_json(json_data, "Page fetch results:")
            else:
                print_success("Page fetched successfully")
                click.echo(f"Final URL: {result.final_url}")
                click.echo(f"Load time: {result.load_time:.2f}s")
                click.echo(f"HTML size: {len(result.html):,} characters")
                click.echo(f"Is listing: {page_info['is_listing']}")
                click.echo(f"Has vehicle data: {page_info['has_vehicle_data']}")
                if page_info['domain_indicators']:
                    click.echo(f"Domain indicators: {', '.join(page_info['domain_indicators'])}")
                    
    except Exception as e:
        print_error(f"Fetch failed: {e}")


@cli.command()
@click.argument('url')
@click.option('--parser', type=click.Choice(['cars.com', 'generic', 'auto']), default='auto',
              help='Parser to use (auto-detects by default)')
@click.option('--json', 'output_json', is_flag=True, help='Output results as JSON')
def parse_page(url: str, parser: str, output_json: bool):
    """Parse a vehicle listing page"""
    try:
        print_info(f"Parsing page: {url}")
        
        # Fetch page first
        with DOMFetcherService() as fetcher:
            fetch_result = fetcher.fetch_page(url)
            
            if not fetch_result.success:
                print_error(f"Failed to fetch page: {fetch_result.error}")
                return
        
        # Determine parser
        if parser == 'auto':
            if 'cars.com' in url.lower():
                parser_instance = CarsComParser()
                parser_name = 'cars.com'
            else:
                parser_instance = GenericParser()
                parser_name = 'generic'
        elif parser == 'cars.com':
            parser_instance = CarsComParser()
            parser_name = 'cars.com'
        else:
            parser_instance = GenericParser()
            parser_name = 'generic'
        
        print_info(f"Using {parser_name} parser")
        
        # Parse the page
        if parser_name == 'cars.com':
            vehicle_data = parser_instance.parse(fetch_result.html, url)
            if vehicle_data:
                parse_result = {'success': True, 'vehicle_data': vehicle_data.dict()}
            else:
                parse_result = {'success': False, 'error': 'Failed to extract vehicle data'}
        else:
            # Generic parser returns ParseResult
            parse_result_obj = parser_instance.parse(fetch_result.html, url)
            parse_result = {
                'success': parse_result_obj.success,
                'vehicle_data': parse_result_obj.vehicle_data.dict() if parse_result_obj.vehicle_data else None,
                'error': parse_result_obj.error,
                'confidence_score': parse_result_obj.confidence_score,
                'requires_ai': parse_result_obj.raw_extracted_data.get('requires_ai', False) if parse_result_obj.raw_extracted_data else False
            }
        
        if output_json:
            print_json(parse_result, "Parse results:")
        else:
            if parse_result['success']:
                print_success("Parsing successful")
                vehicle_data = parse_result['vehicle_data']
                if vehicle_data:
                    click.echo(f"VIN: {vehicle_data.get('vin', 'N/A')}")
                    click.echo(f"Vehicle: {vehicle_data.get('year', '')} {vehicle_data.get('make', '')} {vehicle_data.get('model', '')}")
                    click.echo(f"Price: ${vehicle_data.get('price', 'N/A'):,}" if vehicle_data.get('price') else "Price: N/A")
                    click.echo(f"Mileage: {vehicle_data.get('mileage', 'N/A'):,} miles" if vehicle_data.get('mileage') else "Mileage: N/A")
                    click.echo(f"Dealer: {vehicle_data.get('dealer_name', 'N/A')}")
                    if 'confidence_score' in parse_result:
                        click.echo(f"Confidence: {parse_result['confidence_score']:.2f}")
            else:
                print_error(f"Parsing failed: {parse_result.get('error', 'Unknown error')}")
                if parse_result.get('requires_ai'):
                    print_warning("Consider using --ai flag for AI-assisted extraction")
                    
    except Exception as e:
        print_error(f"Parsing failed: {e}")


@cli.command()
@click.argument('input_value')  # Can be VIN or URL
@click.option('--type', 'input_type', type=click.Choice(['vin', 'url', 'auto']), default='auto',
              help='Input type (auto-detects by default)')
@click.option('--no-api', is_flag=True, help="Don't create case via API, just extract data")
@click.option('--json', 'output_json', is_flag=True, help='Output full results as JSON')
@click.option('--save-trace', help='Save processing trace to JSON file')
def process(input_value: str, input_type: str, no_api: bool, output_json: bool, save_trace: Optional[str]):
    """Process VIN or URL through the complete pipeline"""
    try:
        print_info(f"Processing input: {input_value}")
        
        goal_builder = GoalBuilderService()
        
        try:
            if no_api:
                # Just process, don't create case
                trace = goal_builder.process_input(input_value, None if input_type == 'auto' else input_type)
                result = {
                    'input_value': input_value,
                    'input_type': trace.input_type,
                    'trace': trace.to_dict(),
                    'case_creation': {'skipped': True}
                }
            else:
                # Full pipeline including case creation
                result = goal_builder.process_and_create_case(input_value, None if input_type == 'auto' else input_type)
            
            # Save trace if requested
            if save_trace:
                with open(save_trace, 'w') as f:
                    json.dump(result, f, indent=2, default=str)
                print_success(f"Trace saved to: {save_trace}")
            
            if output_json:
                print_json(result, "Processing results:")
            else:
                # Pretty print results
                print_success(f"Input type detected: {result['input_type']}")
                
                trace = result['trace']
                if trace.get('search_time'):
                    print_info(f"Search completed in {trace['search_time']:.2f}s - found {len(trace.get('search_results', []))} results")
                
                if trace.get('fetch_success'):
                    print_success(f"Page fetched in {trace.get('fetch_time', 0):.2f}s")
                elif trace.get('fetch_error'):
                    print_error(f"Fetch failed: {trace['fetch_error']}")
                
                parse_result = trace.get('parse_result', {})
                if parse_result.get('success'):
                    print_success(f"Parsing successful using {parse_result.get('parser_used', 'unknown')} parser")
                    
                    # Show extracted vehicle data
                    vehicle_data = parse_result.get('vehicle_data', {})
                    if vehicle_data:
                        click.echo("\n" + Fore.CYAN + "Extracted Vehicle Data:" + Style.RESET_ALL)
                        for key, value in vehicle_data.items():
                            if value and key not in ['features', 'images']:
                                click.echo(f"  {key}: {value}")
                        
                        if vehicle_data.get('features'):
                            click.echo(f"  features: {len(vehicle_data['features'])} items")
                        if vehicle_data.get('images'):
                            click.echo(f"  images: {len(vehicle_data['images'])} items")
                    
                    confidence = parse_result.get('confidence_score')
                    if confidence:
                        color = Fore.GREEN if confidence >= 0.8 else Fore.YELLOW if confidence >= 0.6 else Fore.RED
                        click.echo(f"  {color}confidence: {confidence:.2f}{Style.RESET_ALL}")
                        
                else:
                    print_error(f"Parsing failed: {parse_result.get('error', 'Unknown error')}")
                
                # Show case creation results
                case_result = result.get('case_creation', {})
                if case_result.get('skipped'):
                    print_info("Case creation skipped (--no-api flag)")
                elif case_result.get('success'):
                    print_success("Case created successfully!")
                    if case_result.get('case_data'):
                        case_data = case_result['case_data']
                        if isinstance(case_data, dict) and 'id' in case_data:
                            click.echo(f"Case ID: {case_data['id']}")
                else:
                    print_error(f"Case creation failed: {case_result.get('error', 'Unknown error')}")
                
                print_info(f"Total processing time: {trace.get('total_time', 0):.2f}s")
                
        finally:
            goal_builder.cleanup()
            
    except Exception as e:
        print_error(f"Processing failed: {e}")
        import traceback
        if '--debug' in sys.argv:
            traceback.print_exc()


@cli.command()
@click.argument('content', type=click.File('r'))
@click.argument('url')
@click.option('--model', type=click.Choice(['openai', 'ollama']), default=None,
              help='AI model to use (uses config default if not specified)')
@click.option('--json', 'output_json', is_flag=True, help='Output results as JSON')
def extract_ai(content, url: str, model: Optional[str], output_json: bool):
    """Extract vehicle data from HTML content using AI"""
    try:
        html_content = content.read()
        print_info(f"Extracting vehicle data from content ({len(html_content)} chars) using AI")
        
        # Temporarily override model if specified
        original_model = config.AI_MODEL
        if model:
            config.AI_MODEL = model
        
        try:
            extractor = AIGoalExtractor()
            result = extractor.extract_from_html(html_content, url)
            
            if output_json:
                json_data = {
                    'success': result.success,
                    'extracted_data': result.extracted_data,
                    'confidence': result.confidence,
                    'model_used': result.model_used,
                    'processing_time': result.processing_time,
                    'error': result.error
                }
                print_json(json_data, "AI extraction results:")
            else:
                if result.success:
                    print_success(f"AI extraction successful (confidence: {result.confidence:.2f})")
                    click.echo(f"Model: {result.model_used}")
                    click.echo(f"Processing time: {result.processing_time:.2f}s")
                    
                    if result.extracted_data:
                        click.echo("\n" + Fore.CYAN + "Extracted Data:" + Style.RESET_ALL)
                        for key, value in result.extracted_data.items():
                            if value and key not in ['features', 'images']:
                                click.echo(f"  {key}: {value}")
                        
                        if result.extracted_data.get('features'):
                            click.echo(f"  features: {len(result.extracted_data['features'])} items")
                        if result.extracted_data.get('images'):
                            click.echo(f"  images: {len(result.extracted_data['images'])} items")
                else:
                    print_error(f"AI extraction failed: {result.error}")
                    
        finally:
            # Restore original model setting
            config.AI_MODEL = original_model
            
    except Exception as e:
        print_error(f"AI extraction failed: {e}")


@cli.command()
def config_info():
    """Show current configuration"""
    print_info("RanomEngine Configuration:")
    click.echo(f"DDGS Max Results: {config.DDGS_MAX_RESULTS}")
    click.echo(f"WebDriver Headless: {config.WEBDRIVER_HEADLESS}")
    click.echo(f"AI Model: {config.AI_MODEL}")
    click.echo(f"Backend URL: {config.BACKEND_URL}")
    click.echo(f"Supported Domains: {', '.join(config.SUPPORTED_DOMAINS)}")
    click.echo(f"Log Level: {config.LOG_LEVEL}")


@cli.command()
@click.argument('vin')
def validate_vin(vin: str):
    """Validate VIN format"""
    from services.vin_search import VINValidator
    
    if VINValidator.is_valid_vin(vin):
        print_success(f"VIN '{vin}' is valid")
    else:
        print_error(f"VIN '{vin}' is invalid")
        click.echo("VIN must be 17 characters, no I, O, or Q letters")


# ========================================
# RanomGoalMap Commands
# ========================================

@cli.command('list-mappings')
def list_mappings():
    """List all available site mappings"""
    print_info("Available Site Mappings")
    click.echo("=" * 40)
    
    try:
        mapper = GoalMapper()
        sites = mapper.get_available_sites()
        
        if not sites:
            print_warning("No mappings found!")
            return
        
        for site_id in sorted(sites):
            info = mapper.get_mapping_info(site_id)
            if info:
                validation = info['validation']
                status = "✅ Valid" if validation['valid'] else "❌ Invalid"
                click.echo(f"📋 {site_id}")
                click.echo(f"   Status: {status}")
                click.echo(f"   Fields: {info['field_count']}")
                if validation.get('errors'):
                    click.echo(f"   Errors: {len(validation['errors'])}")
                click.echo()
    
    except Exception as e:
        print_error(f"Error: {e}")


@cli.command('validate-mapping')
@click.argument('site_id')
def validate_mapping(site_id):
    """Validate a mapping configuration"""
    print_info(f"Validating mapping: {site_id}")
    click.echo("=" * 40)
    
    try:
        mapper = GoalMapper()
        validation = mapper.validate_mapping(site_id)
        
        if validation['valid']:
            print_success("Mapping is valid!")
            click.echo(f"📊 Fields: {validation['fields_count']}")
            
            if validation.get('warnings'):
                click.echo("\n⚠️ Warnings:")
                for warning in validation['warnings']:
                    click.echo(f"  • {warning}")
        else:
            print_error("Mapping has errors:")
            for error in validation['errors']:
                click.echo(f"  • {error}")
            
            if validation.get('warnings'):
                click.echo("\n⚠️ Additional warnings:")
                for warning in validation['warnings']:
                    click.echo(f"  • {warning}")
    
    except Exception as e:
        print_error(f"Error: {e}")


@cli.command('map-page')
@click.option('--url', help='URL to fetch and map')
@click.option('--html-file', help='Local HTML file to map')
@click.option('--site-id', required=True, help='Site mapping to use (e.g., cars_com, carfax)')
@click.option('--output', '-o', help='Output file for results')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
@click.option('--fallback-ai', is_flag=True, help='Use AI fallback if mapping fails')
def map_page(url, html_file, site_id, output, output_json, fallback_ai):
    """Extract vehicle data using DOM mapping"""
    
    if not url and not html_file:
        print_error("Must provide either --url or --html-file")
        return
    
    if url and html_file:
        print_error("Cannot use both --url and --html-file")
        return
    
    print_info(f"DOM Mapping Extraction: {site_id}")
    click.echo("=" * 50)
    
    try:
        # Get HTML content
        if url:
            click.echo(f"🌐 Fetching: {url}")
            
            with DOMFetcherService() as fetcher:
                fetch_result = fetcher.fetch_page(url)
                
                if not fetch_result.success:
                    print_error(f"Failed to fetch page: {fetch_result.error}")
                    return
                
                html_content = fetch_result.html
                print_success(f"Fetched {len(html_content):,} characters")
        else:
            click.echo(f"📄 Reading: {html_file}")
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            url = f"file://{html_file}"
        
        # Apply mapping
        click.echo(f"🔧 Applying mapping: {site_id}")
        mapper = GoalMapper()
        result = mapper.extract_from_html(html_content, site_id, url or "")
        
        click.echo(f"\n📊 Mapping Results:")
        click.echo(f"   Success: {'✅' if result.success else '❌'}")
        click.echo(f"   Fields mapped: {result.fields_mapped}/{result.fields_total}")
        click.echo(f"   Confidence: {result.confidence:.2f}")
        click.echo(f"   Fallback needed: {'Yes' if result.fallback_needed else 'No'}")
        
        if result.errors:
            click.echo(f"\n⚠️ Errors:")
            for error in result.errors:
                click.echo(f"   • {error}")
        
        # Show extracted data
        if result.extracted_data:
            click.echo(f"\n📋 Extracted Data:")
            for key, value in result.extracted_data.items():
                if isinstance(value, dict):
                    click.echo(f"   {key}:")
                    for subkey, subvalue in value.items():
                        click.echo(f"     {subkey}: {subvalue}")
                elif isinstance(value, list):
                    click.echo(f"   {key}: [{len(value)} items]")
                    if value:
                        click.echo(f"     First: {value[0]}")
                else:
                    click.echo(f"   {key}: {value}")
        
        # AI Fallback if requested and needed
        if fallback_ai and result.fallback_needed:
            click.echo(f"\n🧠 Applying AI fallback...")
            
            extractor = AIGoalExtractor()
            ai_result = extractor.extract_from_html(html_content, url or "", result.extracted_data)
            
            if ai_result.success:
                print_success(f"AI extraction successful! (Confidence: {ai_result.confidence:.2f})")
                # Merge results
                final_data = {**result.extracted_data, **ai_result.extracted_data}
                result.extracted_data = final_data
                result.confidence = max(result.confidence, ai_result.confidence)
            else:
                print_error(f"AI fallback failed: {ai_result.error}")
        
        # Convert to vehicle data and goal JSON
        if result.extracted_data:
            vehicle_data = mapper.to_vehicle_data(result.extracted_data)
            if vehicle_data:
                goal_json = vehicle_data.to_goal_json()
                
                click.echo(f"\n🎯 Goal JSON Preview:")
                click.echo(f"   Goal: {goal_json.get('goal', 'N/A')}")
                click.echo(f"   Vehicle: {goal_json.get('year', '')} {goal_json.get('make', '')} {goal_json.get('model', '')}")
                
                # Save results
                if output:
                    output_data = goal_json if output_json else result.extracted_data
                    with open(output, 'w') as f:
                        json.dump(output_data, f, indent=2)
                    print_success(f"Results saved to: {output}")
                
                # Show full JSON if requested
                if output_json and not output:
                    click.echo(f"\n📄 Full JSON:")
                    click.echo(json.dumps(goal_json, indent=2))
    
    except Exception as e:
        print_error(f"Error: {e}")


if __name__ == '__main__':
    cli() 