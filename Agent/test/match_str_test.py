from src.tool import edit_file_support

content = ("a\n"
           "a\n"
           "a\n"
           "a\n"
           "a\n"
           "a\n"
           "a\n"
           "a\n"
           "a\n")

string = "a\na"
results = edit_file_support.match_line_ranges(content, string, True)
print("Matches", results)
print("Interval", edit_file_support.merge_intervals(results))

content = ("Hello World\n"
           "1\n"
           "2\n"
           "3\n"
           "4\n"
           "Hello World\n"
           "a\n"
           "b\n"
           "Hello World\n")
content_lines = content.splitlines()

string = "Hello World"
results = edit_file_support.match_line_ranges(content, string, False)
print("Matches", results)

results = edit_file_support.match_line_ranges(content, string, True)
print("Matches", results)
print("Interval", edit_file_support.merge_intervals(results))

string = "Hello World\n"
results = edit_file_support.match_line_ranges(content, string, True)
print("Matches", results)

string = "\n"
results = edit_file_support.match_line_ranges(content, string, True)
print("Matches", results)
