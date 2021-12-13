import os
import random
import sys
import glob
import time
import logging
import shutil
import hashlib
 
def hash_string(input):
    byte_input = input.encode()
    hash_object = hashlib.sha256(byte_input)
    return hash_object
 
def update_hash(hash_object, input_str):
    # Adds the string to the hash string
    hash_object.update(input_str.encode())

from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler
from watchdog.events import FileSystemEventHandler

cat = lambda f : [print(l, end='') for l in open(f)]		
rm = lambda path : [os.remove(f) for f in glob.glob(path)]
TMP = os.environ['TMP']

def file_move(src, dst):
	# we need to use os.replace to avoid weird stalling scenearious
	# where rose is reading the dll before it is written.
	# os.replace is atomic. https://docs.python.org/3/library/os.html#os.replace
	try:
		os.replace(src, dst)
	except (IOError, OSError) as error:
		shutil.move(src, dst + ".rose_tmp")
		os.replace(dst + ".rose_tmp", dst)
	pass

def execute(cmd):
	print("EXECUTING:", cmd)
	return os.system(cmd)

def compile(compiler, cfiles, defines=[], target="exe", includes=["."], output_file="."):
	#Target name based on input hashes
	#https://www.askpython.com/python-modules/python-hashlib-module
	hash_object = hash_string(compiler)
	[update_hash(hash_object, s) for s in [output_file, target]]
	[update_hash(hash_object, s) for s in includes]
	[update_hash(hash_object, s) for s in defines]
	[update_hash(hash_object, s) for s in cfiles]

	rand = hash_object.hexdigest()

	PDB_NAME=f'{TMP}/ROSE_{rand}.pdb'
	APP_NAME=f'{TMP}/ROSE_{rand}.{target}'

	arg_c_files = " ".join(["./" + D for D in cfiles])
	arg_defines = " ".join(["/D" + D for D in defines])

	CPP_FILE=C_FILES[-1]

	INCLUDES=" ".join(["/I " + I for I in includes])

	# Faster builds: https://devblogs.microsoft.com/cppblog/recommendations-to-speed-c-builds-in-visual-studio/
	print(f'compiling {CPP_FILE}')
	#CL /nologo /MP /O1 /std:c++17 /wd"4530" /LD /MD /I third_party/maths /I R:/rose/include /Fe%output_file% %CPP_FILE% source\roseimpl.cpp
	#TODO: check target == exe or dll
	#error = os.system(f'CL /nologo /MP /std:c++17 /wd"4530" /Zi /LD /MD {INCLUDES} /Fe{output_file} {CPP_FILE} source/roseimpl.cpp R:/rose/.build/bin/DebugFast/raylib.lib /link /incremental /PDB:"{PDB_NAME}" > %TMP%/clout.txt')
	dll_stuff = "/LD /MD"
	error = execute(f'{compiler} /nologo /MP /std:c++17 /wd"4530" {arg_defines} /Zi {dll_stuff} {INCLUDES} /Fe:"{APP_NAME}" {arg_c_files} R:/rose/.build/bin/Release/raylib.lib R:/rose/.build/bin/Release/imgui.lib /link /incremental /PDB:"{PDB_NAME}" > {TMP}/clout.txt')

	if error:
		print("~~~~~~~~~~~")
		print("~~ ERROR ~~")
		print("~~~~~~~~~~~")
		cat(TMP + "/clout.txt")
		print("")
	else:
		file_move(APP_NAME,output_file)
		print(f"							 ~~ OK ~~")

	return error


INCLUDE_ARRAY = [
	"."
	,"../rose/externals/include"
	,"../rose/externals/include/imgui"
	,"../rose/externals/roselib/include"
	,"../rose/externals/raylib/src"
	,"../rose/externals/premake-comppp/include/"

]

C_FILES = [
	"system.editor.cpp",
	"crude_json.cpp",
	"imgui_canvas.cpp",
	"imgui_node_editor.cpp",
	"imgui_node_editor_api.cpp",
	"../rose/source/systems/source/roseimpl.cpp"
]

DEFINES = [
	"IMGUI_API=__declspec(dllimport)"
]

output_file = "."

#remove any non alpha numeric characters from string
def remove_non_alpha(string):
    return ''.join(char for char in string if char.isalpha())


#a class called MyClass than inherits from watchdog.events.FileSystemEventHandler and implements on_modified
class MyClass(FileSystemEventHandler):
	def __init__(self, files):
		#call the constructor of the parent class
		FileSystemEventHandler.__init__(self)
		#initialize the array of files
		self.files = files

	def on_modified(self, event):
		#check if self.files contains any of event.src_path
		#print("on_modified", event.src_path)

		if remove_non_alpha(event.src_path) in (remove_non_alpha(f) for f in self.files):
			#print the file name
			print("recompile", event.src_path)
			compile("CL", includes=INCLUDE_ARRAY, defines=DEFINES, target="dll", cfiles=C_FILES, output_file=output_file)

if __name__ == "__main__":
	watch = False

	for i in range(1, len(sys.argv)):
		arg = sys.argv[i]
		output_file = arg
		if arg == "--watch" or arg == "-W":
			watch = True

	compile("CL", includes=INCLUDE_ARRAY, defines=DEFINES, target="dll", cfiles=C_FILES, output_file=output_file)

	if watch:
		logging.basicConfig(level=logging.INFO,
							format='%(asctime)s - %(message)s',
							datefmt='%Y-%m-%d %H:%M:%S')
		path = "."
		#event_handler = LoggingEventHandler()
		event_handler = MyClass(C_FILES)
		observer = Observer()
		observer.schedule(event_handler, path, recursive=False)
		observer.start()
		try:
			while True:
				time.sleep(1)
		except KeyboardInterrupt:
			observer.stop()
		observer.join()
