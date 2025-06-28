import sqlite3
import feedparser
import threading
import time
import logging
import re
import validators
from datetime import datetime
from contextlib import contextmanager
from typing import List, Tuple, Optional, Dict, Any
from flask import Flask, render_template_string, request, jsonify, redirect, url_for

class Config:
    DEFAULT_DB_PATH = 'rss_monitor.db'
    DEFAULT_PORT = 5001
    DEFAULT_HOST = '0.0.0.0'
    MAX_ENTRIES_PER_FEED = 20
    MONITORING_INTERVAL_SECONDS = 1800  # 30 minutes
    MAX_DESCRIPTION_LENGTH = 500
    MAX_FEED_NAME_LENGTH = 200
    MAX_KEYWORD_LENGTH = 100
    MAX_URL_LENGTH = 2000
    FEED_REQUEST_DELAY = 2

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rss_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass

class DatabaseManager:
    """Database management with proper connection handling"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """Context manager for safe database operations"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            conn.execute('PRAGMA foreign_keys = ON')
            yield conn
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def init_db(self):
        """Initialize database with required tables"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS rss_feeds (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL CHECK(length(name) <= ?),
                        url TEXT NOT NULL UNIQUE CHECK(length(url) <= ?),
                        active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''', (Config.MAX_FEED_NAME_LENGTH, Config.MAX_URL_LENGTH))
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS keywords (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        keyword TEXT NOT NULL UNIQUE CHECK(length(keyword) <= ?),
                        active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''', (Config.MAX_KEYWORD_LENGTH,))
                
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
                
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_found_news_link ON found_news(link)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_found_news_date ON found_news(found_at)')
                
                self._populate_default_data(cursor)
                conn.commit()
                logger.info("Database initialized successfully")
                
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _populate_default_data(self, cursor):
        """Add test data if database is empty"""
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
            test_keywords = ['technology', 'artificial intelligence', 'Python', 
                           'programming', 'tech', 'AI', 'software', 'digital']
            cursor.executemany('INSERT INTO keywords (keyword) VALUES (?)', 
                             [(k,) for k in test_keywords])

class InputValidator:
    """Input validation utilities"""
    
    @staticmethod
    def validate_feed_name(name: str) -> str:
        if not name or not name.strip():
            raise ValidationError("Feed name cannot be empty")
        
        name = name.strip()
        if len(name) > Config.MAX_FEED_NAME_LENGTH:
            raise ValidationError(f"Feed name too long (max {Config.MAX_FEED_NAME_LENGTH} chars)")
        
        if '<' in name or '>' in name or '"' in name:
            raise ValidationError("Feed name contains invalid characters")
        
        return name
    
    @staticmethod
    def validate_feed_url(url: str) -> str:
        if not url or not url.strip():
            raise ValidationError("Feed URL cannot be empty")
        
        url = url.strip()
        if len(url) > Config.MAX_URL_LENGTH:
            raise ValidationError(f"URL too long (max {Config.MAX_URL_LENGTH} chars)")
        
        if not validators.url(url):
            raise ValidationError("Invalid URL format")
        
        return url
    
    @staticmethod
    def validate_keyword(keyword: str) -> str:
        if not keyword or not keyword.strip():
            raise ValidationError("Keyword cannot be empty")
        
        keyword = keyword.strip()
        if len(keyword) > Config.MAX_KEYWORD_LENGTH:
            raise ValidationError(f"Keyword too long (max {Config.MAX_KEYWORD_LENGTH} chars)")
        
        return keyword

class TextProcessor:
    """Text processing utilities"""
    
    @staticmethod
    def clean_html(text: Optional[str]) -> str:
        """Remove HTML tags and clean whitespace"""
        if not text:
            return ""
        
        try:
            clean = re.sub('<.*?>', '', text)
            clean = ' '.join(clean.split())
            return clean
        except Exception as e:
            logger.warning(f"Error cleaning HTML: {e}")
            return str(text)
    
    @staticmethod
    def check_keywords_in_text(text: Optional[str], keywords: List[str]) -> List[str]:
        """Find keywords in text using word boundaries"""
        if not text or not keywords:
            return []
        
        found_keywords = []
        try:
            text_lower = text.lower()
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text_lower):
                    found_keywords.append(keyword)
        except Exception as e:
            logger.warning(f"Error checking keywords: {e}")
        
        return found_keywords

class RSSParser:
    """RSS feed parsing and processing"""
    
    def __init__(self, db_manager: DatabaseManager, text_processor: TextProcessor):
        self.db_manager = db_manager
        self.text_processor = text_processor
    
    def parse_feed(self, feed_name: str, feed_url: str, keywords: List[str]) -> int:
        """Parse RSS feed and return number of new articles found"""
        try:
            logger.info(f"Parsing feed: {feed_name}")
            feed = feedparser.parse(feed_url)
            
            if feed.bozo:
                logger.warning(f"Feed parsing issues for {feed_name}: {feed.bozo_exception}")
            
            if not hasattr(feed, 'entries') or not feed.entries:
                logger.warning(f"No entries found in feed: {feed_name}")
                return 0
            
            return self._process_entries(feed, feed_name, keywords)
            
        except Exception as e:
            logger.error(f"Error parsing feed {feed_name}: {e}")
            return 0
    
    def _process_entries(self, feed, feed_name: str, keywords: List[str]) -> int:
        new_articles = 0
        
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                for entry in feed.entries[:Config.MAX_ENTRIES_PER_FEED]:
                    try:
                        if self._process_single_entry(cursor, entry, feed_name, keywords):
                            new_articles += 1
                    except Exception as e:
                        logger.warning(f"Error processing entry: {e}")
                        continue
                
                conn.commit()
                
        except sqlite3.Error as e:
            logger.error(f"Database error while processing entries: {e}")
            
        if new_articles > 0:
            logger.info(f"Added {new_articles} new articles from {feed_name}")
        
        return new_articles
    
    def _process_single_entry(self, cursor, entry, feed_name: str, keywords: List[str]) -> bool:
        title = getattr(entry, 'title', '')
        description = getattr(entry, 'description', '') or getattr(entry, 'summary', '')
        link = getattr(entry, 'link', '')
        
        if not title or not link:
            return False
        
        # Check if article already exists
        cursor.execute('SELECT id FROM found_news WHERE link = ?', (link,))
        if cursor.fetchone():
            return False
        
        description = self.text_processor.clean_html(description)
        
        # Search for keywords
        text_to_search = f"{title} {description}"
        matched_keywords = self.text_processor.check_keywords_in_text(text_to_search, keywords)
        
        if not matched_keywords:
            return False
        
        # Parse publication date
        published_date = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                published_date = datetime(*entry.published_parsed[:6])
            except Exception as e:
                logger.warning(f"Error parsing published date: {e}")
        
        # Save to database
        cursor.execute('''
            INSERT INTO found_news 
            (title, description, link, feed_name, keywords_matched, published_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            title,
            description[:Config.MAX_DESCRIPTION_LENGTH],
            link,
            feed_name,
            ', '.join(matched_keywords),
            published_date
        ))
        
        logger.info(f"Found article: {title[:50]}... (keywords: {', '.join(matched_keywords)})")
        return True

class RSSMonitor:
    """Main RSS monitoring class"""
    
    def __init__(self, db_path: str = Config.DEFAULT_DB_PATH):
        self.db_manager = DatabaseManager(db_path)
        self.text_processor = TextProcessor()
        self.rss_parser = RSSParser(self.db_manager, self.text_processor)
        self.monitoring = False
        self.monitor_thread = None
        
    def get_active_feeds(self) -> List[Tuple[str, str]]:
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT name, url FROM rss_feeds WHERE active = 1')
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Error getting active feeds: {e}")
            return []
        
    def get_active_keywords(self) -> List[str]:
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT keyword FROM keywords WHERE active = 1')
                return [row[0].lower() for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error getting active keywords: {e}")
            return []
        
    def monitor_feeds(self):
        """Main monitoring loop"""
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
                        
                        try:
                            self.rss_parser.parse_feed(feed_name, feed_url, keywords)
                        except Exception as e:
                            logger.error(f"Error processing feed {feed_name}: {e}")
                            
                        time.sleep(Config.FEED_REQUEST_DELAY)
                
                # Wait for next cycle with interruption possibility
                for _ in range(Config.MONITORING_INTERVAL_SECONDS):
                    if not self.monitoring:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
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

    def add_feed(self, name: str, url: str) -> bool:
        """Add RSS feed with validation"""
        try:
            validated_name = InputValidator.validate_feed_name(name)
            validated_url = InputValidator.validate_feed_url(url)
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO rss_feeds (name, url) VALUES (?, ?)', 
                             (validated_name, validated_url))
                conn.commit()
                logger.info(f"Added RSS feed: {validated_name}")
                return True
                
        except ValidationError as e:
            logger.warning(f"Validation error adding feed: {e}")
            return False
        except sqlite3.IntegrityError:
            logger.warning(f"RSS feed already exists: {url}")
            return False
        except sqlite3.Error as e:
            logger.error(f"Database error adding feed: {e}")
            return False

    def add_keyword(self, keyword: str) -> bool:
        """Add keyword with validation"""
        try:
            validated_keyword = InputValidator.validate_keyword(keyword)
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO keywords (keyword) VALUES (?)', (validated_keyword,))
                conn.commit()
                logger.info(f"Added keyword: {validated_keyword}")
                return True
                
        except ValidationError as e:
            logger.warning(f"Validation error adding keyword: {e}")
            return False
        except sqlite3.IntegrityError:
            logger.warning(f"Keyword already exists: {keyword}")
            return False
        except sqlite3.Error as e:
            logger.error(f"Database error adding keyword: {e}")
            return False

# Global instance
monitor = RSSMonitor()
app = Flask(__name__)

# HTML template
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
        .error { background: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px; margin: 10px 0; }
        .success { background: #d4edda; color: #155724; padding: 10px; border-radius: 5px; margin: 10px 0; }
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

    {% if error %}
    <div class="error">{{ error }}</div>
    {% endif %}
    
    {% if success %}
    <div class="success">{{ success }}</div>
    {% endif %}

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
            <input type="text" name="name" placeholder="Feed Name (max {{ max_name_length }} chars)" required>
            <input type="url" name="url" placeholder="RSS URL (max {{ max_url_length }} chars)" required>
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
            <input type="text" name="keyword" placeholder="Keyword (max {{ max_keyword_length }} chars)" required>
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
    try:
        with monitor.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM found_news ORDER BY found_at DESC LIMIT 50')
            news = cursor.fetchall()
            
            cursor.execute('SELECT * FROM rss_feeds ORDER BY name')
            feeds = cursor.fetchall()
            
            cursor.execute('SELECT * FROM keywords ORDER BY keyword')
            keywords = cursor.fetchall()
        
        return render_template_string(MAIN_TEMPLATE, 
                                    news=news, 
                                    feeds=feeds, 
                                    keywords=keywords,
                                    monitoring=monitor.monitoring,
                                    max_name_length=Config.MAX_FEED_NAME_LENGTH,
                                    max_url_length=Config.MAX_URL_LENGTH,
                                    max_keyword_length=Config.MAX_KEYWORD_LENGTH)
    except Exception as e:
        logger.error(f"Error rendering index page: {e}")
        return f"Error loading page: {e}", 500

@app.route('/start')
def start_monitoring():
    try:
        monitor.start_monitoring()
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        return redirect(url_for('index'))

@app.route('/stop')
def stop_monitoring():
    try:
        monitor.stop_monitoring()
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
        return redirect(url_for('index'))

@app.route('/add_feed', methods=['POST'])
def add_feed():
    name = request.form.get('name', '').strip()
    url = request.form.get('url', '').strip()
    
    if monitor.add_feed(name, url):
        return redirect(url_for('index'))
    else:
        return redirect(url_for('index'))

@app.route('/toggle_feed/<int:feed_id>')
def toggle_feed(feed_id):
    try:
        with monitor.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE rss_feeds SET active = 1 - active WHERE id = ?', (feed_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error toggling feed {feed_id}: {e}")
    
    return redirect(url_for('index'))

@app.route('/delete_feed/<int:feed_id>')
def delete_feed(feed_id):
    try:
        with monitor.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM rss_feeds WHERE id = ?', (feed_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error deleting feed {feed_id}: {e}")
    
    return redirect(url_for('index'))

@app.route('/add_keyword', methods=['POST'])
def add_keyword():
    keyword = request.form.get('keyword', '').strip()
    
    monitor.add_keyword(keyword)
    return redirect(url_for('index'))

@app.route('/toggle_keyword/<int:keyword_id>')
def toggle_keyword(keyword_id):
    try:
        with monitor.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE keywords SET active = 1 - active WHERE id = ?', (keyword_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error toggling keyword {keyword_id}: {e}")
    
    return redirect(url_for('index'))

@app.route('/delete_keyword/<int:keyword_id>')
def delete_keyword(keyword_id):
    try:
        with monitor.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM keywords WHERE id = ?', (keyword_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error deleting keyword {keyword_id}: {e}")
    
    return redirect(url_for('index'))

@app.route('/api/news')
def api_news():
    """API endpoint for retrieving news"""
    try:
        with monitor.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT title, description, link, feed_name, keywords_matched, published_date, found_at 
                FROM found_news 
                ORDER BY found_at DESC 
                LIMIT 100
            ''')
            news = cursor.fetchall()
        
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
    except Exception as e:
        logger.error(f"Error in API news endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/status')
def api_status():
    """API endpoint for system status"""
    try:
        with monitor.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM rss_feeds WHERE active = 1')
            active_feeds = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM keywords WHERE active = 1')
            active_keywords = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM found_news')
            total_articles = cursor.fetchone()[0]
        
        return jsonify({
            'monitoring': monitor.monitoring,
            'active_feeds': active_feeds,
            'active_keywords': active_keywords,
            'total_articles': total_articles
        })
    except Exception as e:
        logger.error(f"Error in API status endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("RSS News Monitor Service")
    print(f"Web interface: http://localhost:{Config.DEFAULT_PORT}")
    
    monitor.start_monitoring()
    
    try:
        app.run(host=Config.DEFAULT_HOST, port=Config.DEFAULT_PORT, debug=False)
    except KeyboardInterrupt:
        print("\nStopping service...")
        monitor.stop_monitoring()
        print("Service stopped")