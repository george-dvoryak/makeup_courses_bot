#!/usr/bin/env python3
"""
Simplified multi-bot architecture test.
Tests code structure and logic without requiring all dependencies.
"""
import sys
import os
import ast
import re

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_test(name):
    print(f"\n{BLUE}=== {name} ==={RESET}")

def print_success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")

def print_error(msg):
    print(f"{RED}❌ {msg}{RESET}")

def print_warning(msg):
    print(f"{YELLOW}⚠️  {msg}{RESET}")

def print_info(msg):
    print(f"ℹ️  {msg}")

# Test 1: Check required files exist
def test_files_exist():
    print_test("Test 1: Required Files")
    
    required_files = [
        'config.py',
        'bot_factory.py',
        'bot_context.py',
        'db.py',
        'google_sheets.py',
        'main.py',
        'webhook_app_multi.py',
    ]
    
    missing = []
    for file in required_files:
        if os.path.exists(file):
            print_success(f"{file} exists")
        else:
            print_error(f"{file} missing")
            missing.append(file)
    
    return len(missing) == 0

# Test 2: Check config.py structure
def test_config_structure():
    print_test("Test 2: Config Structure")
    
    try:
        with open('config.py', 'r') as f:
            content = f.read()
        
        # Check for multi-bot functions
        checks = [
            ('get_bot_config', 'get_bot_config function'),
            ('get_available_bots', 'get_available_bots function'),
            ('CURRENT_BOT_NAME', 'CURRENT_BOT_NAME variable'),
            ('_bot_configs', 'bot configs cache'),
        ]
        
        all_ok = True
        for pattern, name in checks:
            if pattern in content:
                print_success(f"{name} found")
            else:
                print_error(f"{name} not found")
                all_ok = False
        
        return all_ok
    except Exception as e:
        print_error(f"Error reading config.py: {e}")
        return False

# Test 3: Check bot_context.py structure
def test_bot_context_structure():
    print_test("Test 3: Bot Context Structure")
    
    try:
        with open('bot_context.py', 'r') as f:
            content = f.read()
        
        checks = [
            ('set_bot_context', 'set_bot_context function'),
            ('get_bot_context', 'get_bot_context function'),
            ('clear_bot_context', 'clear_bot_context function'),
            ('threading.local', 'thread-local storage'),
        ]
        
        all_ok = True
        for pattern, name in checks:
            if pattern in content:
                print_success(f"{name} found")
            else:
                print_error(f"{name} not found")
                all_ok = False
        
        return all_ok
    except Exception as e:
        print_error(f"Error reading bot_context.py: {e}")
        return False

# Test 4: Check bot_factory.py structure
def test_bot_factory_structure():
    print_test("Test 4: Bot Factory Structure")
    
    try:
        with open('bot_factory.py', 'r') as f:
            content = f.read()
        
        checks = [
            ('create_bot_instance', 'create_bot_instance function'),
            ('get_bot_instance', 'get_bot_instance function'),
            ('initialize_all_bots', 'initialize_all_bots function'),
            ('_bots', 'bots cache dictionary'),
        ]
        
        all_ok = True
        for pattern, name in checks:
            if pattern in content:
                print_success(f"{name} found")
            else:
                print_error(f"{name} not found")
                all_ok = False
        
        return all_ok
    except Exception as e:
        print_error(f"Error reading bot_factory.py: {e}")
        return False

# Test 5: Check db.py multi-bot support
def test_db_multi_bot():
    print_test("Test 5: Database Multi-Bot Support")
    
    try:
        with open('db.py', 'r') as f:
            content = f.read()
        
        checks = [
            ('get_connection', 'get_connection function'),
            ('bot_name', 'bot_name parameter'),
            ('get_bot_config', 'get_bot_config import'),
            ('get_bot_context', 'get_bot_context import'),
            ('_connections', 'connections cache'),
        ]
        
        all_ok = True
        for pattern, name in checks:
            if pattern in content:
                print_success(f"{name} found")
            else:
                print_error(f"{name} not found")
                all_ok = False
        
        return all_ok
    except Exception as e:
        print_error(f"Error reading db.py: {e}")
        return False

# Test 6: Check google_sheets.py multi-bot support
def test_google_sheets_multi_bot():
    print_test("Test 6: Google Sheets Multi-Bot Support")
    
    try:
        with open('google_sheets.py', 'r') as f:
            content = f.read()
        
        checks = [
            ('get_courses_data', 'get_courses_data function'),
            ('get_texts_data', 'get_texts_data function'),
            ('bot_name', 'bot_name parameter'),
            ('get_bot_config', 'get_bot_config import'),
            ('get_bot_context', 'get_bot_context import'),
        ]
        
        all_ok = True
        for pattern, name in checks:
            if pattern in content:
                print_success(f"{name} found")
            else:
                print_error(f"{name} not found")
                all_ok = False
        
        return all_ok
    except Exception as e:
        print_error(f"Error reading google_sheets.py: {e}")
        return False

