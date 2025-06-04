#!/usr/bin/env python3
import feedparser
import sqlite3
import time
import threading
from datetime import datetime
from flask import Flask, render_template_string

app = Flask(__name__)

class RSSMonitor:
    def __init__(self):
        self.monitoring = False
        self.monitor_thread = None
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect('news.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS found_news (
                id INTEGER PRIMARY KEY,
                title TEXT,
                description TEXT,
                link TEXT UNIQUE,
                keywords TEXT,
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_article(self, article, keywords):
        conn = sqlite3.connect('news.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO found_news (title, description, link, keywords)
                VALUES (?, ?, ?, ?)
            ''', (
                article['title'],
                article['description'][:300],
                article['link'],
                ', '.join(keywords)
            ))
            conn.commit()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Saved: {article['title'][:40]}...")
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def scan_feeds(self):
        rss_urls = [
            'http://feeds.bbci.co.uk/news/rss.xml',
            'http://rss.cnn.com/rss/edition.rss',
            'https://rssexport.rbc.ru/rbcnews/news/20/full.rss'
        ]
        
        keywords = ['technology', 'AI', 'Python', 'programming', 'tech', 'artificial', 'digital']
        
        for url in rss_urls:
            try:
                feed = feedparser.parse(url)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Scanning: {url}")
                
                for entry in feed.entries[:10]:
                    article = {
                        'title': entry.title,
                        'link': entry.link,
                        'description': getattr(entry, 'description', '')
                    }
                    
                    text_to_check = f"{article['title']} {article['description']}"
                    matched_keywords = []
                    
                    for keyword in keywords:
                        if keyword.lower() in text_to_check.lower():
                            matched_keywords.append(keyword)
                    
                    if matched_keywords:
                        self.save_article(article, matched_keywords)
                
                time.sleep(2)
            except Exception as e:
                print(f"Error scanning {url}: {e}")
    
    def monitor_loop(self):
        while self.monitoring:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting RSS scan cycle...")
            self.scan_feeds()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Cycle complete. Waiting 10 minutes...")
            
            for _ in range(600):  # 10 minutes
                if not self.monitoring:
                    break
                time.sleep(1)
    
    def start_monitoring(self):
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            print("Monitoring started")
    
    def stop_monitoring(self):
        self.monitoring = False
        print("Monitoring stopped")
    
    def get_news(self):
        conn = sqlite3.connect('news.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM found_news ORDER BY found_at DESC LIMIT 30')
        news = cursor.fetchall()
        conn.close()
        return news

monitor = RSSMonitor()

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>RSS Monitor with Auto-scan</title>
    <style>
        body { font-family: Arial; margin: 20px; }
        .header { background: #f0f0f0; padding: 15px; margin-bottom: 20px; }
        .status { font-weight: bold; color: {{ 'green' if monitoring else 'red' }}; }
        .article { border: 1px solid #ccc; padding: 15px; margin: 10px 0; }
        .title { font-weight: bold; color: #0066cc; }
        .meta { color: #666; font-size: 0.9em; }
        .keywords { background: #ffeb3b; padding: 2px 4px; }
        .btn { padding: 8px 16px; margin: 5px; text-decoration: none; 
               background: #007bff; color: white; border-radius: 4px; }
        .btn:hover { background: #0056b3; }
    </style>
</head>
<body>
    <div class="header">
        <h1>RSS Monitor - Auto Scanning</h1>
        <div class="status">Status: {{ 'Running' if monitoring else 'Stopped' }}</div>
        <a href="/start" class="btn">Start</a>
        <a href="/stop" class="btn">Stop</a>
        <a href="/scan" class="btn">Manual Scan</a>
        <a href="/" class="btn">Refresh</a>
    </div>
    
    <h2>Found Articles ({{ articles|length }})</h2>
    
    {% for article in articles %}
    <div class="article">
        <div class="title">{{ article[1] }}</div>
        <div class="meta">
            Keywords: <span class="keywords">{{ article[4] }}</span> | 
            Found: {{ article[5] }}
        </div>
        <div>{{ article[2] }}</div>
        <div><a href="{{ article[3] }}" target="_blank">Read more</a></div>
    </div>
    {% endfor %}
</body>
</html>
'''

@app.route('/')
def index():
    articles = monitor.get_news()
    return render_template_string(HTML_TEMPLATE, articles=articles, monitoring=monitor.monitoring)

@app.route('/start')
def start():
    monitor.start_monitoring()
    return '<h2>Monitoring started!</h2><a href="/">Back</a>'

@app.route('/stop')
def stop():
    monitor.stop_monitoring()
    return '<h2>Monitoring stopped!</h2><a href="/">Back</a>'

@app.route('/scan')
def scan():
    monitor.scan_feeds()
    return '<h2>Manual scan completed!</h2><a href="/">Back</a>'

if __name__ == '__main__':
    print("RSS Monitor with Auto-scanning")
    print("Web interface: http://localhost:5000")
    monitor.start_monitoring()
    app.run(debug=False, port=5000)