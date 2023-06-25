#Author: Xiao Wu
#Time: 2023.6.15
#Functionality:
#   According to the .config file corresponding to 
#   the bug report in syzbot, download the corresponding 
#   kernel version and compile with gcc for a runable one
#   which is uesd by syzkaller.

import requests
import sys
import re
import wget
import os
import filecmp
assert ('linux' in sys.platform)

def redp(s:str):
    return "\033[0;31;40m{0}\033[0m".format(s)
    
def greenp(s:str):
    return "\033[0;32;40m{0}\033[0m".format(s)

#Kernel download site
URL_PREFIX = "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/snapshot/linux-"
#Root
ROOT_DIR = "/home/wx/Shaw/GREBE"
#A testcase include a report and its .config file
CASE_DIR = "/home/wx/Shaw/GREBE/analyzer/TestCases/case"
#Determining kernel version
PATTERN1 = re.compile(r'\d.\d+.\d+(-rc\d)? Kernel Configuration')
#Location of patched LLVM
#PATCHED_LLVM = '/home/wx/Shaw/llvm/patched_llvm'
#PATCHED_LLVM = '/home/wx/Shaw/llvm/patched_llvm_11'
GCC = "/home/wx/Shaw/GREBE/gcc-9.3.0/gcc-bin/bin/gcc"
DEBUG = 0

if not DEBUG :
    if len(sys.argv[:]) != 2:
        print('The num of Args must be 1.Please specify the case version you want to test.')
        exit()
    args = sys.argv[1]
else:
    args = '3'

#Get kernel version form .config
CASE_DIR = CASE_DIR + args
with open(CASE_DIR +'/.config','r') as config:
    print(greenp('[Get .config] '),config.name)
    line = config.readline()
    while line:
        version = re.search(PATTERN1,line)
        if version != None:
            print(greenp('[Match Version] '),version.group())
            version = version.group()
            break
        line = config.readline()
        
    if version == None:
        print(redp('[Error .conifg] '),'No version info in .config')
        exit()
    
    else:
        version = str(version).replace(' Kernel Configuration','')
        version = re.sub(r'.0',"",version)
        URL = URL_PREFIX + version + '.tar.gz'
        
#Download kernel file
if not os.path.exists(CASE_DIR+'/linux-gcc/'):
    os.mkdir(CASE_DIR+'/linux-gcc/')

flist = os.listdir(CASE_DIR+'/linux-gcc/')
if not len(flist):
    print(greenp('[Download] Downloading from '),URL)
    filename = wget.download(URL,CASE_DIR+'/linux-gcc/')
    print(greenp('[Download] Download file: '),filename)

else:
    print(redp('[INFO] '),'The following files exist in the folder:')
    print(flist)


#Unzip
PAHT_LOG=os.path.dirname(os.path.abspath(__file__))
print(greenp('[Current pwd] '),PAHT_LOG)
op = input(greenp('[Choose] ')+'[0/1]unzip the tar.gz file?')
#unzip_dir = 'linux-'+version
unzip_dir = 'linux-'+version

if op == '1':
    os.chdir(CASE_DIR+'/linux-gcc/')
    os.system("tar -zxvf *.tar.gz") 
    print(greenp('[Change pwd] '),os.getcwd())
  
    #Configuration
    print(greenp('[Configuration] '),'Copy {} to {}'\
        .format(CASE_DIR+'/.config',CASE_DIR+'/'+unzip_dir))
    os.system('cp {0} {1}'\
        .format(CASE_DIR+'/.config',CASE_DIR+'/linux-gcc/'+unzip_dir))
    #Check the .config file
    if not filecmp.cmp(CASE_DIR+'/.config',\
        CASE_DIR+'/linux-gcc/'+unzip_dir+'/.config'):
        print(redp('[Error] '),'.config error!')
        exit()
        
    #Patch kernel to support object coverage feedback
    os.system("patch {}/kernel/kcov.c -p1 < {}/kernel.patch"\
            .format(CASE_DIR+'/linux-gcc/'+unzip_dir,ROOT_DIR))

#Compile the kernel
op = input(greenp('[Choose] ')+'[0/1]build the kernel with GCC?')
if op == '1':
    os.chdir(CASE_DIR+'/linux-gcc/'+unzip_dir)
    print(greenp('[Change pwd] '),os.getcwd())
    #os.system("make clean")
    os.system("export OBJ_FILE={}".format(CASE_DIR+"/sts.txt"))
    os.system("make CC={} -j`nproc`".format(GCC))

