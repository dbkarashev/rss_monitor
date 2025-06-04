#!/usr/bin/env python3
import feedparser
import sqlite3
import time
import threading
from datetime import datetime
from flask import Flask, render_template_string, request, redirect

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
            CREATE TABLE IF NOT EXISTS rss_feeds (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                active INTEGER DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY,
                keyword TEXT NOT NULL UNIQUE,
                active INTEGER DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS found_news (
                id INTEGER PRIMARY KEY,
                title TEXT,
                description TEXT,
                link TEXT UNIQUE,
                feed_name TEXT,
                keywords TEXT,
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add default feeds
        default_feeds = [
            ('BBC News', 'http://feeds.bbci.co.uk/news/rss.xml'),
            ('CNN', 'http://rss.cnn.com/rss/edition.rss'),
            ('Reuters', 'http://feeds.reuters.com/reuters/topNews')
        ]
        
        for name, url in default_feeds:
            cursor.execute('INSERT OR IGNORE INTO rss_feeds (name, url) VALUES (?, ?)', (name, url))
        
        # Add default keywords
        default_keywords = ['technology', 'AI', 'Python', 'programming', 'tech', 'artificial', 'digital', 'software']
        
        for keyword in default_keywords:
            cursor.execute('INSERT OR IGNORE INTO keywords (keyword) VALUES (?)', (keyword,))
        
        conn.commit()
        conn.close()
    
    def get_active_feeds(self):
        conn = sqlite3.connect('news.db')
        cursor = conn.cursor()
        cursor.execute('SELECT name, url FROM rss_feeds WHERE active = 1')
        feeds = cursor.fetchall()
        conn.close()
        return feeds
    
    def get_all_feeds(self):
        conn = sqlite3.connect('news.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM rss_feeds')
        feeds = cursor.fetchall()
        conn.close()
        return feeds
    
    def get_active_keywords(self):
        conn = sqlite3.connect('news.db')
        cursor = conn.cursor()
        cursor.execute('SELECT keyword FROM keywords WHERE active = 1')
        keywords = [row[0] for row in cursor.fetchall()]
        conn.close()
        return keywords
    
    def get_all_keywords(self):
        conn = sqlite3.connect('news.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM keywords')
        keywords = cursor.fetchall()
        conn.close()
        return keywords
    
    def add_feed(self, name, url):
        conn = sqlite3.connect('news.db')
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO rss_feeds (name, url) VALUES (?, ?)', (name, url))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def add_keyword(self, keyword):
        conn = sqlite3.connect('news.db')
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO keywords (keyword) VALUES (?)', (keyword,))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def toggle_feed(self, feed_id):
        conn = sqlite3.connect('news.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE rss_feeds SET active = 1 - active WHERE id = ?', (feed_id,))
        conn.commit()
        conn.close()
    
    def toggle_keyword(self, keyword_id):
        conn = sqlite3.connect('news.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE keywords SET active = 1 - active WHERE id = ?', (keyword_id,))
        conn.commit()
        conn.close()
    
    def save_article(self, article, keywords, feed_name):
        conn = sqlite3.connect('news.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO found_news (title, description, link, feed_name, keywords)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                article['title'],
                article['description'][:300],
                article['link'],
                feed_name,
                ', '.join(keywords)
            ))
            conn.commit()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Found: {article['title'][:40]}...")
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def scan_feeds(self):
        feeds = self.get_active_feeds()
        keywords = self.get_active_keywords()
        
        if not keywords:
            print("No active keywords found")
            return
        
        for feed_name, feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Scanning: {feed_name}")
                
                for entry in feed.entries[:8]:
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
                        self.save_article(article, matched_keywords, feed_name)
                
                time.sleep(2)
            except Exception as e:
                print(f"Error scanning {feed_name}: {e}")
    
    def monitor_loop(self):
        while self.monitoring:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting RSS scan cycle...")
            self.scan_feeds()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Cycle complete. Waiting 20 minutes...")
            
            for _ in range(1200):  # 20 minutes
                if not self.monitoring:
                    break
                time.sleep(1)
    
    def start_monitoring(self):
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
    
    def stop_monitoring(self):
        self.monitoring = False
    
    def get_news(self):
        conn = sqlite3.connect('news.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM found_news ORDER BY found_at DESC LIMIT 25')
        news = cursor.fetchall()
        conn.close()
        return news

monitor = RSSMonitor()

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>RSS Monitor - Full Management</title>
    <style>
        body { font-family: Arial; margin: 20px; }
        .header { background: #f0f0f0; padding: 15px; margin-bottom: 20px; }
        .status { font-weight: bold; color: {{ 'green' if monitoring else 'red' }}; }
        .section { margin-bottom: 30px; }
        .article { border: 1px solid #ccc; padding: 15px; margin: 10px 0; }
        .title { font-weight: bold; color: #0066cc; }
        .meta { color: #666; font-size: 0.9em; }
        .keywords { background: #ffeb3b; padding: 2px 4px; }
        .btn { padding: 5px 10px; margin: 2px; text-decoration: none; 
               background: #007bff; color: white; border-radius: 3px; display: inline-block; }
        .btn-danger { background: #dc3545; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        input { padding: 5px; margin: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>RSS Monitor - Full Management</h1>
        <div class="status">Status: {{ 'Running' if monitoring else 'Stopped' }}</div>
        <a href="/start" class="btn">Start</a>
        <a href="/stop" class="btn">Stop</a>
        <a href="/scan" class="btn">Manual Scan</a>
        <a href="/" class="btn">Refresh</a>
    </div>

    <div class="section">
        <h2>RSS Feeds ({{ feeds|length }})</h2>
        <form method="POST" action="/add_feed">
            <input type="text" name="name" placeholder="Feed Name" required>
            <input type="url" name="url" placeholder="RSS URL" required>
            <button type="submit" class="btn">Add Feed</button>
        </form>
        
        <table>
            <tr><th>Name</th><th>URL</th><th>Status</th><th>Actions</th></tr>
            {% for feed in feeds %}
            <tr>
                <td>{{ feed[1] }}</td>
                <td>{{ feed[2][:50] }}...</td>
                <td>{{ 'Active' if feed[3] else 'Inactive' }}</td>
                <td>
                    <a href="/toggle_feed/{{ feed[0] }}" class="btn">
                        {{ 'Deactivate' if feed[3] else 'Activate' }}
                    </a>
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>

    <div class="section">
        <h2>Keywords ({{ keywords|length }})</h2>
        <form method="POST" action="/add_keyword">
            <input type="text" name="keyword" placeholder="Keyword" required>
            <button type="submit" class="btn">Add Keyword</button>
        </form>
        
        <table>
            <tr><th>Keyword</th><th>Status</th><th>Actions</th></tr>
            {% for keyword in keywords %}
            <tr>
                <td>{{ keyword[1] }}</td>
                <td>{{ 'Active' if keyword[2] else 'Inactive' }}</td>
                <td>
                    <a href="/toggle_keyword/{{ keyword[0] }}" class="btn">
                        {{ 'Deactivate' if keyword[2] else 'Activate' }}
                    </a>
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>
    
    <div class="section">
        <h2>Found Articles ({{ articles|length }})</h2>
        {% for article in articles %}
        <div class="article">
            <div class="title">{{ article[1] }}</div>
            <div class="meta">
                Source: {{ article[4] }} | 
                Keywords: <span class="keywords">{{ article[5] }}</span> | 
                Found: {{ article[6] }}
            </div>
            <div>{{ article[2] }}</div>
            <div><a href="{{ article[3] }}" target="_blank">Read more</a></div>
        </div>
        {% endfor %}
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    articles = monitor.get_news()
    feeds = monitor.get_all_feeds()
    keywords = monitor.get_all_keywords()
    return render_template_string(HTML_TEMPLATE, 
                                articles=articles, 
                                feeds=feeds, 
                                keywords=keywords,
                                monitoring=monitor.monitoring)

@app.route('/start')
def start():
    monitor.start_monitoring()
    return redirect('/')

@app.route('/stop')
def stop():
    monitor.stop_monitoring()
    return redirect('/')

@app.route('/scan')
def scan():
    monitor.scan_feeds()
    return redirect('/')

@app.route('/add_feed', methods=['POST'])
def add_feed():
    name = request.form.get('name')
    url = request.form.get('url')
    if name and url:
        monitor.add_feed(name, url)
    return redirect('/')

@app.route('/add_keyword', methods=['POST'])
def add_keyword():
    keyword = request.form.get('keyword')
    if keyword:
        monitor.add_keyword(keyword)
    return redirect('/')

@app.route('/toggle_feed/<int:feed_id>')
def toggle_feed(feed_id):
    monitor.toggle_feed(feed_id)
    return redirect('/')

@app.route('/toggle_keyword/<int:keyword_id>')
def toggle_keyword(keyword_id):
    monitor.toggle_keyword(keyword_id)
    return redirect('/')

if __name__ == '__main__':
    print("RSS Monitor with Keyword Management")
    print("Web interface: http://localhost:5000")
    app.run(debug=False, port=5000)