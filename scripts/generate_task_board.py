import os
import re
import json

TASKS_DIR = "Tasks"
STATUSES = ["backlog", "in_progress", "completed"]

def extract_yaml_frontmatter(content):
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}
    
    yaml_text = match.group(1)
    data = {}
    for line in yaml_text.split('\n'):
        if ':' in line:
            key, val = line.split(':', 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            data[key] = val
    return data

def build_board():
    board_data = {status: [] for status in STATUSES}
    
    for status in STATUSES:
        dir_path = os.path.join(TASKS_DIR, status)
        if not os.path.exists(dir_path):
            continue
            
        for filename in os.listdir(dir_path):
            if filename.endswith(".md"):
                filepath = os.path.join(dir_path, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                meta = extract_yaml_frontmatter(content)
                if not meta:
                    continue
                
                # Try to get the first sentence for preview
                body = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)
                preview = body[:150].strip().replace('\n', ' ') + '...' if len(body) > 150 else body.strip().replace('\n', ' ')
                
                meta['preview'] = preview
                meta['filename'] = filename
                
                board_data[status].append(meta)
    
    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tasks Dashboard</title>
    <style>
        :root {{
            --bg: #0f172a;
            --column-bg: rgba(30, 41, 59, 0.7);
            --card-bg: rgba(51, 65, 85, 0.8);
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --border: rgba(255, 255, 255, 0.1);
            --accent: #3b82f6;
        }}
        
        body {{
            margin: 0;
            padding: 2rem;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg);
            background-image: radial-gradient(circle at 15% 50%, rgba(59, 130, 246, 0.15), transparent 25%),
                              radial-gradient(circle at 85% 30%, rgba(16, 185, 129, 0.15), transparent 25%);
            color: var(--text);
            min-height: 100vh;
        }}
        
        h1 {{
            margin-top: 0;
            margin-bottom: 2rem;
            font-weight: 700;
            text-align: center;
        }}
        
        .board {{
            display: flex;
            gap: 1.5rem;
            align-items: flex-start;
            overflow-x: auto;
            padding-bottom: 2rem;
        }}
        
        .column {{
            flex: 1;
            min-width: 320px;
            background: var(--column-bg);
            border-radius: 12px;
            padding: 1rem;
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        
        .column-header {{
            font-weight: 600;
            font-size: 1.1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .task-count {{
            background: rgba(255,255,255,0.1);
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.85rem;
        }}
        
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            position: relative;
        }}
        
        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            border-color: rgba(255,255,255,0.2);
        }}
        
        .card-id {{
            font-size: 0.75rem;
            color: var(--accent);
            font-weight: 700;
            margin-bottom: 0.5rem;
            display: inline-block;
            background: rgba(59, 130, 246, 0.1);
            padding: 2px 6px;
            border-radius: 4px;
        }}
        
        .card-title {{
            font-weight: 600;
            font-size: 0.95rem;
            margin-bottom: 0.5rem;
            line-height: 1.4;
        }}
        
        .card-preview {{
            font-size: 0.8rem;
            color: var(--text-muted);
            line-height: 1.5;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}
        
        a {{
            text-decoration: none;
            color: inherit;
        }}
    </style>
</head>
<body>
    <h1>⚡ Sagittarius Task Board</h1>
    <div class="board">
"""

    column_titles = {
        "backlog": "📋 Backlog",
        "in_progress": "🚀 In Progress",
        "completed": "✅ Completed"
    }

    for status in STATUSES:
        tasks = board_data[status]
        # Sort tasks by ID
        tasks.sort(key=lambda x: x.get('id', ''))
        
        html += f"""
        <div class="column">
            <div class="column-header">
                {column_titles[status]}
                <span class="task-count">{{len(tasks)}}</span>
            </div>
"""
        for task in tasks:
            task_id = task.get('id', 'N/A')
            title = task.get('title', 'Untitled')
            preview = task.get('preview', '')
            filename = task.get('filename', '')
            # Try to build vscode open file URL
            file_url = f"vscode://file/{os.path.abspath(os.path.join(TASKS_DIR, status, filename))}"
            
            html += f"""
            <a href="{file_url}" title="Click to open in VS Code">
                <div class="card">
                    <div class="card-id">{task_id}</div>
                    <div class="card-title">{title}</div>
                    <div class="card-preview">{preview}</div>
                </div>
            </a>
"""
        html += """
        </div>
"""
        
    html += """
    </div>
</body>
</html>
"""

    out_path = os.path.join(TASKS_DIR, "dashboard.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
        
    print(f"Generated dashboard at {out_path}")

if __name__ == "__main__":
    build_board()
