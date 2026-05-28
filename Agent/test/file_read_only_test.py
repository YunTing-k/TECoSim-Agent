from src.tool.file_io_support import AgentContext, Path, check_read_only

ctx = AgentContext()

ctx.system_read_only_paths.append(Path("./"))
ctx.read_only_paths.append(Path("../src"))

print([c.name for c in ctx.system_read_only_paths])
print([c.name for c in ctx.read_only_paths])

print(check_read_only("../", ctx))
print(check_read_only("AABBCC", ctx))
print(check_read_only("C:/Users/admin/Desktop/PythonFile/TECoSimAgent/Agent/src/", ctx))
print(check_read_only("C:\\Users\\admin\\Desktop\\PythonFile\\TECoSimAgent\\Agent\\src", ctx))
print(check_read_only("C:/Users/admin/Desktop/PythonFile/TECoSimAgent/Agent/", ctx))
print(check_read_only("C:/Users/admin/Desktop/PythonFile/TECoSimAgent/Agent/test/file_read_only_test.py", ctx))
