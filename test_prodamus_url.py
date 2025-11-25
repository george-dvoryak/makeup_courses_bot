#!/usr/bin/env python3
"""
Test script to verify Prodamus URL generation and short link resolution.
"""
import os
import sys

# Try to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Test URL generation
def test_url_generation():
    """Test the URL generation format"""
    from urllib.parse import quote
    
    def strip_html(text: str) -> str:
        """Simple HTML tag stripper"""
        import re
        return re.sub(r'<[^>]+>', '', text) if text else ""
    
    def rub_str(amount) -> str:
        """Format amount as string with 2 decimal places"""
        return f"{float(amount):.2f}"
    
    # Sample parameters
    base_url = "https://testwork1.payform.ru"
    order_number = "test_order_123"
    amount = 1000.0
    product_name = "Тестовый курс"
    customer_email = "test@example.com"
    customer_phone = "+79998887755"
    
    # Clean product name
    clean_name = strip_html(product_name) if product_name else "Доступ к курсу"
    
    # Build parameters according to Prodamus documentation
    params = [
        ("order_id", order_number),
        ("products[0][price]", rub_str(amount)),
        ("products[0][quantity]", "1"),
        ("products[0][name]", clean_name),
        ("customer_extra", f"Оплата курса: {clean_name}"),
        ("do", "pay"),
    ]
    
    if customer_email:
        params.append(("customer_email", customer_email))
    if customer_phone:
        phone = customer_phone.replace("+", "").replace(" ", "").replace("-", "")
        params.append(("customer_phone", phone))
    
    # Build URL with proper encoding
    query_string = "&".join(f"{quote(str(k), safe='[]')}={quote(str(v), safe='')}" for k, v in params)
    url = f"{base_url}/?{query_string}"
    
    print("=" * 60)
    print("Generated URL:")
    print(url)
    print("=" * 60)
    
    return url


def test_resolve_short_link(long_url: str):
    """Test resolving the short link"""
    import urllib.request
    import urllib.error
    
    print("\n" + "=" * 60)
    print("Resolving short link...")
    print("=" * 60)
    
    try:
        # Create a request that doesn't follow redirects
        class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        
        opener = urllib.request.build_opener(NoRedirectHandler)
        
        print("\n1. Trying without following redirects...")
        req = urllib.request.Request(long_url, headers={'User-Agent': 'Mozilla/5.0'})
        
        try:
            response = opener.open(req, timeout=15)
            print(f"   Status: {response.status}")
        except urllib.error.HTTPError as e:
            print(f"   Status: {e.code}")
            if e.code in (301, 302, 303, 307, 308):
                location = e.headers.get("Location")
                if location:
                    print(f"   ✅ Found redirect Location: {location}")
                    return location
        
        # Try following redirects
        print("\n2. Trying with following redirects...")
        req = urllib.request.Request(long_url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req, timeout=15)
        final_url = response.geturl()
        print(f"   Final URL: {final_url}")
        print(f"   Status: {response.status}")
        
        if final_url != long_url:
            print(f"   ✅ Redirected to: {final_url}")
            return final_url
        
        # Check response content
        print("\n3. Checking response content...")
        content = response.read().decode('utf-8', errors='ignore')
        print(f"   Content length: {len(content)}")
        if content:
            print(f"   First 500 chars: {content[:500]}")
        
        return long_url
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return long_url


def test_with_real_config():
    """Test with real bot configuration"""
    print("\n" + "=" * 60)
    print("Testing with real bot configuration...")
    print("=" * 60)
    
    # Import after loading env
    from config import get_available_bots, get_bot_config
    
    bots = get_available_bots()
    print(f"Available bots: {bots}")
    
    for bot_name in bots[:1]:  # Test first bot only
        print(f"\n--- Bot: {bot_name} ---")
        config = get_bot_config(bot_name)
        
        prodamus_url = config.get('PRODAMUS_PAYFORM_URL', '')
        prodamus_secret = config.get('PRODAMUS_SECRET_KEY', '')
        enable_prodamus = config.get('ENABLE_PRODAMUS', False)
        
        print(f"ENABLE_PRODAMUS: {enable_prodamus}")
        print(f"PRODAMUS_PAYFORM_URL: {prodamus_url}")
        print(f"PRODAMUS_SECRET_KEY: {'***' + prodamus_secret[-6:] if prodamus_secret else 'NOT SET'}")
        
        if prodamus_url:
            # Generate test URL
            from urllib.parse import quote
            
            base_url = f"https://{prodamus_url}" if not prodamus_url.startswith("http") else prodamus_url
            
            params = [
                ("order_id", "test_123"),
                ("products[0][price]", "100.00"),
                ("products[0][quantity]", "1"),
                ("products[0][name]", "Тестовый курс"),
                ("customer_extra", "Тестовая оплата"),
                ("do", "pay"),
                ("customer_email", "test@test.com"),
            ]
            
            query_string = "&".join(f"{quote(str(k), safe='[]')}={quote(str(v), safe='')}" for k, v in params)
            test_url = f"{base_url}/?{query_string}"
            
            print(f"\nGenerated URL:")
            print(test_url)
            
            # Try to resolve
            print("\nAttempting to resolve short link...")
            short_url = test_resolve_short_link(test_url)
            print(f"\n✅ Final URL: {short_url}")


if __name__ == "__main__":
    print("Prodamus URL Test")
    print("=" * 60)
    
    # Basic test
    long_url = test_url_generation()
    
    # Test resolution (may require network)
    if "--resolve" in sys.argv:
        short_url = test_resolve_short_link(long_url)
        print(f"\n✅ Result: {short_url}")
    
    # Test with real config
    if "--real" in sys.argv:
        test_with_real_config()
    
    print("\n" + "=" * 60)
    print("Done!")

