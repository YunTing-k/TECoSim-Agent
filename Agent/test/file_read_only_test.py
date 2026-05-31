from src.tool.file_io_support import AgentContext, Path, check_read_only

ctx = AgentContext()

test_path = Path("./AABBCC")
print(test_path.exists())
print(test_path.resolve())

test_path = Path("C:/AABBCC")
print(test_path.exists())
print(test_path.resolve())

print(Path("./AABBCC/ccdd").resolve().is_relative_to(Path("./AABBCC/").resolve()))

ctx.system_read_only_paths.append(Path("./"))
ctx.system_read_only_paths.append(Path("C:/Users/admin/Desktop/C++File/Project/TECoSim"))
ctx.read_only_paths.append(Path("../src"))

print([c.name for c in ctx.system_read_only_paths])
print([c.name for c in ctx.read_only_paths])

print(check_read_only("../", ctx))
print(check_read_only("AABBCC", ctx))
print(check_read_only("C:/Users/admin/Desktop/PythonFile/TECoSimAgent/Agent/src/", ctx))
print(check_read_only("C:\\Users\\admin\\Desktop\\PythonFile\\TECoSimAgent\\Agent\\src", ctx))
print(check_read_only("C:/Users/admin/Desktop/PythonFile/TECoSimAgent/Agent/", ctx))
print(check_read_only("C:/Users/admin/Desktop/PythonFile/TECoSimAgent/Agent/test/file_read_only_test.py", ctx))
print(check_read_only("C:/Users/admin/Desktop/C++File/Project/TECoSim/doc/TECoSim_Project_Summary.md", ctx))
