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
DATA_LOCK = threading.RLock()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# ==============================
# DATA MANAGEMENT
# ==============================

def ensure_data_file_exists():
    """Ensure the JSON data file exists."""
    print(f"[DEBUG] Checking if data file exists: {DATA_FILE}")
    if not os.path.exists(DATA_FILE):
        print(f"[DEBUG] Creating new data file: {DATA_FILE}")
        try:
            with open(DATA_FILE, "w") as f:
                json.dump([], f)
            print(f"[DEBUG] Data file created successfully")
        except Exception as e:
            print(f"[ERROR] Failed to create data file: {e}")
            raise
    else:
        print(f"[DEBUG] Data file already exists")

def load_data():
    """Load tracked products from JSON file."""
    print(f"[DEBUG] Loading data from {DATA_FILE}")
    ensure_data_file_exists()
    
    try:
        with DATA_LOCK:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                print(f"[DEBUG] Loaded {len(data)} products from file")
                return data
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in data file: {e}")
        print(f"[DEBUG] Creating fresh data file")
        with open(DATA_FILE, "w") as f:
            json.dump([], f)
        return []
    except Exception as e:
        print(f"[ERROR] Failed to load data: {e}")
        return []

def save_data(data):
    """Save tracked products to JSON file."""
    print(f"[DEBUG] Saving {len(data)} products to {DATA_FILE}")
    try:
        with DATA_LOCK:
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=2)
        print(f"[DEBUG] Data saved successfully")
    except Exception as e:
        print(f"[ERROR] Failed to save data: {e}")

# ==============================
# PRICE FETCHING
# ==============================

