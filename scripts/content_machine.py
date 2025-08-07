#!/usr/bin/env python3
"""
Content Machine Workflow
Main orchestration script for the automated content creation pipeline.
"""

import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import httpx
import openai
from notion_client import Client as NotionClient
from slack_sdk.webhook import WebhookClient
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Import quality validator
from quality_validator import ContentQualityValidator, QualityScore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ContentBundle:
    """Container for all generated content formats."""
    original_url: str
    title: str
    original_content: str
    blog_post: str
    twitter_thread: str
    newsletter_summary: str
    seo_summary: str
    metadata: Dict[str, Any]
    timestamp: datetime
    
    # Quality assessment results
    quality_scores: Optional[Dict[str, QualityScore]] = None
    overall_quality_score: Optional[float] = None
    requires_review: bool = False
    auto_approved: bool = False


class ContentMachine:
    """Main content automation workflow orchestrator."""
    
    def __init__(self, config_path: str = "config/api-keys.json"):
        """Initialize the content machine with API configurations."""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.prompts = self._load_prompts()
        self.environment = self._load_environment()
        
        # Initialize API clients
        self.openai_client = openai.OpenAI(api_key=self.config["openai"]["api_key"])
        self.notion_client = NotionClient(auth=self.config["notion"]["token"])
        self.slack_client = WebhookClient(self.config["slack"]["webhook_url"])
        
        # Initialize quality validator
        self.quality_validator = ContentQualityValidator(config_path)
        
        logger.info("Content Machine initialized successfully")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load API configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise
    
    def _load_prompts(self) -> Dict[str, Any]:
        """Load content generation prompts."""
        with open("config/prompts.json", 'r') as f:
            return json.load(f)
    
    def _load_environment(self) -> Dict[str, Any]:
        """Load environment settings."""
        with open("config/environment.json", 'r') as f:
            return json.load(f)
    
    async def scrape_content(self, url: str) -> Dict[str, Any]:
        """Scrape and clean content using Firecrawl API."""
        logger.info(f"Scraping content from: {url}")
        
        firecrawl_config = self.config["firecrawl"]
        headers = {
            "Authorization": f"Bearer {firecrawl_config['api_key']}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "url": url,
            "formats": ["markdown", "html"],
            "onlyMainContent": True,
            "includeTags": ["title", "meta", "h1", "h2", "h3"],
            "excludeTags": ["nav", "footer", "aside", "script", "style"],
            "waitFor": 2000
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{firecrawl_config['base_url']}/v0/scrape",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                if not data.get("success"):
                    raise Exception(f"Firecrawl scraping failed: {data.get('error', 'Unknown error')}")
                
                content_data = data["data"]
                logger.info(f"Successfully scraped {len(content_data.get('content', ''))} characters")
                
                return {
                    "title": content_data.get("title", "Untitled"),
                    "content": content_data.get("content", ""),
                    "metadata": content_data.get("metadata", {}),
                    "url": url
                }
                
            except httpx.HTTPError as e:
                logger.error(f"HTTP error during scraping: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error during scraping: {e}")
                raise
    
    async def generate_content(self, scraped_data: Dict[str, Any]) -> ContentBundle:
        """Generate all content formats using GPT-4."""
        logger.info("Generating content in multiple formats")
        
        content = scraped_data["content"]
        title = scraped_data["title"]
        url = scraped_data["url"]
        
        # Prepare content generation tasks
        generation_tasks = []
        
        for content_type in ["blog_rewrite", "twitter_thread", "newsletter_summary", "seo_summary"]:
            task = self._generate_single_content(content_type, content, title, url)
            generation_tasks.append(task)
        
        # Execute content generation in parallel
        if self.environment["workflow_settings"]["parallel_content_generation"]:
            results = await asyncio.gather(*generation_tasks, return_exceptions=True)
        else:
            results = []
            for task in generation_tasks:
                result = await task
                results.append(result)
        
        # Process results
        blog_post, twitter_thread, newsletter_summary, seo_summary = results
        
        # Handle any exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                content_types = ["blog_rewrite", "twitter_thread", "newsletter_summary", "seo_summary"]
                logger.error(f"Failed to generate {content_types[i]}: {result}")
                results[i] = f"Error generating content: {str(result)}"
        
        return ContentBundle(
            original_url=url,
            title=title,
            original_content=content,
            blog_post=blog_post,
            twitter_thread=twitter_thread,
            newsletter_summary=newsletter_summary,
            seo_summary=seo_summary,
            metadata=scraped_data.get("metadata", {}),
            timestamp=datetime.now()
        )
    
    async def _generate_single_content(self, content_type: str, content: str, title: str, url: str) -> str:
        """Generate a single content format using GPT-4."""
        prompt_config = self.prompts[content_type]
        
        try:
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model=self.config["openai"]["model"],
                messages=[
                    {"role": "system", "content": prompt_config["system_prompt"]},
                    {"role": "user", "content": prompt_config["user_prompt"].format(
                        content=content,
                        title=title,
                        url=url
                    )}
                ],
                max_tokens=self.config["openai"]["max_tokens"],
                temperature=self.config["openai"]["temperature"]
            )
            
            generated_content = response.choices[0].message.content
            logger.info(f"Generated {content_type}: {len(generated_content)} characters")
            return generated_content
            
        except Exception as e:
            logger.error(f"Error generating {content_type}: {e}")
            raise
    
    async def validate_content_quality(self, content_bundle: ContentBundle) -> ContentBundle:
        """Validate quality of all generated content formats."""
        logger.info("Validating content quality for all formats")
        
        try:
            quality_scores = {}
            content_types = {
                'blog_post': content_bundle.blog_post,
                'twitter_thread': content_bundle.twitter_thread,
                'newsletter_summary': content_bundle.newsletter_summary,
                'seo_summary': content_bundle.seo_summary
            }
            
            # Validate each content type
            validation_tasks = []
            for content_type, content in content_types.items():
                if content and len(content.strip()) > 0:
                    task = self.quality_validator.validate_content(
                        content, content_type, content_bundle.original_url
                    )
                    validation_tasks.append((content_type, task))
            
            # Execute validations in parallel
            results = await asyncio.gather(
                *[task for _, task in validation_tasks], 
                return_exceptions=True
            )
            
            # Process results
            total_score = 0
            valid_scores = 0
            requires_review = False
            auto_approved = True
            
            for i, (content_type, _) in enumerate(validation_tasks):
                result = results[i]
                if isinstance(result, Exception):
                    logger.error(f"Quality validation failed for {content_type}: {result}")
                    quality_scores[content_type] = None
                    auto_approved = False
                else:
                    quality_scores[content_type] = result
                    total_score += result.overall_score
                    valid_scores += 1
                    
                    if result.requires_review:
                        requires_review = True
                    if not result.auto_approve:
                        auto_approved = False
            
            # Calculate overall quality score
            overall_score = total_score / max(valid_scores, 1) if valid_scores > 0 else 0
            
            # Update content bundle with quality results
            content_bundle.quality_scores = quality_scores
            content_bundle.overall_quality_score = round(overall_score, 1)
            content_bundle.requires_review = requires_review or overall_score < 6.0
            content_bundle.auto_approved = auto_approved and overall_score >= 8.0
            
            logger.info(f"Quality validation completed. Overall score: {overall_score:.1f}/10")
            logger.info(f"Auto-approved: {content_bundle.auto_approved}, Requires review: {content_bundle.requires_review}")
            
            return content_bundle
            
        except Exception as e:
            logger.error(f"Error during quality validation: {e}")
            # Return bundle with default quality flags on error
            content_bundle.requires_review = True
            content_bundle.auto_approved = False
            return content_bundle
    
    async def store_content(self, content_bundle: ContentBundle) -> Dict[str, str]:
        """Store generated content in Google Docs and Notion."""
        logger.info("Storing content in Google Docs and Notion")
        
        storage_results = {}
        
        # Store in Google Docs
        try:
            google_docs_urls = await self._store_in_google_docs(content_bundle)
            storage_results["google_docs"] = google_docs_urls
        except Exception as e:
            logger.error(f"Failed to store in Google Docs: {e}")
            storage_results["google_docs"] = {"error": str(e)}
        
        # Store in Notion
        try:
            notion_page_id = await self._store_in_notion(content_bundle)
            storage_results["notion"] = notion_page_id
        except Exception as e:
            logger.error(f"Failed to store in Notion: {e}")
            storage_results["notion"] = {"error": str(e)}
        
        return storage_results
    
    async def _store_in_google_docs(self, content_bundle: ContentBundle) -> Dict[str, str]:
        """Store content in Google Docs."""
        # This would require Google Docs API setup
        # For now, return placeholder URLs
        logger.info("Storing content in Google Docs (placeholder implementation)")
        
        return {
            "blog_post": f"https://docs.google.com/document/d/placeholder-blog-{content_bundle.timestamp.strftime('%Y%m%d%H%M%S')}",
            "twitter_thread": f"https://docs.google.com/document/d/placeholder-twitter-{content_bundle.timestamp.strftime('%Y%m%d%H%M%S')}",
            "newsletter": f"https://docs.google.com/document/d/placeholder-newsletter-{content_bundle.timestamp.strftime('%Y%m%d%H%M%S')}",
            "seo_summary": f"https://docs.google.com/document/d/placeholder-seo-{content_bundle.timestamp.strftime('%Y%m%d%H%M%S')}"
        }
    
    async def _store_in_notion(self, content_bundle: ContentBundle) -> str:
        """Store content metadata in Notion database."""
        logger.info("Storing content metadata in Notion")
        
        try:
            page_data = {
                "parent": {"database_id": self.config["notion"]["database_id"]},
                "properties": {
                    "Title": {
                        "title": [{"text": {"content": content_bundle.title}}]
                    },
                    "URL": {
                        "url": content_bundle.original_url
                    },
                    "Status": {
                        "select": {"name": "Generated"}
                    },
                    "Created": {
                        "date": {"start": content_bundle.timestamp.isoformat()}
                    },
                    "Content Types": {
                        "multi_select": [
                            {"name": "Blog Post"},
                            {"name": "Twitter Thread"},
                            {"name": "Newsletter"},
                            {"name": "SEO Summary"}
                        ]
                    }
                }
            }
            
            response = await asyncio.to_thread(
                self.notion_client.pages.create,
                **page_data
            )
            
            page_id = response["id"]
            logger.info(f"Created Notion page: {page_id}")
            return page_id
            
        except Exception as e:
            logger.error(f"Error creating Notion page: {e}")
            raise
    
    async def send_notification(self, content_bundle: ContentBundle, storage_results: Dict[str, Any]) -> bool:
        """Send Slack notification when content is ready."""
        logger.info("Sending Slack notification")
        
        try:
            # Determine notification emoji and status based on quality
            if content_bundle.auto_approved:
                status_emoji = "✅"
                status_text = "Auto-approved"
            elif content_bundle.requires_review:
                status_emoji = "⚠️"
                status_text = "Requires review"
            else:
                status_emoji = "🚀"
                status_text = "Ready"
            
            quality_info = ""
            if content_bundle.overall_quality_score:
                quality_info = f" (Quality: {content_bundle.overall_quality_score}/10)"
            
            message = {
                "text": f"{status_emoji} Content bundle {status_text.lower()} for: {content_bundle.title}{quality_info}",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"Content Machine - Bundle {status_text}! {status_emoji}"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Title:* {content_bundle.title}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Source:* <{content_bundle.original_url}|View Original>"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Generated:* {content_bundle.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": "*Content Types:* Blog Post, Twitter Thread, Newsletter, SEO Summary"
                            }
                        ]
                    }
                ]
            }
            
            # Add quality information section
            if content_bundle.overall_quality_score:
                quality_section = {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Overall Quality:* {content_bundle.overall_quality_score}/10"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Status:* {status_text}"
                        }
                    ]
                }
                
                # Add individual quality scores if available
                if content_bundle.quality_scores:
                    quality_details = []
                    for content_type, score in content_bundle.quality_scores.items():
                        if score:
                            quality_details.append(f"• {content_type.replace('_', ' ').title()}: {score.overall_score}/10")
                    
                    if quality_details:
                        quality_section["fields"].append({
                            "type": "mrkdwn",
                            "text": f"*Quality Breakdown:*\n" + "\n".join(quality_details[:4])  # Limit to 4 items
                        })
                
                message["blocks"].append(quality_section)
            
            if isinstance(storage_results.get("google_docs"), dict) and "error" not in storage_results["google_docs"]:
                docs_links = storage_results["google_docs"]
                links_text = "\n".join([f"• <{url}|{content_type.replace('_', ' ').title()}>" 
                                      for content_type, url in docs_links.items()])
                message["blocks"].append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Google Docs:*\n{links_text}"
                    }
                })
            
            response = await asyncio.to_thread(
                self.slack_client.send,
                **message
            )
            
            logger.info("Slack notification sent successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False
    
    async def process_url(self, url: str) -> Dict[str, Any]:
        """Main workflow: process a single URL through the entire pipeline."""
        logger.info(f"Starting content machine workflow for: {url}")
        
        try:
            # Step 1: Scrape content
            scraped_data = await self.scrape_content(url)
            
            # Step 2: Generate content
            content_bundle = await self.generate_content(scraped_data)
            
            # Step 3: Validate content quality
            content_bundle = await self.validate_content_quality(content_bundle)
            
            # Step 4: Store content (only if quality is acceptable)
            if content_bundle.overall_quality_score and content_bundle.overall_quality_score >= 4.0:
                storage_results = await self.store_content(content_bundle)
            else:
                logger.warning(f"Content quality too low ({content_bundle.overall_quality_score}/10). Skipping storage.")
                storage_results = {"skipped": "Quality score below threshold"}
            
            # Step 5: Send notification
            notification_sent = await self.send_notification(content_bundle, storage_results)
            
            result = {
                "success": True,
                "url": url,
                "title": content_bundle.title,
                "timestamp": content_bundle.timestamp.isoformat(),
                "storage_results": storage_results,
                "notification_sent": notification_sent,
                "content_preview": {
                    "blog_post_length": len(content_bundle.blog_post),
                    "twitter_thread_tweets": len(content_bundle.twitter_thread.split("Tweet")),
                    "newsletter_length": len(content_bundle.newsletter_summary),
                    "seo_keywords": content_bundle.seo_summary[:200] + "..." if len(content_bundle.seo_summary) > 200 else content_bundle.seo_summary
                }
            }
            
            logger.info(f"Workflow completed successfully for: {url}")
            return result
            
        except Exception as e:
            logger.error(f"Workflow failed for {url}: {e}")
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


async def main():
    """Main entry point for testing the workflow."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python content_machine.py <url>")
        sys.exit(1)
    
    url = sys.argv[1]
    
    try:
        machine = ContentMachine()
        result = await machine.process_url(url)
        
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
