#!/usr/bin/env python3
"""
Setup Script for Content Machine Workflow
Handles initial setup, configuration validation, and deployment preparation.
"""

import json
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, List
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContentMachineSetup:
    """Setup and configuration manager for the content machine workflow."""
    
    def __init__(self, project_root: str = "."):
        """Initialize setup with project root directory."""
        self.project_root = Path(project_root).resolve()
        self.config_dir = self.project_root / "config"
        self.scripts_dir = self.project_root / "scripts"
        self.workflows_dir = self.project_root / "workflows"
        
        logger.info(f"Initializing setup for project: {self.project_root}")
    
    def validate_project_structure(self) -> bool:
        """Validate that all required directories and files exist."""
        logger.info("Validating project structure...")
        
        required_dirs = [
            self.config_dir,
            self.scripts_dir,
            self.workflows_dir,
            self.project_root / "templates",
            self.project_root / "docs"
        ]
        
        required_files = [
            self.config_dir / "api-keys.template.json",
            self.config_dir / "prompts.json",
            self.config_dir / "environment.json",
            self.scripts_dir / "content_machine.py",
            self.scripts_dir / "webhook_handler.py",
            self.workflows_dir / "main-workflow.json",
            self.project_root / "requirements.txt",
            self.project_root / "README.md"
        ]
        
        # Check directories
        for directory in required_dirs:
            if not directory.exists():
                logger.error(f"Missing required directory: {directory}")
                return False
            logger.info(f"✓ Directory exists: {directory}")
        
        # Check files
        for file_path in required_files:
            if not file_path.exists():
                logger.error(f"Missing required file: {file_path}")
                return False
            logger.info(f"✓ File exists: {file_path}")
        
        logger.info("✓ Project structure validation passed")
        return True
    
    def check_api_keys_configuration(self) -> Dict[str, bool]:
        """Check if API keys are properly configured."""
        logger.info("Checking API keys configuration...")
        
        api_keys_file = self.config_dir / "api-keys.json"
        template_file = self.config_dir / "api-keys.template.json"
        
        if not api_keys_file.exists():
            logger.warning(f"API keys file not found: {api_keys_file}")
            logger.info(f"Please copy {template_file} to {api_keys_file} and configure your API keys")
            return {"configured": False, "file_exists": False}
        
        try:
            with open(api_keys_file, 'r') as f:
                config = json.load(f)
            
            # Check for placeholder values
            checks = {
                "openai": self._check_api_key(config.get("openai", {}).get("api_key")),
                "firecrawl": self._check_api_key(config.get("firecrawl", {}).get("api_key")),
                "notion": self._check_api_key(config.get("notion", {}).get("token")),
                "slack": self._check_webhook_url(config.get("slack", {}).get("webhook_url")),
                "google_docs": bool(config.get("google_docs", {}).get("credentials_file"))
            }
            
            configured_count = sum(checks.values())
            total_count = len(checks)
            
            logger.info(f"API configuration status: {configured_count}/{total_count} services configured")
            
            for service, configured in checks.items():
                status = "✓" if configured else "✗"
                logger.info(f"  {status} {service}")
            
            return {
                "configured": configured_count >= 3,  # At least 3 services needed for basic functionality
                "file_exists": True,
                "services": checks,
                "configured_count": configured_count,
                "total_count": total_count
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in API keys file: {e}")
            return {"configured": False, "file_exists": True, "error": "Invalid JSON"}
        except Exception as e:
            logger.error(f"Error reading API keys file: {e}")
            return {"configured": False, "file_exists": True, "error": str(e)}
    
    def _check_api_key(self, api_key: str) -> bool:
        """Check if API key is configured (not placeholder)."""
        if not api_key:
            return False
        
        placeholder_indicators = [
            "your-",
            "placeholder",
            "example",
            "test-key",
            "api-key-here"
        ]
        
        return not any(indicator in api_key.lower() for indicator in placeholder_indicators)
    
    def _check_webhook_url(self, webhook_url: str) -> bool:
        """Check if webhook URL is configured."""
        if not webhook_url:
            return False
        
        return webhook_url.startswith(("http://", "https://")) and "webhook" in webhook_url.lower()
    
    def install_dependencies(self) -> bool:
        """Install Python dependencies from requirements.txt."""
        logger.info("Installing Python dependencies...")
        
        requirements_file = self.project_root / "requirements.txt"
        
        if not requirements_file.exists():
            logger.error("requirements.txt not found")
            return False
        
        try:
            # Check if pip is available
            subprocess.run([sys.executable, "-m", "pip", "--version"], 
                         check=True, capture_output=True)
            
            # Install requirements
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✓ Dependencies installed successfully")
                return True
            else:
                logger.error(f"Failed to install dependencies: {result.stderr}")
                return False
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Error installing dependencies: {e}")
            return False
        except FileNotFoundError:
            logger.error("pip not found. Please ensure Python and pip are installed.")
            return False
    
    def create_template_files(self) -> bool:
        """Create template files for content generation."""
        logger.info("Creating template files...")
        
        templates_dir = self.project_root / "templates"
        templates_dir.mkdir(exist_ok=True)
        
        templates = {
            "blog-template.md": self._get_blog_template(),
            "twitter-template.md": self._get_twitter_template(),
            "newsletter-template.md": self._get_newsletter_template(),
            "seo-template.md": self._get_seo_template()
        }
        
        for filename, content in templates.items():
            template_file = templates_dir / filename
            try:
                with open(template_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f"✓ Created template: {filename}")
            except Exception as e:
                logger.error(f"Failed to create template {filename}: {e}")
                return False
        
        return True
    
    def _get_blog_template(self) -> str:
        """Get blog post template."""
        return """# {title}

*Source: [{original_title}]({original_url})*  
*Generated: {timestamp}*

---

{content}

---

*This content was automatically generated from the original article using AI. Please review and edit as needed.*
"""
    
    def _get_twitter_template(self) -> str:
        """Get Twitter thread template."""
        return """# Twitter Thread: {title}

*Source: [{original_title}]({original_url})*  
*Generated: {timestamp}*

---

{content}

---

**Copy-paste ready tweets above** 📋

*This Twitter thread was automatically generated from the original article using AI. Please review and edit as needed.*
"""
    
    def _get_newsletter_template(self) -> str:
        """Get newsletter template."""
        return """# Newsletter: {title}

*Source: [{original_title}]({original_url})*  
*Generated: {timestamp}*

---

{content}

---

*This newsletter summary was automatically generated from the original article using AI. Please review and edit as needed.*
"""
    
    def _get_seo_template(self) -> str:
        """Get SEO summary template."""
        return """# SEO Analysis: {title}

*Source: [{original_title}]({original_url})*  
*Generated: {timestamp}*

---

{content}

---

*This SEO analysis was automatically generated from the original article using AI. Please review and validate the recommendations.*
"""
    
    def create_documentation(self) -> bool:
        """Create documentation files."""
        logger.info("Creating documentation files...")
        
        docs_dir = self.project_root / "docs"
        docs_dir.mkdir(exist_ok=True)
        
        docs = {
            "setup-guide.md": self._get_setup_guide(),
            "api-reference.md": self._get_api_reference(),
            "troubleshooting.md": self._get_troubleshooting_guide()
        }
        
        for filename, content in docs.items():
            doc_file = docs_dir / filename
            try:
                with open(doc_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f"✓ Created documentation: {filename}")
            except Exception as e:
                logger.error(f"Failed to create documentation {filename}: {e}")
                return False
        
        return True
    
    def _get_setup_guide(self) -> str:
        """Get setup guide content."""
        return """# Content Machine Setup Guide

## Prerequisites

1. **Python 3.8+** installed
2. **API Keys** for the following services:
   - OpenAI (GPT-4 access)
   - Firecrawl
   - Google Docs (optional)
   - Notion (optional)
   - Slack (for notifications)

## Step-by-Step Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Keys

1. Copy the template file:
   ```bash
   cp config/api-keys.template.json config/api-keys.json
   ```

2. Edit `config/api-keys.json` with your actual API keys:
   - **OpenAI**: Get from https://platform.openai.com/api-keys
   - **Firecrawl**: Get from https://firecrawl.dev/
   - **Notion**: Create integration at https://www.notion.so/my-integrations
   - **Slack**: Create webhook at https://api.slack.com/messaging/webhooks
   - **Google Docs**: Set up OAuth2 credentials

### 3. Test the Setup

```bash
python scripts/setup.py --validate
```

### 4. Run a Test

```bash
python scripts/content_machine.py "https://example.com/article"
```

### 5. Start the Webhook Handler

```bash
python scripts/webhook_handler.py --port 5000
```

## n8n Integration

1. Import `workflows/main-workflow.json` into your n8n instance
2. Configure credentials for each service
3. Activate the workflow
4. Test with a webhook call

## Troubleshooting

See `troubleshooting.md` for common issues and solutions.
"""
    
    def _get_api_reference(self) -> str:
        """Get API reference content."""
        return """# Content Machine API Reference

## Webhook Endpoint

### POST /webhook/content-machine

Process a URL through the content generation pipeline.

**Request Body:**
```json
{
  "url": "https://example.com/article"
}
```

**Response:**
```json
{
  "success": true,
  "title": "Article Title",
  "url": "https://example.com/article",
  "timestamp": "2025-01-07T10:00:00Z",
  "content_types": ["blog_post", "twitter_thread", "newsletter_summary", "seo_summary"],
  "storage_results": {
    "google_docs": {...},
    "notion": "page_id"
  }
}
```

## Direct Python Usage

### ContentMachine Class

```python
from scripts.content_machine import ContentMachine

machine = ContentMachine()
result = await machine.process_url("https://example.com/article")
```

### Methods

- `scrape_content(url)`: Extract content using Firecrawl
- `generate_content(scraped_data)`: Generate all content formats
- `store_content(content_bundle)`: Save to Google Docs and Notion
- `send_notification(content_bundle, storage_results)`: Send Slack alert
- `process_url(url)`: Complete pipeline

## Configuration

### API Keys (`config/api-keys.json`)

Required services:
- `openai.api_key`: OpenAI API key
- `firecrawl.api_key`: Firecrawl API key

Optional services:
- `notion.token`: Notion integration token
- `slack.webhook_url`: Slack webhook URL
- `google_docs.credentials_file`: Google OAuth2 credentials

### Prompts (`config/prompts.json`)

Customize content generation prompts:
- `blog_rewrite`: Blog post generation
- `twitter_thread`: Twitter thread creation
- `newsletter_summary`: Newsletter summary
- `seo_summary`: SEO analysis

### Environment (`config/environment.json`)

Workflow settings:
- `max_retries`: Error retry attempts
- `timeout_seconds`: Request timeout
- `parallel_content_generation`: Enable parallel processing
"""
    
    def _get_troubleshooting_guide(self) -> str:
        """Get troubleshooting guide content."""
        return """# Content Machine Troubleshooting Guide

## Common Issues

### 1. API Key Errors

**Problem:** "Invalid API key" or authentication errors

**Solutions:**
- Verify API keys in `config/api-keys.json`
- Check for extra spaces or quotes in keys
- Ensure keys have proper permissions
- Test keys individually with curl commands

### 2. Firecrawl Scraping Fails

**Problem:** "Failed to scrape content" errors

**Solutions:**
- Check if URL is accessible
- Verify Firecrawl API key and quota
- Try with a simpler URL (e.g., Wikipedia article)
- Check Firecrawl service status

### 3. OpenAI Generation Errors

**Problem:** Content generation fails or returns errors

**Solutions:**
- Verify OpenAI API key and billing
- Check model availability (gpt-4 vs gpt-3.5-turbo)
- Reduce content length if hitting token limits
- Check OpenAI service status

### 4. Google Docs Integration Issues

**Problem:** Cannot save to Google Docs

**Solutions:**
- Set up OAuth2 credentials properly
- Grant necessary permissions to service account
- Check Google Drive API quotas
- Verify folder permissions

### 5. Notion Database Errors

**Problem:** Cannot create Notion pages

**Solutions:**
- Verify Notion integration token
- Check database ID is correct
- Ensure integration has access to database
- Verify database schema matches expected properties

### 6. Slack Notifications Not Working

**Problem:** Slack messages not sent

**Solutions:**
- Verify webhook URL is correct
- Check Slack app permissions
- Test webhook with curl
- Check message format compliance

## Debugging Tips

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Test Individual Components

```bash
# Test scraping only
python -c "import asyncio; from scripts.content_machine import ContentMachine; print(asyncio.run(ContentMachine().scrape_content('https://example.com')))"

# Test webhook handler
curl -X POST http://localhost:5000/test -H "Content-Type: application/json" -d '{"url":"https://example.com"}'
```

### Check Service Status

- OpenAI: https://status.openai.com/
- Firecrawl: Check their status page
- Google APIs: https://status.cloud.google.com/
- Notion: https://status.notion.so/
- Slack: https://status.slack.com/

## Performance Issues

### Slow Content Generation

- Enable parallel processing in `config/environment.json`
- Use gpt-3.5-turbo instead of gpt-4 for faster generation
- Reduce max_tokens in prompts

### Rate Limiting

- Add delays between API calls
- Implement exponential backoff
- Monitor API usage quotas

## Getting Help

1. Check logs for specific error messages
2. Verify all configuration files
3. Test with minimal examples
4. Check service status pages
5. Review API documentation for each service
"""
    
    def run_full_setup(self) -> bool:
        """Run complete setup process."""
        logger.info("Starting full setup process...")
        
        steps = [
            ("Validating project structure", self.validate_project_structure),
            ("Installing dependencies", self.install_dependencies),
            ("Creating template files", self.create_template_files),
            ("Creating documentation", self.create_documentation),
        ]
        
        for step_name, step_function in steps:
            logger.info(f"Running: {step_name}")
            if not step_function():
                logger.error(f"Setup failed at step: {step_name}")
                return False
        
        # Check API configuration (non-blocking)
        api_status = self.check_api_keys_configuration()
        if not api_status.get("configured", False):
            logger.warning("API keys not fully configured. Please update config/api-keys.json")
        
        logger.info("✓ Setup completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Configure your API keys in config/api-keys.json")
        logger.info("2. Test the workflow: python scripts/content_machine.py <url>")
        logger.info("3. Start the webhook handler: python scripts/webhook_handler.py")
        
        return True


def main():
    """Main entry point for setup script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Content Machine Setup')
    parser.add_argument('--validate', action='store_true', help='Validate setup only')
    parser.add_argument('--install-deps', action='store_true', help='Install dependencies only')
    parser.add_argument('--check-config', action='store_true', help='Check API configuration only')
    parser.add_argument('--project-root', default='.', help='Project root directory')
    
    args = parser.parse_args()
    
    setup = ContentMachineSetup(args.project_root)
    
    if args.validate:
        success = setup.validate_project_structure()
        sys.exit(0 if success else 1)
    
    if args.install_deps:
        success = setup.install_dependencies()
        sys.exit(0 if success else 1)
    
    if args.check_config:
        status = setup.check_api_keys_configuration()
        print(json.dumps(status, indent=2))
        sys.exit(0 if status.get("configured", False) else 1)
    
    # Run full setup
    success = setup.run_full_setup()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
