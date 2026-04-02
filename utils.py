import os
import json
import time

def _default_output_dir() -> str:
    return os.path.join(os.path.expanduser('~'), 'Downloads', 'SimpDL')

def _sanitize_output_dir(path: str) -> str:
    path = (path or '').strip()
    if not path or path == '/path':
        return _default_output_dir()
    return os.path.expanduser(path)

def _has_auth_cookies(cookie_data: dict) -> bool:
    if not isinstance(cookie_data, dict):
        return False
    ch = (cookie_data.get('cookie_header') or '').strip()
    pc = cookie_data.get('parsed_cookies') or {}
    return bool(ch) or (isinstance(pc, dict) and len(pc) > 0)

def get_folder_name(url):
    url = url.rstrip('/')
    parts = url.split('/')
    if 'threads' in parts:
        idx = parts.index('threads')
        if idx + 1 < len(parts):
            folder = parts[idx + 1]
            if folder.startswith('page-'):
                if idx + 2 < len(parts):
                    folder = parts[idx + 2]
            return folder.split('?')[0]
    return "default_folder"

def verify_full_quality(url, session):
    """Attempt to find the full-res version of a medium-res link."""
    # Common Chevereto pattern: filename.md.jpg (medium) -> filename.jpg (full)
    if '.md.' in url:
        full_url = url.replace('.md.', '.')
        try:
            r = session.head(full_url, timeout=5)
            if r.status_code == 200:
                return full_url
        except:
            pass
    return url

def resolve_source_image_headless(url, context, session, log_callback=None):
    """
    Use a headless browser to resolve JS-rendered source images from landing pages.
    """
    if not url:
        return None
    
    url = url.strip()
    
    # If it's already a direct image link, return verified full version
    if any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
        return verify_full_quality(url, session)
        
    known_hosts = ['jpg6.su', 'jpg5.su', 'imgbox.com', 'pixl.is', 'saint.to', 'img.kiwi', 'catbox.moe']
    if not any(host in url for host in known_hosts):
        return None

    try:
        page = context.new_page()
        # Stealth headers
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://simpcity.cr/"
        })
        
        # Don't block too many resources, just the obvious ads/trackers
        page.route("**/*.{css,woff,woff2}", lambda route: route.abort())
        
        # Navigate and wait for actual content
        page.goto(url, wait_until='load', timeout=20000)
        
        # Stealth: move mouse slightly to trigger any "human" checks
        page.mouse.move(100, 100)
        time.sleep(1)
        
        # High-res selectors
        selectors = [
            'img.main-image',
            'img#img',
            'img#image',
            '.image-viewer-main-image',
            '#image-viewer-container img',
            'a[href*="/images/"] img'
        ]
        
        source_url = None
        for selector in selectors:
            try:
                # Wait for the image to be injected and HAVE a source that isn't a loading gif
                page.wait_for_selector(selector, timeout=8000)
                element = page.query_selector(selector)
                if element:
                    src = element.get_attribute('src')
                    if src and 'loading.svg' not in src and not src.startswith('data:'):
                        # Some sites use data-src for lazy loading the full res
                        data_src = element.get_attribute('data-src') or element.get_attribute('data-main-image')
                        source_url = data_src or src
                        break
            except:
                continue
        
        page.close()
        
        if source_url:
            return verify_full_quality(source_url, session)
        return None
    except:
        try: page.close()
        except: pass
        return None
