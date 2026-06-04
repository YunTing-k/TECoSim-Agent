from src.tool.summarize_support import get_field


test_cases = [
    # === Normal cases (Method 1: direct parsing) ===
    {
        "input": '{"title": "Fix login button"}',
        "expected": "Fix login button",
        "desc": "Standard JSON, direct parsing"
    },

    # === JSON embedded in text ===
    {
        "input": 'Summary: {"title": "Debug API timeout"} End.',
        "expected": "Debug API timeout",
        "desc": "JSON embedded in plain text"
    },
    {
        "input": '```json\n{"title": "Add OAuth support"}\n```',
        "expected": "Add OAuth support",
        "desc": "Wrapped in markdown code block"
    },

    # === Nested dictionary with title ===
    {
        "input": '{"data": {"title": "Refactor database layer"}, "status": "ok"}',
        "expected": "Refactor database layer",
        "desc": "Title in nested dictionary"
    },

    # === Special characters: escaped quotes ===
    {
        "input": '{"title": "Fix \\"remember me\\" checkbox"}',
        "expected": 'Fix "remember me" checkbox',
        "desc": "Title value contains escaped quotes"
    },

    # === Special characters: curly braces in title value ===
    {
        "input": '{"title": "Handle {placeholder} in templates"}',
        "expected": "Handle {placeholder} in templates",
        "desc": "Title value contains curly braces"
    },

    # === Special characters: escaped newline and tab ===
    {
        "input": '{"title": "Fix\\n multi-line\\t display"}',
        "expected": "Fix\n multi-line\t display",
        "desc": "Title value contains escaped newline and tab"
    },

    # === Multiple JSON objects, take the first valid one with title ===
    {
        "input": 'First: {"what": "Fake title title here"} Second: {"name": "test"} Third: {"title": "Real title title title here"}',
        "expected": "Real title title title here",
        "desc": "Multiple JSON objects, second one contains title"
    },

    # === Title is not a string (should return None) ===
    {
        "input": '{"title": 12345}',
        "expected": "12345",
        "desc": "Title value is not a string, should return string"
    },

    # === Not in JSON format ===
    {
        "input": 'title: What is this?',
        "expected": "What is this?",
        "desc": "Title is not in JSON format"
    },

    # === No title field at all ===
    {
        "input": '{"name": "test", "value": 42}',
        "expected": None,
        "desc": "JSON has no title field at all"
    },

    # === Edge cases: empty input ===
    {
        "input": None,
        "expected": None,
        "desc": "Input is None"
    },
    {
        "input": "",
        "expected": None,
        "desc": "Input is empty string"
    },
]

# Run tests
print("Testing get_title():\n" + "=" * 60)
all_passed = True

for i, case in enumerate(test_cases, 1):
    result = get_field(case["input"])
    passed = result == case["expected"]
    if not passed:
        all_passed = False

    status = "✅" if passed else "❌"
    print(f"{status} Test {i}: {case['desc']}")
    print(f"   Input:    {case['input']!r}")
    print(f"   Expected: {case['expected']!r}")
    print(f"   Got:      {result!r}")
    print()

print("=" * 60)
print("✅ All tests passed!" if all_passed else "❌ Some tests failed!")
