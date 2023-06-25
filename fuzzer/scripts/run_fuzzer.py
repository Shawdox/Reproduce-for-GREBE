#Author: Xiao Wu
#Time: 2023.6.16
#Functionality:
#   Run the modified syskaller with a poc form analyzer.

import sys
import os
import json
assert ('linux' in sys.platform)
FUZZER_DIR = "/home/wx/Shaw/GREBE/fuzzer"
TEST_KERNEL_DIR = "/home/wx/Shaw/GREBE/analyzer/TestCases/case"
CASE_DIR = ""
IMAGE_DIR = "/home/wx/Shaw/GREBE/fuzzer/syzkaller_image"
DEBUG = 0

#set env
os.environ["KERNEL"] = TEST_KERNEL_DIR
os.environ["IMAGE"] = IMAGE_DIR

def redp(s:str):
    return "\033[0;31;40m{0}\033[0m".format(s)
    
def greenp(s:str):
    return "\033[0;32;40m{0}\033[0m".format(s)

if len(sys.argv[:]) != 2:
    print('The num of Args must be 1.Please specify the case version you want to test.')
    exit()
args = sys.argv[1]
CASE_DIR = TEST_KERNEL_DIR + args

#Find the compiled linux dir 
TEST_KERNEL_DIR += args + '/linux-gcc'
for s in os.listdir(TEST_KERNEL_DIR):
    if os.path.isdir(TEST_KERNEL_DIR+'/'+s):
        TEST_KERNEL_DIR += '/'+s
        break

#Build the syzkaller configure file
syzconfig = {
    "target": "linux/amd64",
	"http": "127.0.0.1:56741",
	"workdir": FUZZER_DIR + "/workdir",
	"kernel_obj": TEST_KERNEL_DIR,
	"image": IMAGE_DIR + "/bullseye.img",
	"sshkey": IMAGE_DIR + "/bullseye.id_rsa",
	"syzkaller": FUZZER_DIR,
	"procs": 8,
	"type": "qemu",
	"vm": {
		"count": 4,
		"kernel": TEST_KERNEL_DIR + "/arch/x86/boot/bzImage",
		"cpu": 2,
		"mem": 2048
	}
}
json.dump(syzconfig,open(CASE_DIR + '/syzconfig.cfg','w'),indent=4)

#Copy the poc to workdir
os.system("cp {0} {1}".format(CASE_DIR + '/poc.txt', FUZZER_DIR + "/workdir"))

#Run the fuzzer
cmd = "{0}/bin/syz-manager -config {1} --auxiliary {2}"\
        .format(FUZZER_DIR, CASE_DIR + '/syzconfig.cfg', 'poc.txt')
print(greenp('[RUN] '),cmd )
os.system(cmd)



