#!/usr/bin/env python3
"""
Test Script for Content Machine Workflow
Tests individual components and the complete workflow.
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

import httpx
from content_machine import ContentMachine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WorkflowTester:
    """Test suite for the content machine workflow."""
    
    def __init__(self, config_path: str = "config/api-keys.json"):
        """Initialize the workflow tester."""
        self.config_path = config_path
        self.test_results = {}
        
    async def test_api_connectivity(self) -> Dict[str, bool]:
        """Test connectivity to all external APIs."""
        logger.info("Testing API connectivity...")
        
        results = {}
        
        try:
            # Load configuration
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Test OpenAI API
            results['openai'] = await self._test_openai_api(config.get('openai', {}))
            
            # Test Firecrawl API
            results['firecrawl'] = await self._test_firecrawl_api(config.get('firecrawl', {}))
            
            # Test Slack webhook
            results['slack'] = await self._test_slack_webhook(config.get('slack', {}))
            
            # Test Notion API
            results['notion'] = await self._test_notion_api(config.get('notion', {}))
            
            return results
            
        except Exception as e:
            logger.error(f"Error testing API connectivity: {e}")
            return {'error': str(e)}
    
    async def _test_openai_api(self, config: Dict[str, Any]) -> bool:
        """Test OpenAI API connectivity."""
        try:
            import openai
            client = openai.OpenAI(api_key=config.get('api_key'))
            
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Test message"}],
                max_tokens=10
            )
            
            logger.info("✓ OpenAI API connection successful")
            return True
            
        except Exception as e:
            logger.error(f"✗ OpenAI API test failed: {e}")
            return False
    
    async def _test_firecrawl_api(self, config: Dict[str, Any]) -> bool:
        """Test Firecrawl API connectivity."""
        try:
            headers = {
                "Authorization": f"Bearer {config.get('api_key')}",
                "Content-Type": "application/json"
            }
            
            # Test with a simple, reliable URL
            payload = {
                "url": "https://example.com",
                "formats": ["markdown"],
                "onlyMainContent": True
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{config.get('base_url', 'https://api.firecrawl.dev')}/v0/scrape",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    logger.info("✓ Firecrawl API connection successful")
                    return True
                else:
                    logger.error(f"✗ Firecrawl API test failed: HTTP {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ Firecrawl API test failed: {e}")
            return False
    
    async def _test_slack_webhook(self, config: Dict[str, Any]) -> bool:
        """Test Slack webhook connectivity."""
        try:
            webhook_url = config.get('webhook_url')
            if not webhook_url or 'your-slack-webhook' in webhook_url:
                logger.warning("✗ Slack webhook not configured")
                return False
            
            test_message = {
                "text": "Content Machine test message - please ignore",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "🧪 *Content Machine Test*\nThis is a test message from the workflow setup. You can ignore this."
                        }
                    }
                ]
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=test_message)
                
                if response.status_code == 200:
                    logger.info("✓ Slack webhook connection successful")
                    return True
                else:
                    logger.error(f"✗ Slack webhook test failed: HTTP {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"✗ Slack webhook test failed: {e}")
            return False
    
    async def _test_notion_api(self, config: Dict[str, Any]) -> bool:
        """Test Notion API connectivity."""
        try:
            from notion_client import Client
            
            token = config.get('token')
            if not token or 'your-notion' in token:
                logger.warning("✗ Notion API not configured")
                return False
            
            client = Client(auth=token)
            
            # Test by listing users (simple API call)
            response = await asyncio.to_thread(client.users.list)
            
            if response.get('results') is not None:
                logger.info("✓ Notion API connection successful")
                return True
            else:
                logger.error("✗ Notion API test failed: Invalid response")
                return False
                
        except Exception as e:
            logger.error(f"✗ Notion API test failed: {e}")
            return False
    
    async def test_content_scraping(self, test_url: str = "https://example.com") -> Dict[str, Any]:
        """Test content scraping functionality."""
        logger.info(f"Testing content scraping with URL: {test_url}")
        
        try:
            machine = ContentMachine(self.config_path)
            scraped_data = await machine.scrape_content(test_url)
            
            result = {
                'success': True,
                'url': test_url,
                'title': scraped_data.get('title', ''),
                'content_length': len(scraped_data.get('content', '')),
                'has_metadata': bool(scraped_data.get('metadata'))
            }
            
            logger.info(f"✓ Content scraping successful: {result['content_length']} characters")
            return result
            
        except Exception as e:
            logger.error(f"✗ Content scraping failed: {e}")
            return {'success': False, 'error': str(e), 'url': test_url}
    
    async def test_content_generation(self, sample_content: Optional[str] = None) -> Dict[str, Any]:
        """Test content generation functionality."""
        logger.info("Testing content generation...")
        
        if not sample_content:
            sample_content = """
            This is a sample article about artificial intelligence and automation.
            AI is transforming how we work and live. Machine learning algorithms
            can now process vast amounts of data and generate insights that help
            businesses make better decisions. The future of AI looks promising
            with applications in healthcare, finance, and education.
            """
        
        try:
            machine = ContentMachine(self.config_path)
            
            # Create mock scraped data
            scraped_data = {
                'title': 'Test Article: AI and Automation',
                'content': sample_content,
                'url': 'https://example.com/test-article',
                'metadata': {}
            }
            
            content_bundle = await machine.generate_content(scraped_data)
            
            result = {
                'success': True,
                'content_types': {
                    'blog_post': len(content_bundle.blog_post) > 0,
                    'twitter_thread': len(content_bundle.twitter_thread) > 0,
                    'newsletter_summary': len(content_bundle.newsletter_summary) > 0,
                    'seo_summary': len(content_bundle.seo_summary) > 0
                },
                'lengths': {
                    'blog_post': len(content_bundle.blog_post),
                    'twitter_thread': len(content_bundle.twitter_thread),
                    'newsletter_summary': len(content_bundle.newsletter_summary),
                    'seo_summary': len(content_bundle.seo_summary)
                }
            }
            
            generated_count = sum(result['content_types'].values())
            logger.info(f"✓ Content generation successful: {generated_count}/4 formats generated")
            
            return result
            
        except Exception as e:
            logger.error(f"✗ Content generation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def test_full_workflow(self, test_url: str) -> Dict[str, Any]:
        """Test the complete workflow end-to-end."""
        logger.info(f"Testing full workflow with URL: {test_url}")
        
        start_time = time.time()
        
        try:
            machine = ContentMachine(self.config_path)
            result = await machine.process_url(test_url)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            result['processing_time_seconds'] = round(processing_time, 2)
            
            if result.get('success'):
                logger.info(f"✓ Full workflow completed successfully in {processing_time:.2f}s")
            else:
                logger.error(f"✗ Full workflow failed: {result.get('error', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            end_time = time.time()
            processing_time = end_time - start_time
            
            logger.error(f"✗ Full workflow failed after {processing_time:.2f}s: {e}")
            return {
                'success': False,
                'error': str(e),
                'url': test_url,
                'processing_time_seconds': round(processing_time, 2)
            }
    
    async def test_webhook_handler(self, port: int = 5000) -> Dict[str, Any]:
        """Test the webhook handler endpoint."""
        logger.info(f"Testing webhook handler on port {port}")
        
        webhook_url = f"http://localhost:{port}/webhook/content-machine"
        test_payload = {"url": "https://example.com"}
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(webhook_url, json=test_payload)
                
                result = {
                    'success': response.status_code == 200,
                    'status_code': response.status_code,
                    'response_time_ms': response.elapsed.total_seconds() * 1000
                }
                
                if response.status_code == 200:
                    result['response_data'] = response.json()
                    logger.info(f"✓ Webhook handler test successful: {response.status_code}")
                else:
                    result['error'] = response.text
                    logger.error(f"✗ Webhook handler test failed: HTTP {response.status_code}")
                
                return result
                
        except httpx.ConnectError:
            logger.error(f"✗ Webhook handler not running on port {port}")
            return {
                'success': False,
                'error': f'Connection refused - webhook handler not running on port {port}'
            }
        except Exception as e:
            logger.error(f"✗ Webhook handler test failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def run_all_tests(self, test_url: str = "https://example.com") -> Dict[str, Any]:
        """Run all tests and return comprehensive results."""
        logger.info("Running comprehensive test suite...")
        
        all_results = {
            'timestamp': time.time(),
            'test_url': test_url,
            'tests': {}
        }
        
        # Test 1: API Connectivity
        logger.info("\n=== Test 1: API Connectivity ===")
        all_results['tests']['api_connectivity'] = await self.test_api_connectivity()
        
        # Test 2: Content Scraping
        logger.info("\n=== Test 2: Content Scraping ===")
        all_results['tests']['content_scraping'] = await self.test_content_scraping(test_url)
        
        # Test 3: Content Generation
        logger.info("\n=== Test 3: Content Generation ===")
        all_results['tests']['content_generation'] = await self.test_content_generation()
        
        # Test 4: Full Workflow (only if previous tests passed)
        if (all_results['tests']['content_scraping'].get('success') and 
            all_results['tests']['content_generation'].get('success')):
            logger.info("\n=== Test 4: Full Workflow ===")
            all_results['tests']['full_workflow'] = await self.test_full_workflow(test_url)
        else:
            logger.warning("Skipping full workflow test due to previous failures")
            all_results['tests']['full_workflow'] = {'success': False, 'skipped': True}
        
        # Test 5: Webhook Handler (optional)
        logger.info("\n=== Test 5: Webhook Handler (optional) ===")
        all_results['tests']['webhook_handler'] = await self.test_webhook_handler()
        
        # Generate summary
        all_results['summary'] = self._generate_test_summary(all_results['tests'])
        
        return all_results
    
    def _generate_test_summary(self, tests: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of test results."""
        summary = {
            'total_tests': len(tests),
            'passed_tests': 0,
            'failed_tests': 0,
            'skipped_tests': 0,
            'overall_success': True
        }
        
        for test_name, test_result in tests.items():
            if test_result.get('skipped'):
                summary['skipped_tests'] += 1
            elif test_result.get('success'):
                summary['passed_tests'] += 1
            else:
                summary['failed_tests'] += 1
                summary['overall_success'] = False
        
        return summary


