#!/usr/bin/env python3
"""
Webhook Handler for n8n Integration
Handles incoming webhook requests and triggers the content machine workflow.
"""

import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

from flask import Flask, request, jsonify
from content_machine import ContentMachine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


class WebhookHandler:
    """Handles webhook requests and orchestrates content generation."""
    
    def __init__(self):
        """Initialize the webhook handler."""
        self.content_machine = ContentMachine()
        logger.info("Webhook handler initialized")
    
    async def process_webhook_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming webhook request."""
        try:
            # Extract URL from request
            url = data.get('url')
            if not url:
                return {
                    "success": False,
                    "error": "Missing 'url' parameter in request",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Validate URL format
            if not (url.startswith('http://') or url.startswith('https://')):
                return {
                    "success": False,
                    "error": "Invalid URL format. Must start with http:// or https://",
                    "timestamp": datetime.now().isoformat()
                }
            
            logger.info(f"Processing webhook request for URL: {url}")
            
            # Process the URL through content machine
            result = await self.content_machine.process_url(url)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing webhook request: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Global webhook handler instance
webhook_handler = WebhookHandler()


@app.route('/webhook/content-machine', methods=['POST'])
def handle_webhook():
    """Handle incoming webhook requests from n8n."""
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No JSON data provided",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        # Process the request asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                webhook_handler.process_webhook_request(data)
            )
        finally:
            loop.close()
        
        # Return appropriate HTTP status code
        status_code = 200 if result.get("success") else 400
        
        return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"Webhook handler error: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "content-machine-webhook",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/test', methods=['POST'])
def test_endpoint():
    """Test endpoint for manual testing."""
    try:
        data = request.get_json() or {}
        test_url = data.get('url', 'https://example.com')
        
        return jsonify({
            "message": "Test endpoint called",
            "received_url": test_url,
            "timestamp": datetime.now().isoformat(),
            "note": "Use /webhook/content-machine for actual processing"
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Content Machine Webhook Handler')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    logger.info(f"Starting webhook handler on {args.host}:{args.port}")
    
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )
