from src.tool.file_filter_support import *

# --- 1. Basic content search ---
print("=== 1. content: search for 'import re' ===")
results, flag, info = grep_impl({"pattern": "import re", "path": "..", "output_mode": "content"}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

# --- 2. Find matching file paths ---
print("\n=== 2. files_with_matches: search for 'import re' ===")
results, flag, info = grep_impl({"pattern": "import re", "path": "..", "output_mode": "files_with_matches"}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

# --- 3. Count matches ---
print("\n=== 3. count: search for 'import re' ===")
results, flag, info = grep_impl({"pattern": "import re", "path": "..", "output_mode": "count"}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

# --- 4. Glob filter ---
print("\n=== 4. glob: only search *.py files ===")
results, flag, info = grep_impl({"pattern": "import re", "path": "..", "glob": "*.py", "output_mode": "files_with_matches"}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

# --- 5. Type filter ---
print("\n=== 5. type: only search python files ===")
results, flag, info = grep_impl({"pattern": "import re", "path": "..", "type": "py", "output_mode": "files_with_matches"}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

# --- 6. Case-insensitive search ---
print("\n=== 6. ignore_case: search for 'IMPORT RE' (case-insensitive) ===")
results, flag, info = grep_impl({"pattern": "IMPORT RE", "path": "..", "output_mode": "content", "ignore_case": True}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

# --- 7. Context lines ---
print("\n=== 7. context: show 2 lines before and after each match ===")
results, flag, info = grep_impl({"pattern": "def main", "path": "../src/main.py", "output_mode": "content", "context": 2}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

# --- 8. Limit output with head_limit ---
print("\n=== 8. head_limit: limit to 2 lines ===")
results, flag, info = grep_impl({"pattern": "import", "path": "../src/main.py", "output_mode": "content", "head_limit": 2}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

# --- 9. head_limit=0 for unlimited output ---
print("\n=== 9. head_limit=0: unlimited output ===")
results, flag, info = grep_impl({"pattern": "import", "path": "../src/main.py", "output_mode": "content", "head_limit": 0}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

# --- 10. Regex pattern ---
print("\n=== 10. regex: search for re.compile(...) ===")
results, flag, info = grep_impl({"pattern": r"re\.compile\(r'.*'\)", "path": "..", "output_mode": "content"}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

# --- 11. Multiline matching ---
print("\n=== 11. multiline: cross-line match 'def main...main()' ===")
results, flag, info = grep_impl({"pattern": r"def main\(\):[\s\S]*?main\(\)", "path": "..", "output_mode": "content", "multiline": True}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

# --- 12. No matches ---
print("\n=== 12. no match: search for nonexistent pattern ===")
results, flag, info = grep_impl({"pattern": "nonexistent_xyz123", "path": "./any_path_no_exist", "output_mode": "content"}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

# --- 13. Search non-Python files ---
print("\n=== 13. JSON file search ===")
results, flag, info = grep_impl({"pattern": "version", "path": ".", "glob": "*.json", "output_mode": "content"}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

# --- 14. Search a specific file ---
print("\n=== 14. search specific file ===")
results, flag, info = grep_impl({"pattern": "def", "path": "../main.py", "output_mode": "content"}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

# --- 15. Count mode with head_limit ---
print("\n=== 15. count + head_limit ===")
results, flag, info = grep_impl({"pattern": "import", "path": "..", "output_mode": "count", "head_limit": 2}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

# --- 16. Search subdirectory ---
print("\n=== 16. search subdirectory ===")
results, flag, info = grep_impl({"pattern": "re", "path": "subdir", "output_mode": "files_with_matches"}, timeout=20)
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")


print("=== 1. Basic glob pattern: find all Python files ===")
results, flag, info = glob_impl({"pattern": "*.py"})
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

print("=== 2. Recursive glob: find all .py files in subdirectories ===")
results, flag, info = glob_impl({"pattern": "../src/**/*.py"})
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

print("=== 3. Glob with specific path ===")
results, flag, info = glob_impl({"pattern": "*.py", "path": "../src"})
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

print("=== 4. Glob with absolute path ===")
results, flag, info = glob_impl({"pattern": "**/*.json", "path": "C:/Users/admin/Desktop/PythonFile/TECoSimAgent/Agent"})
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

print("=== 5. Glob with multiple extension pattern ===")
results, flag, info = glob_impl({"pattern": "**/*.{py,js,json}", "path": "C:/Users/admin/Desktop/PythonFile/TECoSimAgent/Agent"})
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

print("=== 6. Glob with single character wildcard ===")
results, flag, info = glob_impl({"pattern": "bash_ris?_test.py"})
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

print("=== 7. Glob with numeric range pattern ===")
results, flag, info = glob_impl({"pattern": "file[0-9].txt"})
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

print("=== 8. Glob with character class ===")
results, flag, info = glob_impl({"pattern": "[a-z]*.py"})
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

print("=== 9. Glob with multiple directories depth ===")
results, flag, info = glob_impl({"pattern": "../**/*_test.py"})
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

print("=== 10. No matches found ===")
results, flag, info = glob_impl({"pattern": "nonexistent_pattern_xyz123"})
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

print("=== 11. Empty pattern (should fail) ===")
results, flag, info = glob_impl({"pattern": ""})
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")


print("=== 12. Find all Python files in current directory only (non-recursive) ===")
results, flag, info = glob_impl({"pattern": "*.py", "path": "."})
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

print("=== 13. Find all files with 'test' in name ===")
results, flag, info = glob_impl({"pattern": "**/*test*.py"})
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

print("=== 14. Globbing in home directory ===")
results, flag, info = glob_impl({"pattern": "*.txt", "path": os.path.expanduser("~")})
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")

print("=== 15. Pattern with double star in middle ===")
results, flag, info = glob_impl({"pattern": "../../**/src/*.py"})
print(f"results: {results}\n"
      f"flag: {flag}\n"
      f"info: {info}\n")