async def main():
    """Main entry point for test script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Content Machine Workflow Tester')
    parser.add_argument('--url', default='https://example.com', help='Test URL to process')
    parser.add_argument('--test', choices=['api', 'scraping', 'generation', 'workflow', 'webhook', 'all'], 
                       default='all', help='Specific test to run')
    parser.add_argument('--config', default='config/api-keys.json', help='Configuration file path')
    parser.add_argument('--port', type=int, default=5000, help='Webhook handler port')
    parser.add_argument('--output', help='Output file for test results (JSON)')
    
    args = parser.parse_args()
    
    tester = WorkflowTester(args.config)
    
    try:
        if args.test == 'all':
            results = await tester.run_all_tests(args.url)
        elif args.test == 'api':
            results = await tester.test_api_connectivity()
        elif args.test == 'scraping':
            results = await tester.test_content_scraping(args.url)
        elif args.test == 'generation':
            results = await tester.test_content_generation()
        elif args.test == 'workflow':
            results = await tester.test_full_workflow(args.url)
        elif args.test == 'webhook':
            results = await tester.test_webhook_handler(args.port)
        
        # Output results
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Test results saved to: {args.output}")
        else:
            print(json.dumps(results, indent=2))
        
        # Exit with appropriate code
        if isinstance(results, dict) and results.get('summary', {}).get('overall_success', True):
            sys.exit(0)
        else:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