def fetch_price_selenium(product_link):
    """Fetch price using Selenium with comprehensive error handling."""
    print(f"[DEBUG] Starting price fetch for: {product_link}")
    
    driver = None
    try:
        print("[DEBUG] Setting up Chrome options...")
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        selected_user_agent = random.choice(USER_AGENTS)
        options.add_argument(f'--user-agent={selected_user_agent}')
        print(f"[DEBUG] Using user agent: {selected_user_agent}")
        
        print("[DEBUG] Initializing Chrome webdriver...")
        driver = webdriver.Chrome(options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print(f"[DEBUG] Navigating to: {product_link}")
        driver.get(product_link)
        
        # Wait for page to load
        time.sleep(3)
        print("[DEBUG] Page loaded, searching for price...")
        
        # Try multiple price selectors
        price_selectors = [
            ".Nx9bqj.CxhGGd",
        ]
        
        price = None
        for i, selector in enumerate(price_selectors, 1):
            print(f"[DEBUG] Trying selector {i}/{len(price_selectors)}: {selector}")
            
            try:
                price_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                
                price_text = price_element.text.strip()
                print(f"[DEBUG] Found text: '{price_text}'")
                
                if price_text:
                    # Extract price from text
                    price_match = re.search(r'₹?[\s]*([0-9,]+)', price_text)
                    if price_match:
                        price_str = price_match.group(1).replace(',', '')
                        price = int(price_str)
                        print(f"[SUCCESS] Extracted price: ₹{price:,}")
                        break
                        
            except TimeoutException:
                print(f"[DEBUG] Selector timeout: {selector}")
                continue
            except Exception as e:
                print(f"[DEBUG] Error with selector {selector}: {e}")
                continue
        
        if price is None:
            print("[WARNING] Could not find price with any selector")
            try:
                page_title = driver.title
                print(f"[DEBUG] Page title: {page_title}")
                
                if any(keyword in page_title.lower() for keyword in ["404", "not found", "error"]):
                    print("[ERROR] Invalid page detected")
                else:
                    print("[DEBUG] Valid page but price not found")
            except Exception as e:
                print(f"[DEBUG] Error checking page: {e}")
        
        return price
        
    except WebDriverException as e:
        print(f"[ERROR] WebDriver error: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error: {type(e).__name__}: {e}")
        return None
    
    finally:
        if driver:
            try:
                driver.quit()
                print("[DEBUG] WebDriver closed")
            except Exception as e:
                print(f"[DEBUG] Error closing driver: {e}")

def get_product_title_selenium(product_link):
    """Get product title using Selenium."""
    print(f"[DEBUG] Fetching title for: {product_link}")
    
    driver = None
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(f'--user-agent={random.choice(USER_AGENTS)}')
        
        driver = webdriver.Chrome(options=options)
        driver.get(product_link)
        time.sleep(2)
        
        # Try multiple title selectors
        title_selectors = [
            "h1.yhB1nd",
            "h1._35KyD6",
            ".B_NuCI",
            "span.B_NuCI", 
            "h1",
            "[data-testid='product-title']"
        ]
        
        for selector in title_selectors:
            try:
                title_element = driver.find_element(By.CSS_SELECTOR, selector)
                title = title_element.text.strip()
                if title:
                    print(f"[DEBUG] Found title: {title[:50]}...")
                    return title[:100]  # Limit length
            except NoSuchElementException:
                continue
            except Exception as e:
                print(f"[DEBUG] Error getting title with {selector}: {e}")
                continue
        
        print("[WARNING] Could not find product title")
        return "Unknown Product"
        
    except Exception as e:
        print(f"[ERROR] Error fetching title: {e}")
        return "Unknown Product"
    
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

# ==============================
# TELEGRAM FUNCTIONS
# ==============================

async def send_message_async(context, chat_id, message):
    """Send message asynchronously."""
    try:
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
    except Exception as e:
        print(f"[ERROR] Failed to send message: {e}")
        # Try without markdown as fallback
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e2:
            print(f"[ERROR] Failed to send plain message: {e2}")

def add_product(chat_id, product_link):
    """Add product to tracking list."""
    print(f"[DEBUG] Adding product for chat {chat_id}: {product_link}")
    
    # First fetch current price
    current_price = fetch_price_selenium(product_link)
    if current_price is None:
        print(f"[ERROR] Could not fetch price for {product_link}")
        return None, "Could not fetch price. Please check the URL and try again."
    
    # Get product title
    title = get_product_title_selenium(product_link)
    
    # Atomic read-modify-write to avoid races with background checker
    with DATA_LOCK:
        data = load_data()
        
        # Check if already tracking
        for item in data:
            if item["product_link"] == product_link and item["chat_id"] == chat_id:
                return current_price, f"Already tracking this product!\n\n**Current Price:** ₹{current_price:,}"
        
        # Add new product
        new_product = {
            "chat_id": chat_id,
            "product_link": product_link,
            "title": title,
            "initial_price": current_price,
            "last_price": current_price,
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        data.append(new_product)
        save_data(data)
    
    success_msg = (
        f"✅ **Product Added Successfully!**\n\n"
        f"📱 **Product:** {title}\n"
        f"💰 **Current Price:** ₹{current_price:,}\n\n"
        f"🔔 You'll get alerts when the price drops!"
    )
    
    print(f"[SUCCESS] Product added for chat {chat_id}")
    return current_price, success_msg

def check_prices():
    """Check all tracked products for price changes."""
    print(f"[INFO] Starting price check at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    data = load_data()
    if not data:
        print("[INFO] No products to check")
        return
    
    updated = False
    for item in data:
        try:
            chat_id = item["chat_id"]
            product_link = item["product_link"]
            last_price = item["last_price"]
            title = item.get("title", "Unknown Product")
            
            print(f"[DEBUG] Checking: {title}")
            current_price = fetch_price_selenium(product_link)
            
            if current_price is None:
                print(f"[WARNING] Failed to check price for: {title}")
                continue
            
            print(f"[INFO] {title}: ₹{current_price:,} (was ₹{last_price:,})")
            
            # Update price
            item["last_price"] = current_price
            item["last_checked"] = time.strftime("%Y-%m-%d %H:%M:%S")
            updated = True
            
            # Check for price drop
            if current_price < last_price:
                discount = last_price - current_price
                discount_percent = (discount / last_price) * 100
                
                alert_msg = (
                    f"🎉 **PRICE DROP ALERT!**\n\n"
                    f"📱 **{title}**\n"
                    f"💰 **New Price:** ₹{current_price:,}\n"
                    f"📉 **Was:** ₹{last_price:,}\n"
                    f"💸 **You Save:** ₹{discount:,} ({discount_percent:.1f}% off)\n\n"
                    f"🔗 {product_link}"
                )
                
                # Send alert (this is synchronous, but for background task it's okay)
                try:
                    import requests
                    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                    requests.post(url, data={"chat_id": chat_id, "text": alert_msg}, timeout=10)
                    print(f"[SUCCESS] Price drop alert sent for {title}")
                except Exception as e:
                    print(f"[ERROR] Failed to send alert: {e}")
            
            # Add delay between checks
            time.sleep(random.uniform(5, 10))
            
        except Exception as e:
            print(f"[ERROR] Error checking product: {e}")
            continue
    
    if updated:
        # Merge updates with the latest on-disk data to avoid overwriting user additions
        with DATA_LOCK:
            current = load_data()
            # Build index for quick lookup
            index = {(item["chat_id"], item["product_link"]): i for i, item in enumerate(current)}
            for updated_item in data:
                key = (updated_item["chat_id"], updated_item["product_link"])
                if key in index:
                    i = index[key]
                    # Update only mutable fields
                    current[i]["last_price"] = updated_item.get("last_price", current[i].get("last_price"))
                    current[i]["last_checked"] = updated_item.get("last_checked", current[i].get("last_checked"))
                    if "title" in updated_item:
                        current[i]["title"] = updated_item["title"] or current[i].get("title")
                else:
                    # If background discovered an entry not on disk, append it
                    current.append(updated_item)
            save_data(current)
        print("[INFO] Price check completed and data saved")

# ==============================
# TELEGRAM HANDLERS
# ==============================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    if not update.message:
        return
    
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    print(f"[DEBUG] Received message from {chat_id}: {text}")
    
    if text.lower() in ['/start', '/help']:
        help_text = (
            "🤖 **Flipkart Price Tracker Bot**\n\n"
            "📌 **How to use:**\n"
            "• Send any Flipkart product link\n"
            "• Get current price instantly\n" 
            "• Automatic price drop alerts\n\n"
            "📋 **Commands:**\n"
            "• `/list` - View tracked products\n"
            "• `/help` - Show this help\n\n"
            "💡 **Tip:** Copy the full product URL from your browser"
        )
        await send_message_async(context, chat_id, help_text)
        
    elif text.lower() == '/list':
        await show_tracked_products(chat_id, context)
        
    elif "flipkart.com" in text.lower() and text.startswith("http"):
        # Show processing message
        await send_message_async(context, chat_id, "🔍 Fetching product details... Please wait...")
        
        # Process in thread to avoid blocking
        loop = asyncio.get_running_loop()
        try:
            current_price, result_msg = await loop.run_in_executor(None, add_product, chat_id, text)
            await send_message_async(context, chat_id, result_msg)
        except Exception as e:
            print(f"[ERROR] Error processing product: {e}")
            await send_message_async(context, chat_id, "❌ Error processing product. Please try again.")
    
    else:
        await send_message_async(context, chat_id, 
            "📌 Please send a valid Flipkart product link.\n\n"
            "Example: `https://www.flipkart.com/product-name/p/itm123456789`"
        )

async def show_tracked_products(chat_id, context):
    """Show user's tracked products."""
    data = load_data()
    user_products = [item for item in data if item["chat_id"] == chat_id]
    
    if not user_products:
        await send_message_async(context, chat_id, 
            "📋 No products tracked yet.\n\nSend me a Flipkart link to start tracking!"
        )
        return
    
    message = f"📋 **Your Tracked Products ({len(user_products)}):**\n\n"
    
    for i, item in enumerate(user_products[:5], 1):  # Show max 5
        title = item.get("title", "Unknown")[:40] + "..."
        current_price = item["last_price"]
        initial_price = item["initial_price"]
        
        if current_price < initial_price:
            trend = f"📉 -{((initial_price - current_price) / initial_price) * 100:.1f}%"
        elif current_price > initial_price:
            trend = f"📈 +{((current_price - initial_price) / initial_price) * 100:.1f}%"
        else:
            trend = "➖ Same"
        
        message += f"{i}. **{title}**\n   ₹{current_price:,} {trend}\n\n"
    
    if len(user_products) > 5:
        message += f"... and {len(user_products) - 5} more"
    
    await send_message_async(context, chat_id, message)

def start_price_checker():
    """Start background price checker."""
    def price_check_loop():
        while True:
            try:
                check_prices()
            except Exception as e:
                print(f"[ERROR] Error in price check loop: {e}")
            
            print(f"[INFO] Sleeping for 1 hour...")
            time.sleep(60)  # 1 hour
    
    thread = threading.Thread(target=price_check_loop, daemon=True)
    thread.start()
    print("[INFO] Price checker thread started")

# ==============================
# MAIN
# ==============================

if __name__ == "__main__":

    print("🚀 Starting Flipkart Price Tracker Bot...")
    
    # Ensure data file exists
    ensure_data_file_exists()
    
    # Create Telegram application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT, handle_message))
    
    # Start price checker
    start_price_checker()
    
    print("🤖 Bot started successfully!")
    print("📊 Monitoring for price changes every hour...")
    
    # Start bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)