#!/usr/bin/env python3
import feedparser
import time

def parse_rss_feed(url):
    feed = feedparser.parse(url)
    articles = []
    
    for entry in feed.entries[:10]:
        article = {
            'title': entry.title,
            'link': entry.link,
            'description': getattr(entry, 'description', '')
        }
        articles.append(article)
    
    return articles

def check_keywords(text, keywords):
    found = []
    text_lower = text.lower()
    for keyword in keywords:
        if keyword.lower() in text_lower:
            found.append(keyword)
    return found

def main():
    rss_urls = [
        'http://feeds.bbci.co.uk/news/rss.xml',
        'http://rss.cnn.com/rss/edition.rss'
    ]
    
    keywords = ['technology', 'AI', 'Python', 'programming']
    
    print("RSS Feed Monitor - Basic Version")
    print("=" * 40)
    
    for url in rss_urls:
        print(f"\nParsing: {url}")
        articles = parse_rss_feed(url)
        
        for article in articles:
            text_to_check = f"{article['title']} {article['description']}"
            matched_keywords = check_keywords(text_to_check, keywords)
            
            if matched_keywords:
                print(f"\nFound: {article['title']}")
                print(f"Keywords: {', '.join(matched_keywords)}")
                print(f"Link: {article['link']}")
        
        time.sleep(2)

if __name__ == '__main__':
    main()