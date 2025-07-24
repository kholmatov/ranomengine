"""
RanomEngine Configuration Management

Handles all configuration parameters with environment variable support
and default values for the VIN search and goal extraction system.
"""

import os
from typing import List, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


@dataclass
class Config:
    """Main configuration class for RanomEngine"""
    
    # DuckDuckGo Search Settings
    DDGS_MAX_RESULTS: int = int(os.getenv('DDGS_MAX_RESULTS', '10'))
    DDGS_TIMEOUT: int = int(os.getenv('DDGS_TIMEOUT', '30'))
    
    # Supported domains for parsing
    SUPPORTED_DOMAINS: List[str] = field(default_factory=lambda: [
        'cars.com',
        'carfax.com', 
        'capitalone.com',
        'autotrader.com',
        'toyota.com'
    ])
    
    # Selenium WebDriver Settings
    WEBDRIVER_TIMEOUT: int = int(os.getenv('WEBDRIVER_TIMEOUT', '30'))
    WEBDRIVER_HEADLESS: bool = os.getenv('WEBDRIVER_HEADLESS', 'True').lower() == 'true'
    WEBDRIVER_IMPLICITLY_WAIT: int = int(os.getenv('WEBDRIVER_IMPLICITLY_WAIT', '10'))
    
    # AI Model Configuration
    AI_MODEL: str = os.getenv('AI_MODEL', 'ollama')  # 'ollama' or 'openai'
    OPENAI_API_KEY: Optional[str] = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL: str = os.getenv('OPENAI_MODEL', 'gpt-4')
    OLLAMA_BASE_URL: str = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    OLLAMA_MODEL: str = os.getenv('OLLAMA_MODEL', 'llama2')
    
    # Ranom API Configuration
    BACKEND_URL: str = os.getenv('BACKEND_URL', 'https://api.ranom.com')
    API_KEY: Optional[str] = os.getenv('API_KEY')
    CASES_ENDPOINT: str = '/api/cases/create_from_goal/'
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT: str = os.getenv('LOG_FORMAT', 'json')
    
    # User Agent for web requests
    USER_AGENT: str = os.getenv(
        'USER_AGENT', 
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    
    # Search Query Template
    VIN_SEARCH_TEMPLATE: str = '{vin} site:cars.com OR site:carfax.com OR site:capitalone.com OR site:autotrader.com'
    
    def validate(self) -> None:
        """Validate configuration settings"""
        if self.AI_MODEL == 'openai' and not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when using OpenAI model")
        
        if not self.BACKEND_URL:
            raise ValueError("BACKEND_URL is required for case creation")
    
    @property
    def selenium_options(self) -> List[str]:
        """Get Selenium Chrome options"""
        options = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-web-security',
            '--allow-running-insecure-content',
            '--disable-extensions',
            f'--user-agent={self.USER_AGENT}'
        ]
        
        if self.WEBDRIVER_HEADLESS:
            options.append('--headless')
            
        return options


# Global config instance
config = Config()

# Validate configuration on import
config.validate() 