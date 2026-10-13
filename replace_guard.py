import re
import guard_html

with open('guard.py', 'r', encoding='utf-8') as f:
    content = f.read()

start = content.find('HTML_GUARD_STATION = """')
end = content.find('"""\n\n@guard_bp.route(\'/\')', start)

if start != -1 and end != -1:
    content = content[:start] + guard_html.HTML_GUARD_STATION + '\n' + content[end + 4:]
    with open('guard.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Updated guard.py successfully!")
else:
    print("Could not find boundaries in guard.py", start, end)

