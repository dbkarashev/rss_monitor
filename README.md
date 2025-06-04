# RSS News Monitor

RSS feed monitoring service with web interface for managing feeds and tracking keyword-based news articles.

## Features

- Parse multiple RSS feeds with configurable sources
- Add/remove RSS feeds via web interface
- Activate/deactivate feeds without deletion
- Search for technology-related keywords in articles
- Automatic background monitoring every 15 minutes
- Web interface with full feed management
- Display matching articles with source attribution

## Installation

```bash
pip3 install -r requirements.txt
```

## Usage

```bash
python3 rss_monitor.py
```

Open http://127.0.0.1:5000 in your browser to:
- View found articles by source
- Manage RSS feeds (add, activate, deactivate)
- Start/stop automatic monitoring
- Manually trigger RSS scans

## Default Configuration

**RSS Sources:**
- BBC News
- CNN  
- Reuters

**Keywords:**
- technology, AI, Python, programming, tech, artificial, digital, software

## Requirements

- Python 3.6+