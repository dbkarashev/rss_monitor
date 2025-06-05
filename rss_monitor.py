#!/usr/bin/env python3
import sqlite3
import feedparser
import threading
import time
import logging
import re
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, redirect, url_for

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rss_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RSSMonitor:
    def __init__(self, db_path='rss_monitor.db'):
        self.db_path = db_path
        self.init_db()
        self.monitoring = False
        self.monitor_thread = None
        
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rss_feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL UNIQUE,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS found_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                link TEXT NOT NULL UNIQUE,
                feed_name TEXT,
                keywords_matched TEXT,
                published_date TIMESTAMP,
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('SELECT COUNT(*) FROM rss_feeds')
        if cursor.fetchone()[0] == 0:
            test_feeds = [
                ('TechCrunch', 'https://techcrunch.com/feed/'),
                ('The Verge', 'https://www.theverge.com/rss/index.xml'),
                ('Ars Technica', 'https://feeds.arstechnica.com/arstechnica/index'),
                ('Hacker News', 'https://hnrss.org/frontpage'),
                ('VentureBeat', 'https://venturebeat.com/feed/')
            ]
            cursor.executemany('INSERT INTO rss_feeds (name, url) VALUES (?, ?)', test_feeds)
            
        cursor.execute('SELECT COUNT(*) FROM keywords')
        if cursor.fetchone()[0] == 0:
            test_keywords = ['technology', 'artificial intelligence', 'Python', 'programming', 'tech', 'AI', 'software', 'digital']
            cursor.executemany('INSERT INTO keywords (keyword) VALUES (?)', [(k,) for k in test_keywords])
        
        conn.commit()
        conn.close()
        logger.info("Database initialized")
        
    def get_active_feeds(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT name, url FROM rss_feeds WHERE active = 1')
        feeds = cursor.fetchall()
        conn.close()
        return feeds
        
    def get_active_keywords(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT keyword FROM keywords WHERE active = 1')
        keywords = [row[0].lower() for row in cursor.fetchall()]
        conn.close()
        return keywords
        
    def clean_html(self, text):
        if not text:
            return ""
        # Remove HTML tags
        clean = re.sub('<.*?>', '', text)
        # Remove extra whitespace
        clean = ' '.join(clean.split())
        return clean
        
    def check_keywords_in_text(self, text, keywords):
        if not text:
            return []
        
        found_keywords = []
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text.lower()):
                found_keywords.append(keyword)
        return found_keywords
        
    def parse_feed(self, feed_name, feed_url, keywords):
        try:
            logger.info(f"Parsing feed: {feed_name}")
            feed = feedparser.parse(feed_url)
            
            if feed.bozo:
                logger.warning(f"Feed parsing issues for {feed_name}: {feed.bozo_exception}")
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            new_articles = 0
            for entry in feed.entries[:20]:
                title = getattr(entry, 'title', '')
                description = getattr(entry, 'description', '') or getattr(entry, 'summary', '')
                link = getattr(entry, 'link', '')
                
                # Clean HTML from description
                description = self.clean_html(description)
                
                if not title or not link:
                    continue
                
                cursor.execute('SELECT id FROM found_news WHERE link = ?', (link,))
                if cursor.fetchone():
                    continue
                    
                text_to_search = f"{title} {description}"
                matched_keywords = self.check_keywords_in_text(text_to_search, keywords)
                
                if matched_keywords:
                    published_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            published_date = datetime(*entry.published_parsed[:6])
                        except:
                            pass
                    
                    cursor.execute('''
                        INSERT INTO found_news 
                        (title, description, link, feed_name, keywords_matched, published_date)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        title, 
                        description[:500], 
                        link, 
                        feed_name, 
                        ', '.join(matched_keywords),
                        published_date
                    ))
                    new_articles += 1
                    logger.info(f"Found article: {title[:50]}... (keywords: {', '.join(matched_keywords)})")
            
            conn.commit()
            conn.close()
            
            if new_articles > 0:
                logger.info(f"Added {new_articles} new articles from {feed_name}")
            
        except Exception as e:
            logger.error(f"Error parsing feed {feed_name}: {str(e)}")
            
    def monitor_feeds(self):
        logger.info("RSS monitoring started")
        
        while self.monitoring:
            try:
                feeds = self.get_active_feeds()
                keywords = self.get_active_keywords()
                
                if not feeds:
                    logger.warning("No active RSS feeds")
                elif not keywords:
                    logger.warning("No active keywords")
                else:
                    logger.info(f"Monitoring {len(feeds)} feeds with {len(keywords)} keywords")
                    
                    for feed_name, feed_url in feeds:
                        if not self.monitoring:
                            break
                        self.parse_feed(feed_name, feed_url, keywords)
                        time.sleep(2)
                
                for _ in range(1800):  # 30 minutes
                    if not self.monitoring:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(60)
                
        logger.info("RSS monitoring stopped")
        
    def start_monitoring(self):
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_feeds)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            logger.info("Monitoring started")
            
    def stop_monitoring(self):
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Monitoring stopped")

monitor = RSSMonitor()
app = Flask(__name__)

MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>RSS News Monitor</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f0f0f0; padding: 20px; margin-bottom: 20px; }
        .section { margin-bottom: 30px; }
        .news-item { border: 1px solid #ddd; padding: 15px; margin: 10px 0; }
        .news-title { font-weight: bold; color: #0066cc; }
        .news-meta { color: #666; font-size: 0.9em; margin: 5px 0; }
        .keywords { background: #fff3cd; padding: 2px 6px; border-radius: 3px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .btn { padding: 5px 10px; margin: 2px; text-decoration: none; background: #007bff; color: white; border-radius: 3px; }
        .btn-danger { background: #dc3545; }
        .btn-success { background: #28a745; }
        .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
        .status-active { background: #d4edda; color: #155724; }
        .status-inactive { background: #f8d7da; color: #721c24; }
        form { margin: 10px 0; }
        input, textarea { padding: 5px; margin: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>RSS News Monitor</h1>
        <div class="status {{ 'status-active' if monitoring else 'status-inactive' }}">
            Monitoring Status: {{ 'Active' if monitoring else 'Inactive' }}
        </div>
        <a href="/start" class="btn btn-success">Start</a>
        <a href="/stop" class="btn btn-danger">Stop</a>
        <a href="/" class="btn">Refresh</a>
    </div>

    <div class="section">
        <h2>Found Articles ({{ news|length }})</h2>
        {% for item in news %}
        <div class="news-item">
            <div class="news-title">{{ item[1] }}</div>
            <div class="news-meta">
                Source: {{ item[4] }} | 
                Keywords: <span class="keywords">{{ item[5] }}</span> | 
                Found: {{ item[7] }}
            </div>
            <div>{{ item[2] }}</div>
            <div><a href="{{ item[3] }}" target="_blank">Read more</a></div>
        </div>
        {% endfor %}
    </div>

    <div class="section">
        <h2>RSS Sources</h2>
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
                <td>{{ feed[2] }}</td>
                <td>{{ 'Active' if feed[3] else 'Inactive' }}</td>
                <td>
                    <a href="/toggle_feed/{{ feed[0] }}" class="btn">
                        {{ 'Deactivate' if feed[3] else 'Activate' }}
                    </a>
                    <a href="/delete_feed/{{ feed[0] }}" class="btn btn-danger" 
                       onclick="return confirm('Delete?')">Delete</a>
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>

    <div class="section">
        <h2>Keywords</h2>
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
                    <a href="/delete_keyword/{{ keyword[0] }}" class="btn btn-danger" 
                       onclick="return confirm('Delete?')">Delete</a>
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    conn = sqlite3.connect(monitor.db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM found_news ORDER BY found_at DESC LIMIT 50')
    news = cursor.fetchall()
    
    cursor.execute('SELECT * FROM rss_feeds ORDER BY name')
    feeds = cursor.fetchall()
    
    cursor.execute('SELECT * FROM keywords ORDER BY keyword')
    keywords = cursor.fetchall()
    
    conn.close()
    
    return render_template_string(MAIN_TEMPLATE, 
                                news=news, 
                                feeds=feeds, 
                                keywords=keywords,
                                monitoring=monitor.monitoring)

@app.route('/start')
def start_monitoring():
    monitor.start_monitoring()
    return redirect(url_for('index'))

@app.route('/stop')
def stop_monitoring():
    monitor.stop_monitoring()
    return redirect(url_for('index'))

@app.route('/add_feed', methods=['POST'])
def add_feed():
    name = request.form.get('name')
    url = request.form.get('url')
    
    if name and url:
        conn = sqlite3.connect(monitor.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO rss_feeds (name, url) VALUES (?, ?)', (name, url))
            conn.commit()
            logger.info(f"Added RSS feed: {name}")
        except sqlite3.IntegrityError:
            logger.warning(f"RSS feed already exists: {url}")
        conn.close()
    
    return redirect(url_for('index'))

@app.route('/toggle_feed/<int:feed_id>')
def toggle_feed(feed_id):
    conn = sqlite3.connect(monitor.db_path)
    cursor = conn.cursor()
    cursor.execute('UPDATE rss_feeds SET active = 1 - active WHERE id = ?', (feed_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete_feed/<int:feed_id>')
def delete_feed(feed_id):
    conn = sqlite3.connect(monitor.db_path)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM rss_feeds WHERE id = ?', (feed_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/add_keyword', methods=['POST'])
def add_keyword():
    keyword = request.form.get('keyword')
    
    if keyword:
        conn = sqlite3.connect(monitor.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO keywords (keyword) VALUES (?)', (keyword,))
            conn.commit()
            logger.info(f"Added keyword: {keyword}")
        except sqlite3.IntegrityError:
            logger.warning(f"Keyword already exists: {keyword}")
        conn.close()
    
    return redirect(url_for('index'))

@app.route('/toggle_keyword/<int:keyword_id>')
def toggle_keyword(keyword_id):
    conn = sqlite3.connect(monitor.db_path)
    cursor = conn.cursor()
    cursor.execute('UPDATE keywords SET active = 1 - active WHERE id = ?', (keyword_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete_keyword/<int:keyword_id>')
def delete_keyword(keyword_id):
    conn = sqlite3.connect(monitor.db_path)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM keywords WHERE id = ?', (keyword_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/api/news')
def api_news():
    conn = sqlite3.connect(monitor.db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, description, link, feed_name, keywords_matched, published_date, found_at 
        FROM found_news 
        ORDER BY found_at DESC 
        LIMIT 100
    ''')
    news = cursor.fetchall()
    conn.close()
    
    result = []
    for item in news:
        result.append({
            'title': item[0],
            'description': item[1],
            'link': item[2],
            'feed_name': item[3],
            'keywords_matched': item[4],
            'published_date': item[5],
            'found_at': item[6]
        })
    
    return jsonify(result)

@app.route('/api/feeds')
def api_feeds():
    conn = sqlite3.connect(monitor.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, url, active FROM rss_feeds')
    feeds = cursor.fetchall()
    conn.close()
    
    result = []
    for feed in feeds:
        result.append({
            'id': feed[0],
            'name': feed[1],
            'url': feed[2],
            'active': bool(feed[3])
        })
    
    return jsonify(result)

@app.route('/api/keywords')
def api_keywords():
    conn = sqlite3.connect(monitor.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT id, keyword, active FROM keywords')
    keywords = cursor.fetchall()
    conn.close()
    
    result = []
    for keyword in keywords:
        result.append({
            'id': keyword[0],
            'keyword': keyword[1],
            'active': bool(keyword[2])
        })
    
    return jsonify(result)

@app.route('/api/status')
def api_status():
    conn = sqlite3.connect(monitor.db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM rss_feeds WHERE active = 1')
    active_feeds = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM keywords WHERE active = 1')
    active_keywords = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM found_news')
    total_articles = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'monitoring': monitor.monitoring,
        'active_feeds': active_feeds,
        'active_keywords': active_keywords,
        'total_articles': total_articles
    })

if __name__ == '__main__':
    print("RSS News Monitor Service")
    print("Web interface: http://localhost:5001")
    print("API endpoints:")
    print("  GET /api/news - list of found news")
    print("  GET /api/feeds - list of RSS feeds")
    print("  GET /api/keywords - list of keywords")
    print("  GET /api/status - monitoring status")
    
    monitor.start_monitoring()
    
    try:
        app.run(host='0.0.0.0', port=5001, debug=False)
    except KeyboardInterrupt:
        print("\nStopping service...")
        monitor.stop_monitoring()
        print("Service stopped")