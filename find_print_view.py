import re

path = "orders/views.py"

with open(path, "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

# Look for likely function/class names for the print/pull sheet endpoint
candidates = re.findall(r"(def\s+\w*print\w*\s*\(.*?\):|class\s+\w*[Pp]rint\w*.*?:)", content)
candidates += re.findall(r"(def\s+\w*pull\w*sheet\w*\s*\(.*?\):|class\s+\w*[Pp]ull[Ss]heet\w*.*?:)", content)

print("=" * 70)
print("Candidate matches for the pull sheet / print view in orders/views.py")
print("=" * 70)
if not candidates:
    print("No matches found for 'print' or 'pullsheet' patterns.")
    print("Try searching manually: Select-String -Path orders/views.py -Pattern 'def.*print'")
else:
    for c in candidates:
        print(c)
print("=" * 70)
