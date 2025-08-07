# Content Machine Workflow

An automated content creation pipeline using n8n, Firecrawl, and GPT-4 that transforms any URL into multi-platform content.

## Features

- **Automated Web Scraping**: Clean content extraction using Firecrawl
- **Multi-Format Content Generation**: Blog posts, Twitter threads, newsletters, SEO summaries
- **Smart Storage**: Organized content in Google Docs and Notion
- **Real-time Notifications**: Slack alerts when content is ready
- **Scalable Architecture**: Easy to extend with new content formats

## Tech Stack

- **n8n**: Workflow orchestration and automation
- **Firecrawl**: Web scraping and content cleaning
- **OpenAI GPT-4**: Content generation and rewriting
- **Google Docs API**: Document storage and collaboration
- **Notion API**: Database organization and tagging
- **Slack API**: Notifications and alerts

## Project Structure

```
content-machine/
├── workflows/              # n8n workflow definitions
│   ├── main-workflow.json
│   └── webhook-config.json
├── config/                 # Configuration files
│   ├── environment.json
│   ├── prompts.json
│   └── api-keys.template.json
├── scripts/               # Utility scripts
│   ├── setup.py
│   ├── test-workflow.py
│   └── deploy.py
├── templates/             # Content templates
│   ├── blog-template.md
│   ├── twitter-template.md
│   ├── newsletter-template.md
│   └── seo-template.md
├── docs/                  # Documentation
│   ├── setup-guide.md
│   ├── api-reference.md
│   └── troubleshooting.md
└── requirements.txt       # Python dependencies
```

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API Keys**
   ```bash
   cp config/api-keys.template.json config/api-keys.json
   # Edit api-keys.json with your credentials
   ```

3. **Set Up n8n Workflow**
   ```bash
   python scripts/setup.py
   ```

4. **Test the Workflow**
   ```bash
   python scripts/test-workflow.py --url "https://example.com/article"
   ```

## API Requirements

- **OpenAI API Key**: For GPT-4 content generation
- **Firecrawl API Key**: For web scraping and cleaning
- **Google Docs API**: For document storage
- **Notion API Token**: For database organization
- **Slack Webhook URL**: For notifications

## Cost Estimation

- OpenAI API: ~$5-10/month (depending on usage)
- Firecrawl: ~$20/month for 1000 pages
- n8n Cloud: Free tier available, $20/month for pro features
- **Total**: ~$25-50/month for moderate usage

## Usage

Send a POST request to your n8n webhook with:
```json
{
  "url": "https://example.com/article-to-process"
}
```

The system will automatically:
1. Scrape and clean the content
2. Generate 4 content formats
3. Store in Google Docs and Notion
4. Send Slack notification when complete

## Next Steps

After basic setup, we'll implement:
- Content quality validation
- Brand voice consistency
- Content calendar integration
- Analytics tracking
- Error handling and fallbacks
