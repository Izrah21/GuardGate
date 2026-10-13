import re
import os

def update_file(filename, replacements):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old_str, new_str in replacements:
        if old_str in content:
            content = content.replace(old_str, new_str)
        else:
            print(f"Warning: could not find snippet in {filename}: {old_str[:30]}")

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

app_replacements = [
    (
        '"text": "Database is empty. Please register your face."',
        '"text": "No registered profiles found. Please register."'
    ),
    (
        "return redirect(url_for('login_page'))",
        "return redirect(url_for('scanner'))"
    )
]

update_file("app.py", app_replacements)

# For the large string, I will read it from another file I create here

import new_html

def regex_replace(filename, pattern, replacement):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

# We need to correctly substitute HTML_TEMPLATE and LOGIN_TEMPLATE.
# Notice that the regex should match the exact old code structure
# But to be safe, I'll just use string replacement on the prefix.

