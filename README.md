# RSS News Monitor

Complete RSS feed monitoring service with web interface for managing feeds, keywords, and tracking news articles.

## Features

- Parse multiple RSS feeds with configurable sources
- Add/remove RSS feeds via web interface
- Add/remove keywords via web interface
- Activate/deactivate feeds and keywords without deletion
- Search articles using custom keyword combinations
- Automatic background monitoring every 20 minutes
- Web interface with full feed and keyword management
- Display matching articles with source attribution and matched keywords

## Installation

```bash
pip3 install -r requirements.txt
```

## Usage

```bash
python3 rss_monitor.py
```

Open http://127.0.0.1:5000 in your browser to:
- View found articles by source and keywords
- Manage RSS feeds (add, activate, deactivate)
- Manage keywords (add, activate, deactivate)
- Start/stop automatic monitoring
- Manually trigger RSS scans

## Default Configuration

**RSS Sources:**
- BBC News
- CNN  
- Reuters

**Keywords:**
- technology, AI, Python, programming, tech, artificial, digital, software

## Web Interface

The web interface provides complete control over:
- **RSS Feeds Management**: Add new sources, toggle active feeds
- **Keywords Management**: Add custom keywords, enable/disable specific terms
- **Monitoring Control**: Start/stop automatic scanning
- **Article Viewing**: Browse found articles with keyword highlighting

## Requirements

- Python 3.6+