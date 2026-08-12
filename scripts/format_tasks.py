import os
import re

TASKS_DIR = "Tasks"
STATUSES = ["backlog", "in_progress", "completed"]

def format_file(filepath, status):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # If already has YAML frontmatter, skip
    if content.startswith("---\n"):
        return
        
    filename = os.path.basename(filepath)
    # Extract ID from filename if possible (e.g., BOT-023)
    id_match = re.match(r'^([A-Z]+-\d+)', filename)
    task_id = id_match.group(1) if id_match else "UNKNOWN"
    
    # Extract Title from first # Header or filename
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
    else:
        title = filename.replace('.md', '').replace('_', ' ')
        
    # Build YAML frontmatter
    yaml = f"---\n"
    yaml += f"id: \"{task_id}\"\n"
    yaml += f"title: \"{title}\"\n"
    yaml += f"status: \"{status}\"\n"
    yaml += f"---\n\n"
    
    # Prepend YAML to content
    new_content = yaml + content
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"Formatted: {filepath}")

def main():
    for status in STATUSES:
        dir_path = os.path.join(TASKS_DIR, status)
        if not os.path.exists(dir_path):
            continue
            
        for filename in os.listdir(dir_path):
            if filename.endswith(".md"):
                filepath = os.path.join(dir_path, filename)
                format_file(filepath, status)
                
if __name__ == "__main__":
    main()