# Test 7: Check main.py multi-bot support
def test_main_multi_bot():
    print_test("Test 7: Main.py Multi-Bot Support")
    
    try:
        with open('main.py', 'r') as f:
            content = f.read()
        
        checks = [
            ('get_current_bot', 'get_current_bot function'),
            ('get_current_config', 'get_current_config function'),
            ('get_current_admin_ids', 'get_current_admin_ids function'),
            ('get_current_payment_config', 'get_current_payment_config function'),
            ('get_bot_context', 'get_bot_context import'),
            ('get_bot_instance', 'get_bot_instance import'),
        ]
        
        all_ok = True
        for pattern, name in checks:
            if pattern in content:
                print_success(f"{name} found")
            else:
                print_error(f"{name} not found")
                all_ok = False
        
        # Check that bot. is replaced with current_bot. in handlers
        # Count occurrences
        bot_dot_count = len(re.findall(r'\bbot\.', content))
        current_bot_dot_count = len(re.findall(r'\bcurrent_bot\.', content))
        
        print_info(f"Found {bot_dot_count} 'bot.' references")
        print_info(f"Found {current_bot_dot_count} 'current_bot.' references")
        
        if current_bot_dot_count > 0:
            print_success("current_bot. usage found in handlers")
        else:
            print_warning("No current_bot. usage found (may need migration)")
        
        return all_ok
    except Exception as e:
        print_error(f"Error reading main.py: {e}")
        return False

# Test 8: Check webhook_app_multi.py structure
def test_webhook_multi_structure():
    print_test("Test 8: Webhook Multi-Bot Structure")
    
    try:
        with open('webhook_app_multi.py', 'r') as f:
            content = f.read()
        
        checks = [
            ('initialize_all_bots', 'initialize_all_bots call'),
            ('get_bot_config', 'get_bot_config usage'),
            ('set_bot_context', 'set_bot_context usage'),
            ('get_bot_instance', 'get_bot_instance usage'),
            ('/webhook/', 'webhook routing pattern'),
            ('/prodamus/', 'prodamus routing pattern'),
        ]
        
        all_ok = True
        for pattern, name in checks:
            if pattern in content:
                print_success(f"{name} found")
            else:
                print_error(f"{name} not found")
                all_ok = False
        
        return all_ok
    except Exception as e:
        print_error(f"Error reading webhook_app_multi.py: {e}")
        return False

# Test 9: Check for bot. usage in main.py handlers
def test_bot_replacement():
    print_test("Test 9: Bot Reference Replacement")
    
    try:
        with open('main.py', 'r') as f:
            lines = f.readlines()
        
        # Find function definitions
        in_handler = False
        handler_functions = []
        current_function = None
        
        for i, line in enumerate(lines):
            # Check if this is a handler function
            if '@bot.' in line or 'def handle_' in line or 'def cb_' in line:
                in_handler = True
                # Extract function name
                match = re.search(r'def\s+(\w+)', line)
                if match:
                    current_function = match.group(1)
            
            # Check if we're in a handler function
            if in_handler and current_function:
                # Check for bot. usage
                if 'bot.' in line and 'current_bot = get_current_bot()' not in '\n'.join(lines[max(0, i-5):i]):
                    if current_function not in handler_functions:
                        handler_functions.append(current_function)
            
            # Reset if we hit another function or decorator
            if line.strip().startswith('def ') and current_function:
                if 'def ' + current_function not in line:
                    in_handler = False
                    current_function = None
        
        if handler_functions:
            print_warning(f"Found {len(handler_functions)} handler(s) that may still use 'bot.': {', '.join(handler_functions[:5])}")
        else:
            print_success("No obvious bot. usage in handlers (may need manual check)")
        
        return True
    except Exception as e:
        print_error(f"Error checking bot replacement: {e}")
        return False

# Main test runner
def main():
    print(f"\n{BLUE}{'='*60}")
    print("MULTI-BOT ARCHITECTURE STRUCTURE TEST")
    print(f"{'='*60}{RESET}\n")
    
    tests = [
        ("Required Files", test_files_exist),
        ("Config Structure", test_config_structure),
        ("Bot Context Structure", test_bot_context_structure),
        ("Bot Factory Structure", test_bot_factory_structure),
        ("Database Multi-Bot", test_db_multi_bot),
        ("Google Sheets Multi-Bot", test_google_sheets_multi_bot),
        ("Main.py Multi-Bot", test_main_multi_bot),
        ("Webhook Multi-Bot", test_webhook_multi_structure),
        ("Bot Reference Replacement", test_bot_replacement),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{BLUE}{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}{RESET}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        if result:
            print_success(f"{test_name}")
        else:
            print_error(f"{test_name}")
    
    print(f"\n{BLUE}Total: {passed}/{total} tests passed{RESET}\n")
    
    if passed == total:
        print(f"{GREEN}🎉 All structure tests passed!{RESET}\n")
        print(f"{YELLOW}Note: This test only checks code structure.{RESET}")
        print(f"{YELLOW}For full functional testing, install dependencies and run test_multi_bot.py{RESET}\n")
        return 0
    else:
        print(f"{RED}⚠️  Some structure tests failed{RESET}\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())

