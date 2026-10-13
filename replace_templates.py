import re
import new_html

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. replace system_status text
content = content.replace(
    '"text": "Database is empty. Please register your face."',
    '"text": "No registered profiles found. Please register."'
)

# 2. redirect login to scanner
content = content.replace(
    "return redirect(url_for('login_page'))",
    "return redirect(url_for('scanner'))"
)

# Replace HTML_TEMPLATE
start = content.find('HTML_TEMPLATE = """')
end = content.find('"""\n\n@app.route(\'/\')', start)
if start != -1 and end != -1:
    content = content[:start] + 'HTML_TEMPLATE = """\n' + new_html.HTML_TEMPLATE + '\n' + content[end:]
else:
    print("Could not find HTML_TEMPLATE boundaries")

# Replace LOGIN_TEMPLATE
start2 = content.find('LOGIN_TEMPLATE = """')
end2 = content.find('"""\n\n# Guard login', start2)
if start2 != -1 and end2 != -1:
    content = content[:start2] + 'LOGIN_TEMPLATE = """\n' + new_html.LOGIN_TEMPLATE + '\n"""\n\nGUARD_LOGIN_TEMPLATE = """\n' + new_html.GUARD_LOGIN_TEMPLATE + '\n' + content[end2:]
else:
    print("Could not find LOGIN_TEMPLATE boundaries")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated app.py!")
