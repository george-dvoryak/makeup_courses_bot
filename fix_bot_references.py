#!/usr/bin/env python3
"""
Script to replace all bot. references with get_current_bot() in main.py
This helps migrate to multi-bot architecture.
"""

import re

def fix_bot_references():
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Track which functions we've already added current_bot to
    functions_with_bot = set()
    
    # Find all function definitions that use bot.
    # Pattern: @bot.decorator ... def function_name(...):
    pattern = r'(@bot\.(?:message_handler|callback_query_handler)[^\n]*\n(?:[^\n]*\n)*?def\s+(\w+)\s*\([^)]*\)\s*:)'
    
    matches = list(re.finditer(pattern, content, re.MULTILINE))
    
    # For each function, check if it uses bot. and add current_bot = get_current_bot() at the start
    for match in reversed(matches):  # Process in reverse to maintain positions
        func_name = match.group(2)
        func_start = match.end()
        
        # Find the function body (first non-empty line after def)
        body_match = re.search(r':\s*\n(\s*)', content[func_start:func_start+200])
        if not body_match:
            continue
        
        indent = body_match.group(1)
        
        # Check if this function uses bot.
        func_end = content.find('\n\n', func_start)
        if func_end == -1:
            func_end = len(content)
        
        func_body = content[func_start:func_end]
        
        if 'bot.' in func_body and func_name not in functions_with_bot:
            # Add current_bot = get_current_bot() at the start of function body
            insert_pos = func_start + body_match.end()
            insert_text = f"{indent}current_bot = get_current_bot()\n"
            
            # Check if current_bot is already defined
            if 'current_bot = get_current_bot()' not in func_body:
                content = content[:insert_pos] + insert_text + content[insert_pos:]
                functions_with_bot.add(func_name)
    
    # Now replace all bot. with current_bot. in function bodies (but not in decorators)
    # We'll do this carefully, only in function bodies
    
    # Replace bot. with current_bot. but skip decorators
    lines = content.split('\n')
    new_lines = []
    in_function = False
    indent_level = 0
    
    for i, line in enumerate(lines):
        # Check if this is a function definition
        if re.match(r'^\s*def\s+\w+\s*\(', line):
            in_function = True
            indent_level = len(line) - len(line.lstrip())
        elif re.match(r'^@bot\.', line):
            # Decorator - don't replace
            new_lines.append(line)
            continue
        elif line.strip() and not line.strip().startswith('#'):
            # Check if we're still in the same function
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= indent_level and in_function:
                in_function = False
        
        # Replace bot. with current_bot. only in function bodies
        if in_function and 'bot.' in line and not line.strip().startswith('@'):
            # Replace bot. with current_bot.
            line = re.sub(r'\bbot\.', 'current_bot.', line)
        
        new_lines.append(line)
    
    content = '\n'.join(new_lines)
    
    # Also replace standalone bot references (not bot.method)
    # But be careful - only in contexts where it makes sense
    # For now, let's just do bot. replacements
    
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Fixed bot references in main.py")
    print(f"Added current_bot = get_current_bot() to {len(functions_with_bot)} functions")

if __name__ == '__main__':
    fix_bot_references()

