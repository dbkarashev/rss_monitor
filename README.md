# RSS News Monitor

Complete RSS feed monitoring service with web interface and REST API for managing feeds, keywords, and tracking news articles.

## Features

- Parse multiple RSS feeds with configurable sources
- Add/remove RSS feeds via web interface
- Add/remove keywords via web interface
- Activate/deactivate feeds and keywords without deletion
- Search articles using custom keyword combinations
- Automatic background monitoring every 25 minutes
- Web interface with full feed and keyword management
- **REST API endpoints for programmatic access**
- Display matching articles with source attribution and matched keywords

## Installation

```bash
pip3 install -r requirements.txt
```

## Usage

```bash
python3 rss_monitor.py
```

**Web Interface:** http://127.0.0.1:5000
- View found articles by source and keywords
- Manage RSS feeds (add, activate, deactivate)
- Manage keywords (add, activate, deactivate)
- Start/stop automatic monitoring
- Manually trigger RSS scans

**API Endpoints:** 
- `GET /api/news` - Get found articles in JSON format
- `GET /api/feeds` - Get RSS feeds list with status
- `GET /api/keywords` - Get keywords list with status  
- `GET /api/status` - Get monitoring status and statistics

## API Examples

```bash
# Get latest news articles
curl http://127.0.0.1:5000/api/news

# Get monitoring status
curl http://127.0.0.1:5000/api/status

# Get all RSS feeds
curl http://127.0.0.1:5000/api/feeds
```

## Default Configuration

**RSS Sources:**
- BBC News, CNN, Reuters, TechCrunch

**Keywords:**
- technology, AI, Python, programming, tech, artificial, digital, software, machine learning

## Requirements

- Python 3.6+