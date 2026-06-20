import os
import shutil
import re

PROJECTS_DIR = "projects"
DOCS_DIR = "documents"

TARGET_PROJECTS = {
    "wbc-analyzer": "WBC Analyzer",
    "kinematic": "Kinematic Action Recognition",
    "listing-pilot": "Listing Pilot",
    "popcorn-wagon": "Popcorn Wagon",
    "portal-cleaner-ultimate": "Portal Cleaner Ultimate"
}

def extract_comments_and_docstrings(filepath):
    """
    Extract docstrings and inline comments from a Python file.
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return ""

    comments = []
    
    # 1. Extract block comments/docstrings: """ ... """ and ''' ... '''
    docstring_pattern = r'(?:"{3}([\s\S]*?)"{3}|\'{3}([\s\S]*?)\'{3})'
    matches = re.finditer(docstring_pattern, content)
    for match in matches:
        doc = match.group(1) or match.group(2)
        if doc and doc.strip():
            comments.append(f"--- Docstring ---\n{doc.strip()}\n")
            
    # 2. Extract inline comments starting with '#' (excluding shebang)
    lines = content.splitlines()
    inline_comments = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#!"):
            continue
        if stripped.startswith("#"):
            comment_text = stripped.lstrip("#").strip()
            if comment_text:
                inline_comments.append(comment_text)
                
    if inline_comments:
        comments.append("--- Code Comments ---\n" + "\n".join(inline_comments) + "\n")
        
    return "\n".join(comments)

def main():
    if os.path.exists(DOCS_DIR):
        try:
            shutil.rmtree(DOCS_DIR)
        except Exception as e:
            print(f"Could not clear documents directory: {e}")
    os.makedirs(DOCS_DIR, exist_ok=True)
    
    for folder_name, project_title in TARGET_PROJECTS.items():
        project_path = os.path.join(PROJECTS_DIR, folder_name)
        if not os.path.isdir(project_path):
            print(f"Directory {project_path} not found. Skipping...")
            continue
            
        print(f"Processing project: {project_title}...")
        
        # 1. Copy README.md
        readme_path = os.path.join(project_path, "README.md")
        if os.path.exists(readme_path):
            target_readme = os.path.join(DOCS_DIR, f"{folder_name}_README.md")
            shutil.copy2(readme_path, target_readme)
            print(f"  Copied README to {target_readme}")
        else:
            print(f"  Warning: README.md not found in {project_path}")
            
        # 2. Scan and extract comments from all python files
        project_comments = []
        for root, dirs, files in os.walk(project_path):
            if "venv" in root or ".git" in root or "__pycache__" in root:
                continue
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, project_path)
                    
                    file_comments = extract_comments_and_docstrings(full_path)
                    if file_comments.strip():
                        project_comments.append(f"=== File: {rel_path} ===\n{file_comments}\n")
                        
        if project_comments:
            comments_file_path = os.path.join(DOCS_DIR, f"{folder_name}_code_comments.txt")
            with open(comments_file_path, "w", encoding="utf-8") as f:
                f.write(f"# Important Comments and Docstrings from {project_title}\n\n")
                f.write("\n".join(project_comments))
            print(f"  Extracted comments to {comments_file_path}")

if __name__ == "__main__":
    main()