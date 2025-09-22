import requests
from bs4 import BeautifulSoup
import json
import os
import asyncio
import time
import threading
import re
import random
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
# ==============================
# CONFIG
# ==============================

load_dotenv()  
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") 

if not TELEGRAM_TOKEN:
    raise SystemExit("ERROR: Telegram token not found in environment variable TELEGRAM_TOKEN")

DATA_FILE = "tracked_products.json"
DATA_LOCK = threading.Lock()

# User agents pool to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# ==============================
# UTILITIES
# ==============================

def load_data():
    """Load tracked products from JSON file."""
    if not os.path.exists(DATA_FILE):
        return []
    with DATA_LOCK:
        with open(DATA_FILE, "r") as f:
            return json.load(f)

def save_data(data):
    """Save tracked products to JSON file."""
    with DATA_LOCK:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)

def get_random_headers():
    """Generate randomized headers to avoid detection."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "DNT": "1",
        "Sec-GPC": "1",
    }

def create_session():
    """Create a session with retry strategy and better configuration."""
    session = requests.Session()
    
    # Retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

# ==============================
# CORE FUNCTIONS
# ==============================

def resolve_flipkart_url(url):
    """Resolve Flipkart short URLs to actual product URLs."""
    try:
        session = create_session()
        headers = get_random_headers()
        
        # Add random delay
        time.sleep(random.uniform(2, 5))
        
        # Follow redirects to get final URL
        response = session.head(url, headers=headers, allow_redirects=True, timeout=15)
        final_url = response.url
        
        print(f"Original: {url}")
        print(f"Resolved: {final_url}")
        
        # Ensure it's a valid Flipkart product URL
        if "flipkart.com" in final_url and ("/p/" in final_url or "/dp/" in final_url):
            return final_url
        else:
            print(f"Invalid final URL: {final_url}")
            return url  # Return original URL if resolution fails
            
    except Exception as e:
        print(f"Error resolving URL: {e}")
        return url

def fetch_price(product_link):
    """Alternative method using selenium (requires installation)."""
    print(f"[DEBUG] Starting selenium price fetch for: {product_link}")
    
    resolved_url = resolve_flipkart_url(product_link)
    if not resolved_url:
        print(f"Could not resolve URL: {product_link}")
        return None
    
    print(f"Using URL: {resolved_url}")
    driver = None
    try:
        print("[DEBUG] Setting up Chrome options...")
        # Chrome options for headless browsing
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # User agents list (you'll need to define this or import it)
        USER_AGENTS = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        
        selected_user_agent = random.choice(USER_AGENTS)
        options.add_argument(f'--user-agent={selected_user_agent}')
        print(f"[DEBUG] Using user agent: {selected_user_agent}")
        
        print("[DEBUG] Initializing Chrome webdriver...")
        driver = webdriver.Chrome(options=options)
        print("[DEBUG] Chrome webdriver initialized successfully")
        
        # Anti-detection measure
        print("[DEBUG] Applying anti-detection measures...")
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        print("[DEBUG] Anti-detection measures applied")
        
        print(f"[DEBUG] Navigating to product page: {product_link}")
        driver.get(product_link)
        print("[DEBUG] Page loaded successfully")
        
        # Add a small delay to let the page fully load
        time.sleep(2)
        print("[DEBUG] Waited 2 seconds for page to stabilize")
        
        # Wait and try different selectors
        price_selectors = [
            ".Nx9bqj.CxhGGd",
            "._30jeq3._16Jk6d", 
            "._1_WHN1",
            ".CEmiEU .Nx9bqj",
            "._25b18c",
        ]
        
        print(f"[DEBUG] Attempting to find price using {len(price_selectors)} different selectors...")
        
        price = None
        for i, selector in enumerate(price_selectors, 1):
            print(f"[DEBUG] Trying selector {i}/{len(price_selectors)}: {selector}")
            
            try:
                print(f"[DEBUG] Waiting for element with selector: {selector}")
                price_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                print("[DEBUG] Price element found!")
                
                price_text = price_element.text
                print(f"[DEBUG] Raw price text: '{price_text}'")
                
                if not price_text:
                    print("[DEBUG] Price text is empty, trying next selector...")
                    continue
                
                # Extract price from text
                price_match = re.search(r'₹?([\d,]+)', price_text.replace(',', ''))
                if price_match:
                    price_str = price_match.group(1).replace(',', '')
                    price = int(price_str)
                    print(f"[DEBUG] Successfully extracted price: ₹{price}")
                    break
                else:
                    print(f"[DEBUG] Could not extract price from text: '{price_text}'")
                    
            except TimeoutException:
                print(f"[DEBUG] Timeout waiting for selector: {selector}")
                continue
            except NoSuchElementException:
                print(f"[DEBUG] Element not found for selector: {selector}")
                continue
            except ValueError as e:
                print(f"[DEBUG] Error converting price to integer: {e}")
                continue
            except Exception as e:
                print(f"[DEBUG] Unexpected error with selector {selector}: {type(e).__name__}: {e}")
                continue
        
        if price is None:
            print("[WARNING] Could not find price with any selector")
            # Try to get page source for debugging
            try:
                page_title = driver.title
                print(f"[DEBUG] Page title: {page_title}")
                
                # Check if we're on the right page
                if "404" in page_title.lower() or "not found" in page_title.lower():
                    print("[ERROR] Page not found (404)")
                elif "blocked" in page_title.lower() or "captcha" in page_title.lower():
                    print("[ERROR] Page blocked or CAPTCHA detected")
                else:
                    print("[DEBUG] Page seems valid but price not found")
                    
            except Exception as e:
                print(f"[DEBUG] Error getting page info: {e}")
        else:
            print(f"[SUCCESS] Price fetched successfully: ₹{price}")
        
        return price
        
    except WebDriverException as e:
        print(f"[ERROR] WebDriver error: {e}")
        print("[INFO] Make sure ChromeDriver is installed and in PATH")
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error in selenium fetch: {type(e).__name__}: {e}")
        import traceback
        print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
        return None
    
    finally:
        # Ensure driver is always closed
        if driver:
            try:
                print("[DEBUG] Closing webdriver...")
                driver.quit()
                print("[DEBUG] Webdriver closed successfully")
            except Exception as e:
                print(f"[DEBUG] Error closing webdriver: {e}")

def send_message(chat_id, message):
    """Send Telegram message to a user."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url, 
            data={"chat_id": chat_id, "text": message}, 
            timeout=15
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to send message: {e}")

