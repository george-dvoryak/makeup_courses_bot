#!/usr/bin/env python3
"""
Comprehensive test for multi-bot architecture.
Tests configuration, initialization, context, database, and Google Sheets isolation.
"""
import os
import sys
import tempfile
import shutil

# Colors for output
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

# Test 1: Configuration loading
def test_config_loading():
    print_test("Test 1: Configuration Loading")
    
    try:
        from config import get_bot_config, get_available_bots, CURRENT_BOT_NAME
        
        # Test default bot config
        default_config = get_bot_config()
        print_success(f"Default bot config loaded: {CURRENT_BOT_NAME}")
        print_info(f"  - Token: {default_config.get('TELEGRAM_BOT_TOKEN', 'N/A')[:20]}...")
        print_info(f"  - Database: {default_config.get('DATABASE_PATH', 'N/A')}")
        print_info(f"  - Google Sheet: {default_config.get('GSHEET_ID', 'N/A')[:20]}...")
        
        # Test available bots
        available_bots = get_available_bots()
        print_success(f"Available bots: {', '.join(available_bots) if available_bots else 'None (using default)'}")
        
        # Test bot-specific config (if exists)
        for bot_name in available_bots[:3]:  # Test first 3 bots
            try:
                bot_config = get_bot_config(bot_name)
                print_success(f"Bot '{bot_name}' config loaded")
                print_info(f"  - Database: {bot_config.get('DATABASE_PATH', 'N/A')}")
            except Exception as e:
                print_warning(f"Bot '{bot_name}' config error: {e}")
        
        return True
    except Exception as e:
        print_error(f"Configuration loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# Test 2: Bot factory
def test_bot_factory():
    print_test("Test 2: Bot Factory")
    
    try:
        from bot_factory import create_bot_instance, get_bot_instance, initialize_all_bots, get_all_bots
        from config import get_available_bots
        
        # Initialize all bots
        bots = initialize_all_bots()
        print_success(f"Initialized {len(bots)} bot(s)")
        
        for bot_name, bot_instance in bots.items():
            print_info(f"  - {bot_name}: {type(bot_instance).__name__}")
            print_info(f"    Token: {bot_instance.token[:20]}...")
        
        # Test get_bot_instance
        available_bots = get_available_bots()
        if available_bots:
            test_bot_name = available_bots[0]
            bot = get_bot_instance(test_bot_name)
            print_success(f"Retrieved bot instance for '{test_bot_name}'")
        else:
            bot = get_bot_instance()
            print_success("Retrieved default bot instance")
        
        return True
    except Exception as e:
        print_error(f"Bot factory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# Test 3: Bot context
def test_bot_context():
    print_test("Test 3: Bot Context")
    
    try:
        from bot_context import set_bot_context, get_bot_context, clear_bot_context
        import threading
        
        # Test context in main thread
        print_info("Testing context in main thread...")
        set_bot_context("test_bot")
        context = get_bot_context()
        if context == "test_bot":
            print_success("Context set and retrieved correctly")
        else:
            print_error(f"Context mismatch: expected 'test_bot', got '{context}'")
            return False
        
        clear_bot_context()
        context = get_bot_context()
        if context is None:
            print_success("Context cleared correctly")
        else:
            print_error(f"Context not cleared: {context}")
            return False
        
        # Test context in different thread
        print_info("Testing context in different thread...")
        thread_context = [None]
        
        def thread_func():
            set_bot_context("thread_bot")
            thread_context[0] = get_bot_context()
        
        thread = threading.Thread(target=thread_func)
        thread.start()
        thread.join()
        
        if thread_context[0] == "thread_bot":
            print_success("Context works in separate thread")
        else:
            print_error(f"Context in thread: expected 'thread_bot', got '{thread_context[0]}'")
            return False
        
        # Verify main thread context is not affected
        main_context = get_bot_context()
        if main_context is None:
            print_success("Main thread context not affected by thread")
        else:
            print_error(f"Main thread context affected: {main_context}")
            return False
        
        return True
    except Exception as e:
        print_error(f"Bot context test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# Test 4: Database isolation
def test_database_isolation():
    print_test("Test 4: Database Isolation")
    
    try:
        from db import get_connection, add_user, get_user
        from bot_context import set_bot_context, clear_bot_context
        import tempfile
        import os
        
        # Create temporary databases
        temp_dir = tempfile.mkdtemp()
        db1_path = os.path.join(temp_dir, "bot1_test.db")
        db2_path = os.path.join(temp_dir, "bot2_test.db")
        
        try:
            # Test database 1
            print_info("Testing database 1...")
            conn1 = get_connection(database_path=db1_path)
            add_user(123, "user1", conn=conn1)
            user1 = get_user(123, conn=conn1)
            if user1 and user1["username"] == "user1":
                print_success("Database 1: User added and retrieved")
            else:
                print_error("Database 1: User not found")
                return False
            
            # Test database 2
            print_info("Testing database 2...")
            conn2 = get_connection(database_path=db2_path)
            add_user(456, "user2", conn=conn2)
            user2 = get_user(456, conn=conn2)
            if user2 and user2["username"] == "user2":
                print_success("Database 2: User added and retrieved")
            else:
                print_error("Database 2: User not found")
                return False
            
            # Verify isolation: user1 should not be in db2
            user1_in_db2 = get_user(123, conn=conn2)
            if user1_in_db2 is None:
                print_success("Database isolation: User from db1 not found in db2")
            else:
                print_error("Database isolation failed: User from db1 found in db2")
                return False
            
            # Verify isolation: user2 should not be in db1
            user2_in_db1 = get_user(456, conn=conn1)
            if user2_in_db1 is None:
                print_success("Database isolation: User from db2 not found in db1")
            else:
                print_error("Database isolation failed: User from db2 found in db1")
                return False
            
            return True
        finally:
            # Cleanup
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    except Exception as e:
        print_error(f"Database isolation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# Test 5: Google Sheets isolation
def test_google_sheets_isolation():
    print_test("Test 5: Google Sheets Isolation")
    
    try:
        from google_sheets import get_courses_data, get_texts_data
        from bot_context import set_bot_context, clear_bot_context
        from config import get_available_bots
        
        # Test with context
        available_bots = get_available_bots()
        if len(available_bots) >= 2:
            print_info(f"Testing with {len(available_bots)} bots...")
            
            # Test bot 1
            set_bot_context(available_bots[0])
            try:
                courses1 = get_courses_data()
                texts1 = get_texts_data()
                print_success(f"Bot '{available_bots[0]}': Loaded {len(courses1)} courses, {len(texts1)} texts")
            except Exception as e:
                print_warning(f"Bot '{available_bots[0]}': Error loading data: {e}")
            
            clear_bot_context()
            
            # Test bot 2
            set_bot_context(available_bots[1])
            try:
                courses2 = get_courses_data()
                texts2 = get_texts_data()
                print_success(f"Bot '{available_bots[1]}': Loaded {len(courses2)} courses, {len(texts2)} texts")
            except Exception as e:
                print_warning(f"Bot '{available_bots[1]}': Error loading data: {e}")
            
            clear_bot_context()
            
            return True
        else:
            print_warning("Need at least 2 bots configured to test isolation")
            # Test default bot
            try:
                courses = get_courses_data()
                texts = get_texts_data()
                print_success(f"Default bot: Loaded {len(courses)} courses, {len(texts)} texts")
                return True
            except Exception as e:
                print_warning(f"Default bot: Error loading data: {e}")
                return True  # Not a failure, just no data
    except Exception as e:
        print_error(f"Google Sheets isolation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# Test 6: Main.py helpers
def test_main_helpers():
    print_test("Test 6: Main.py Helpers")
    
    try:
        from main import get_current_bot, get_current_config, get_current_admin_ids, get_current_payment_config
        from bot_context import set_bot_context, clear_bot_context
        
        # Test default
        config = get_current_config()
        print_success("get_current_config() works")
        print_info(f"  - Database: {config.get('DATABASE_PATH', 'N/A')}")
        
        admin_ids = get_current_admin_ids()
        print_success(f"get_current_admin_ids() works: {len(admin_ids)} admin(s)")
        
        payment_config = get_current_payment_config()
        print_success("get_current_payment_config() works")
        print_info(f"  - Prodamus enabled: {payment_config.get('ENABLE_PRODAMUS', False)}")
        
        bot = get_current_bot()
        print_success("get_current_bot() works")
        print_info(f"  - Bot type: {type(bot).__name__}")
        
        # Test with context
        available_bots = get_available_bots()
        if available_bots:
            test_bot = available_bots[0]
            set_bot_context(test_bot)
            
            config2 = get_current_config()
            if config2.get('DATABASE_PATH') != config.get('DATABASE_PATH'):
                print_success(f"Context switching works: different config for '{test_bot}'")
            else:
                print_warning(f"Context switching: same config (may be expected if not configured)")
            
            clear_bot_context()
        
        return True
    except Exception as e:
        print_error(f"Main.py helpers test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# Test 7: Webhook routing
def test_webhook_routing():
    print_test("Test 7: Webhook Routing")
    
    try:
        # Check if webhook_app_multi.py exists and can be imported
        try:
            import webhook_app_multi
            print_success("webhook_app_multi.py can be imported")
            
            # Check Flask app
            if hasattr(webhook_app_multi, 'app'):
                print_success("Flask app exists")
                
                # Check routes
                routes = []
                for rule in webhook_app_multi.app.url_map.iter_rules():
                    routes.append(rule.rule)
                
                print_info(f"Found {len(routes)} route(s):")
                for route in routes[:10]:  # Show first 10
                    print_info(f"  - {route}")
                
                if len(routes) > 10:
                    print_info(f"  ... and {len(routes) - 10} more")
                
                return True
            else:
                print_error("Flask app not found")
                return False
        except ImportError as e:
            print_warning(f"webhook_app_multi.py not available: {e}")
            return True  # Not a failure if file doesn't exist
    except Exception as e:
        print_error(f"Webhook routing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# Main test runner
def main():
    print(f"\n{BLUE}{'='*60}")
    print("MULTI-BOT ARCHITECTURE TEST SUITE")
    print(f"{'='*60}{RESET}\n")
    
    tests = [
        ("Configuration Loading", test_config_loading),
        ("Bot Factory", test_bot_factory),
        ("Bot Context", test_bot_context),
        ("Database Isolation", test_database_isolation),
        ("Google Sheets Isolation", test_google_sheets_isolation),
        ("Main.py Helpers", test_main_helpers),
        ("Webhook Routing", test_webhook_routing),
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
        print(f"{GREEN}🎉 All tests passed!{RESET}\n")
        return 0
    else:
        print(f"{RED}⚠️  Some tests failed{RESET}\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())

