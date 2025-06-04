# RSS News Monitor

RSS feed parser with automatic monitoring and web interface for keyword detection in news articles.

## Features

- Parse RSS feeds from BBC News and CNN
- Search for technology-related keywords in articles
- Automatic background monitoring every 10 minutes
- Web interface with start/stop controls
- Display matching articles with titles, links, and matched keywords

## Installation

```bash
pip3 install -r requirements.txt
```

## Usage

```bash
python3 rss_monitor.py
```

Open http://127.0.0.1:5000 in your browser to:
- View found articles
- Start/stop automatic monitoring
- Manually trigger RSS scans

The script will scan RSS feeds and display articles containing keywords like:
- technology
- AI
- Python
- programming

## Requirements

- Python 3.6+