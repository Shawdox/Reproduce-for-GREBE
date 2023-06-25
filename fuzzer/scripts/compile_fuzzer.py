#Author: Xiao Wu
#Time: 2023.6.16
#Functionality:
#   Complie the modified syzkaller

import sys
import os
assert ('linux' in sys.platform)

GO_DIR = "/home/wx/Shaw/go"
FUZZ_DIR = "/home/wx/Shaw/GREBE/fuzzer"

os.environ["PATH"] += GO_DIR+"/bin"
os.chdir(FUZZ_DIR)
os.system("make")
