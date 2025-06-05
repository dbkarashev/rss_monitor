# RSS News Monitor

Production-ready RSS feed monitoring service with automated keyword tracking, web management interface, and REST API endpoints.

## Overview

RSS News Monitor continuously scans multiple RSS feeds, identifies articles matching specified keywords, and provides both web and programmatic access to discovered content. Built for reliability with comprehensive logging and error handling.

## Features

### Core Functionality
- **Automated RSS Monitoring**: Continuous background scanning every 30 minutes
- **Keyword Detection**: Word-boundary matching for precise results
- **Content Cleaning**: Automatic HTML tag removal from article descriptions
- **Duplicate Prevention**: Link-based deduplication of articles

### Management Interface
- **Web Dashboard**: Complete feed and keyword management via browser
- **RSS Source Control**: Add, activate, deactivate, and remove RSS feeds
- **Keyword Management**: Dynamic keyword addition and status control
- **Real-time Monitoring**: Start/stop monitoring with live status display

### API Access
- **REST Endpoints**: Full programmatic access to all data and functions
- **JSON Responses**: Structured data for integration with external systems
- **Status Monitoring**: Real-time system health and statistics

### Data & Logging
- **SQLite Database**: Persistent storage with automatic schema management
- **Comprehensive Logging**: File and console logging with detailed operation tracking
- **Error Handling**: Robust exception management with continued operation

## Quick Start

### Installation
```bash
git clone https://github.com/dbkarashev/rss_monitor.git
cd rss_monitor
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

### Basic Usage
```bash
python3 rss_monitor.py
```

**Access Points:**
- **Web Interface**: http://localhost:5001
- **API Base URL**: http://localhost:5001/api

## Web Interface

### Dashboard Features
- **Article Feed**: View discovered articles with source attribution and keyword highlighting
- **Monitoring Controls**: Start/stop automated scanning with status indicators
- **RSS Management**: Add new feeds, toggle active status, remove sources
- **Keyword Configuration**: Add search terms, enable/disable specific keywords

### Default Configuration
The system initializes with curated RSS sources and keywords:

**RSS Sources:**
- TechCrunch (Technology News)
- The Verge (Tech & Culture)
- Ars Technica (Science & Technology)
- Hacker News (Developer Community)
- VentureBeat (AI & Startup News)

**Keywords:**
- AI, artificial intelligence, technology, tech, programming, Python, software, digital

## API Reference

### Endpoints

| Method | Endpoint | Description | Response |
|--------|----------|-------------|----------|
| `GET` | `/api/news` | Retrieve found articles | Array of article objects |
| `GET` | `/api/feeds` | List RSS feed sources | Array of feed objects |
| `GET` | `/api/keywords` | List search keywords | Array of keyword objects |
| `GET` | `/api/status` | System status and stats | Status object |

### API Examples

**Get Latest Articles:**
```bash
curl http://localhost:5001/api/news
```

**Response:**
```json
[
  {
    "title": "AI Breakthrough in Machine Learning",
    "description": "Researchers announce significant advances...",
    "link": "https://example.com/article",
    "feed_name": "TechCrunch",
    "keywords_matched": "AI, technology",
    "published_date": "2025-06-05T10:30:00",
    "found_at": "2025-06-05T10:35:22"
  }
]
```

**System Status:**
```bash
curl http://localhost:5001/api/status
```

**Response:**
```json
{
  "monitoring": true,
  "active_feeds": 4,
  "active_keywords": 8,
  "total_articles": 127
}
```

## Configuration

### Adding RSS Feeds
**Via Web Interface:** Navigate to RSS Sources section, enter feed name and URL

**Supported Formats:**
- RSS 2.0
- Atom 1.0
- RSS 1.0/RDF

### Keyword Management
**Word Boundaries:** Uses word-boundary matching to prevent false positives
**Case Insensitive:** All keyword matching is performed case-insensitively
**Phrase Support:** Multi-word phrases supported (e.g., "machine learning")
**Unicode Support:** Full UTF-8 support for international keywords

## File Structure

```
rss-monitor/
├── rss_monitor.py          # Main application
├── requirements.txt        # Python dependencies
├── README.md               # Documentation
├── LICENSE                 # MIT license
├── .gitignore              # Git exclusions
├── rss_monitor.db          # SQLite database (auto-created)
└── rss_monitor.log         # Application logs (auto-created)
```

## Database Schema

**Tables:**
- `rss_feeds`: RSS source management
- `keywords`: Search term configuration  
- `found_news`: Discovered articles with metadata

## Logging

All operations are logged to both console and `rss_monitor.log`:

- Feed parsing operations and results
- Article discovery with matched keywords
- Configuration changes (feeds/keywords)
- Error conditions and recovery actions
- System startup and shutdown events

**Log Levels:** INFO for normal operations, WARNING for recoverable issues, ERROR for critical problems

## Requirements

- **Python**: 3.6 or higher
- **Dependencies**: Flask, feedparser (see requirements.txt)
- **Storage**: ~50MB for database and logs
- **Network**: Internet access for RSS feed retrieval

## Production Deployment

### Recommendations
- Use WSGI server (gunicorn, uWSGI) instead of built-in Flask server
- Configure reverse proxy (nginx) for external access
- Set up log rotation for rss_monitor.log
- Monitor disk space for database growth
- Configure firewall rules for port access

### Environment Variables
```bash
export RSS_MONITOR_PORT=5001
export RSS_MONITOR_HOST=0.0.0.0
export RSS_MONITOR_DB_PATH=/var/lib/rss_monitor/rss_monitor.db
```

## Troubleshooting

**Port 5001 in use:**
```bash
lsof -ti:5001 | xargs kill -9
```

**Database corruption:**
```bash
rm rss_monitor.db
python3 rss_monitor.py  # Will recreate with default data
```

**No articles found:**
- Verify RSS feeds are accessible
- Check keyword configuration
- Review logs for parsing errors

## License

MIT License - see LICENSE file for details

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request