def get_product_title(product_link):
    """Extract product title from Flipkart page."""
    resolved_url = resolve_flipkart_url(product_link)
    if not resolved_url:
        return "Unknown Product"
    
    session = create_session()
    headers = get_random_headers()
    
    try:
        time.sleep(random.uniform(1, 3))
        res = session.get(resolved_url, headers=headers, timeout=15)
        
        if res.status_code != 200:
            return "Unknown Product"
            
        soup = BeautifulSoup(res.text, "html.parser")
        
        title_selectors = [
            "h1.yhB1nd",
            "h1._35KyD6", 
            ".B_NuCI",
            "span.B_NuCI",
            "h1",
            ".x-item-title-label h1",
        ]
        
        for selector in title_selectors:
            title_tag = soup.select_one(selector)
            if title_tag:
                return title_tag.get_text(strip=True)[:100]
                
        return "Unknown Product"
        
    except Exception as e:
        print(f"Error getting title: {e}")
        return "Unknown Product"

def add_product(chat_id, product_link):
    """Add product to tracking list with its current price."""
    send_message(chat_id, "🔍 Fetching product details... (This may take a moment)")
    
    price = fetch_price(product_link)
    if price is None:
        error_msg = (
            "❌ Could not fetch price. Possible reasons:\n\n"
            "🔒 **Anti-bot protection active**\n"
            "🌐 **Try using the full product URL instead of short links**\n"
            "📱 **Product might be unavailable**\n"
            "⏰ **Server overload - try again later**\n\n"
            "💡 **Tips:**\n"
            "• Copy the full URL from browser\n" 
            "• Make sure product is available\n"
            "• Try again in a few minutes"
        )
        send_message(chat_id, error_msg)
        return

    title = get_product_title(product_link)
    
    with DATA_LOCK:
        data = load_data()
        
        # Check if product already exists
        for item in data:
            if item["product_link"] == product_link and item["chat_id"] == chat_id:
                send_message(chat_id, "⚠️ This product is already being tracked!")
                return
        
        data.append({
            "chat_id": chat_id,
            "product_link": product_link,
            "title": title,
            "initial_price": price,
            "last_price": price,
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        save_data(data)

    send_message(
        chat_id, 
        f"✅ **Successfully added to tracking!**\n\n"
        f"📱 **Product:** {title}\n"
        f"💰 **Current Price:** ₹{price:,}\n"
        f"🔗 **Link:** {product_link}\n\n"
        f"🔔 You'll get alerts when the price drops!"
    )

def check_prices():
    """Check all tracked products and send alerts if price drops."""
    print(f"🔍 Checking prices at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    with DATA_LOCK:
        data = load_data()
        updated = False
        failed_checks = 0

        for item in data:
            chat_id = item["chat_id"]
            product_link = item["product_link"]
            last_price = item["last_price"]
            title = item.get("title", "Unknown Product")

            print(f"Checking: {title}")
            current_price = fetch_price(product_link)
            
            if current_price is None:
                failed_checks += 1
                print(f"❌ Failed to fetch price for: {title}")
                continue

            print(f"✅ {title}: ₹{current_price:,} (was ₹{last_price:,})")

            if current_price < last_price:
                discount_percent = ((last_price - current_price) / last_price) * 100
                send_message(
                    chat_id,
                    f"🎉 **PRICE DROP ALERT!**\n\n"
                    f"📱 **{title}**\n"
                    f"💰 **New Price:** ₹{current_price:,}\n"
                    f"📉 **Was:** ₹{last_price:,}\n"
                    f"💸 **You Save:** ₹{last_price - current_price:,} ({discount_percent:.1f}% off)\n\n"
                    f"🔗 {product_link}"
                )
                
            item["last_price"] = current_price
            item["last_checked"] = time.strftime("%Y-%m-%d %H:%M:%S")
            updated = True
            
            # Add delay between product checks
            time.sleep(random.uniform(5, 15))

        if updated:
            save_data(data)
            
        print(f"✅ Price check complete. Failed: {failed_checks}/{len(data)}")

# ==============================
# TELEGRAM HANDLERS
# ==============================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages sent to the bot."""
    if update.message is None:
        return
        
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        return
        
    text = update.message.text.strip()

    if text.lower() in ['/start', '/help']:
        help_text = (
            "🤖 **Flipkart Price Tracker Bot**\n\n"
            "📌 **How to use:**\n"
            "• Send me any Flipkart product link\n"
            "• I'll track price changes for you\n"
            "• Get alerts when prices drop!\n\n"
            "📋 **Commands:**\n"
            "• `/list` - View tracked products\n"
            "• `/test` - Test with a sample link\n"
            "• `/help` - Show this help\n\n"
            "💡 **Note:** Due to anti-bot protection, some links may not work immediately. I'll keep trying!"
        )
        await context.bot.send_message(chat_id=chat_id, text=help_text, parse_mode='Markdown')
        
    elif text.lower() == '/list':
        await show_tracked_products(chat_id, context)
        
    elif text.lower() == '/test':
        test_url = "https://www.flipkart.com/apple-iphone-15-black-128-gb/p/itm6ac6485515ae4"
        await context.bot.send_message(chat_id=chat_id, text=f"🧪 Testing with sample URL:\n{test_url}")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, add_product, chat_id, test_url)
        
    elif text and ("flipkart.com" in text or "dl.flipkart.com" in text) and text.startswith("http"):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, add_product, chat_id, text)
        
    else:
        await context.bot.send_message(
            chat_id=chat_id, 
            text=(
                "📌 **Please send a valid Flipkart product link.**\n\n"
                "✅ **Examples:**\n"
                "• `https://www.flipkart.com/product-name/p/itm123456789`\n"
                "• `https://dl.flipkart.com/s/shortlink`\n\n"
                "💡 **Tip:** Copy the link directly from your browser for best results!"
            ),
            parse_mode='Markdown'
        )

async def show_tracked_products(chat_id, context):
    """Show user's tracked products."""
    with DATA_LOCK:
        data = load_data()
        user_products = [item for item in data if item["chat_id"] == chat_id]
    
    if not user_products:
        await context.bot.send_message(
            chat_id=chat_id, 
            text="📋 You're not tracking any products yet.\n\nSend me a Flipkart link to get started!"
        )
        return
    
    message = f"📋 **Your Tracked Products ({len(user_products)}):**\n\n"
    
    for i, item in enumerate(user_products[:10], 1):
        title = item.get("title", "Unknown Product")[:50]
        current_price = item["last_price"]
        initial_price = item["initial_price"]
        
        if current_price < initial_price:
            trend = f"📉 -{((initial_price - current_price) / initial_price) * 100:.1f}%"
        elif current_price > initial_price:
            trend = f"📈 +{((current_price - initial_price) / initial_price) * 100:.1f}%"
        else:
            trend = "➖ No change"
            
        message += f"{i}. **{title}**\n   ₹{current_price:,} {trend}\n\n"
    
    if len(user_products) > 10:
        message += f"... and {len(user_products) - 10} more products"
    
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

def start_price_check_thread():
    """Start a daemon thread that runs price checks periodically."""
    def _loop():
        while True:
            try:
                check_prices()
            except Exception as e:
                print(f"Error in price check: {e}")
            # Longer interval to avoid detection
            time.sleep(60 * 60)  # 1 hour
            
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    print("🔄 Price check thread started (1-hour intervals)")

# ==============================
# MAIN
# ==============================

if __name__ == "__main__":
    print("🚀 Starting Advanced Flipkart Price Tracker...")
    
    # Build application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT, handle_message))

    # Start periodic price checks
    start_price_check_thread()

    # Start polling
    print("🤖 Telegram bot started...")
    print("📡 Polling for messages...")
    print("⚠️  Note: Due to anti-bot measures, some requests may fail initially")
    application.run_polling(allowed_updates=Update.ALL_TYPES)