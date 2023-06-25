---
title: (论文复现)GREBE-Unveiling Exploitation Potential for Linux Kernel Bugs
author: Shaw
categories: Paper
tags: ["Vulnerability" , "AEG" ]

---

# (论文复现)GREBE: Unveiling Exploitation Potential for Linux Kernel Bugs

源码：[Markakd/GREBE (github.com)](https://github.com/Markakd/GREBE)

# 1. Analysis

## 1.1 Critical Structure Identification

### 1.1.1 **report来源：**

​	syzbot是一个基于syzkaller的自动化fuzzing系统。它能持续不停的运行syzkaller，对linux内核各个分支进行模糊测试，自动报告crash，监控bug的当前状态（是否已被修复等），监测对于bug的patch是否有效，完成发现-报告-复现-修复的整个流程。

<img src="https://shaw-typora.oss-cn-beijing.aliyuncs.com/20230410171230.png" alt="syzbot报告的错误列表" style="zoom:80%;" />

​	对每个错误，syzbot会发布其对应的报告以及可能存在的POC程序：

![某个错误报告](https://shaw-typora.oss-cn-beijing.aliyuncs.com/20230615150648.png)

​	如上图所示，syzbot发布了某个错误发生时其对应的寄存器内容，call trace以及3次crashes（底部）的对应信息，可以看到，该错误提供了一个syz脚本编写的reproducer，也就是Poc程序。

​	syzkaller repro是用特殊的syzkaller符号编写的程序，它们可以在目标系统上执行。并且，syzkaller repro可以转化为对应的C语言poc，如果syzbot没有提供C语言的repro，它就无法使用C语言程序来触发该错误（这可能只是因为该错误是由一个竞态条件触发的）。

​	GREBE就是从这些报告中提取call trace进行后续分析。

### 1.1.2 编译Analyzer

​	安装llvm–10（[LLVM Debian/Ubuntu packages](https://apt.llvm.org/)）：

```bash
#To install a specific version of LLVM:
wget https://apt.llvm.org/llvm.sh
chmod +x llvm.sh
sudo ./llvm.sh <version number>
```

​	clang-10被安装在`/usr`中，故将analyer的make文件修改来指定clang，如下（这里直接指定C与C++编译器）：

```makefile
CUR_DIR = $(shell pwd)
SRC_DIR := ${CURDIR}/src
BUILD_DIR := ${CURDIR}/build

include Makefile.inc

NPROC := ${shell nproc}

build_ka_func = \
	(mkdir -p ${2} \
		&& cd ${2} \
        &&    cmake ${1} \
				-DCMAKE_CXX_COMPILER=/home/wx/Shaw/llvm/patched_llvm/bin/clang++\
				-DCMAKE_C_COMPILER=/home/wx/Shaw/llvm/patched_llvm/bin/clang\
                -DCMAKE_BUILD_TYPE=Release \
                -DCMAKE_CXX_FLAGS_RELEASE="-std=c++14 -fno-rtti -fpic -g" \
		&& make -j${NPROC})

all: analyzer

analyzer:
	$(call build_ka_func, ${SRC_DIR}, ${BUILD_DIR})
```

​	接着修改analyzer/src中的CMakeLists.txt文件来指定LLVM：

```cmake
cmake_minimum_required(VERSION 2.8.8)
project(KANALYZER)
#指定LLVM版本
set(LLVM_DIR "/home/wx/Shaw/llvm/patched_llvm/lib/cmake/llvm")

find_package(LLVM REQUIRED CONFIG)

message(STATUS "Found LLVM ${LLVM_PACKAGE_VERSION}")
message(STATUS "Using LLVMConfig.cmake in: ${LLVM_DIR}")

# Set your project compile flags.
# E.g. if using the C++ header files
# you will need to enable C++14 support
# for your compiler.
# Check for C++14 support and set the compilation flag
include(CheckCXXCompilerFlag)
#CHECK_CXX_COMPILER_FLAG("-std=c++14" COMPILER_SUPPORTS_CXX14)
# if(COMPILER_SUPPORTS_CXX14)
# 	set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14 -fno-rtti -fPIC -Wall")
# else()
# 	message(STATUS "The compiler ${CMAKE_CXX_COMPILER} has no C++14 support. Please use a different C++ compiler.")
# endif()

include_directories(${LLVM_INCLUDE_DIRS})
add_definitions(${LLVM_DEFINITIONS})

add_subdirectory (lib)
```

​	编译好的analyer位于GREBE/analyzer/build/lib中。

### 1.1.3 编译内核bitcode文件

#### 1.1.3.1 安装带补丁的LLVM

​	内核bitcode文件指的是待测试的Linux内核，需要将其编译为bc文件后进行分析。

​	这里需要使用llvm-10并且给LLVM编译器打上补丁，以便在调用任何编译器优化通道之前转储比特码。通过这种方式，可以防止编译器优化影响分析的准确性。<u>故这里单独准备一个llvm并安装到特定文件夹中，以避免对全局llvm的影响：</u>

```shell
git clone https://github.com/llvm/llvm-project
cd llvm-project
git checkout 5521236a18074584542b81fd680158d89a845fca
```

​	打补丁：

```shell
patch -p0 < WriteBitcode.patch
```

<img src="https://shaw-typora.oss-cn-beijing.aliyuncs.com/20230531152450.png" style="zoom: 50%;" />

​	build clang:

```shell
mkdir build && cd build
cmake -DCMAKE_INSTALL_PREFIX=/home/wx/Shaw/llvm/patched_llvm -DLLVM_ENABLE_PROJECTS=clang -DCMAKE_BUILD_TYPE=Release  -G "Unix Makefiles" ../llvm
sudo make -j$(nproc) && make install
```

​	这里通过指定`DCMAKE_INSTALL_PREFIX`的方式指定其安装位置。注意，LLVM编译后体积非常大，如果在虚拟机中编译需要给足够内存和硬盘空间（80G+）。



#### 1.1.3.2 编译内核

​	编译安装完带有特定补丁的LLVM，接下来就需要使用其来编译Linux内核源码。

​	以[KASAN: slab-use-after-free Read in hfsplus_read_wrapper](https://syzkaller.appspot.com/bug?extid=4b52080e97cde107939d)为例，其附带的.config文件中详细的说明了漏洞的内核版本、config编译选项等信息：

<img src="https://shaw-typora.oss-cn-beijing.aliyuncs.com/20230531202020.png" style="zoom: 67%;" />

​	在[kernel/git/torvalds/linux.git - Linux kernel source tree](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/refs/tags)处下载对应版本的内核源码，解压后先安装编译所需的包：

```bash
sudo apt-get install git fakeroot build-essential ncurses-dev xz-utils libssl-dev bc flex libelf-dev bison
```

​	使用如下命令编译,`CC`和`CXX`指定为带补丁的clang，由于LLVM-10存在一定bug，这里令`LLVM_IAS`为0关闭**integrated assembler**：

```bash
make CC=/home/wx/Shaw/llvm/patched_llvm/bin/clang CXX=/home/wx/Shaw/llvm/patched_llvm/bin/clang++ LLVM_IAS=0 all -j$(nproc) 
```

​	analyzer编译完成后，使用如下命令运行：

```bash
python run_analyze.py ./case
```

​	可以在对应case目录下看到对应的解析结果`sys.txt`：

<img src="https://shaw-typora.oss-cn-beijing.aliyuncs.com/20230615150924.png" style="zoom: 50%;" />

​	注意：

>1. **编译analyzer与源码的LLVM一定要是相同版本的；**
>
>2. **作者给出的LLVM-10是可以成功运行的，但是存在的问题如下：**
>
>   a. 目前使用LLVM编译新版本的内核最低要求其版本为11，其无法编译内核；
>
>   b. 如果使用LLVM-11，其编译analyzer存在错误（见文末错误日志）；
>
>   <u>故目前作者仓库中给出的代码仅适合版本不高的内核。</u>
>
>3. **部分工作已通过脚本自动化，整个内核的下载+解压+编译已自动化为`/analyzer/scripts/get_kernel.py`，复现analyzer需要：**
>
>   a. 在/analyzer/Testcase/下创建对应case文件夹，命名格式为case+数字；
>
>   b. 将对应report中的.config文件与report文件以名称`.config`和`report`复制到case文件夹中；
>
>   c. 修改/analyzer/scripts/下的三个py文件中的`CASE_DIR`，`PATCHED_LLVM `和`AnalyzerPath`变量，使其分别对应Testcase，打过补丁的LLVM和编译好的analyzer；
>
>   d. 按次序运行`get_cg.py`、`get_kernel.py`和`run_analyze.py`，其参数为case序号，例如：
>
>   ```bash
>   #分析/analyzer/Testcases/case7
>   python get_cg.py 7
>   python get_kernel.py 7
>   python run_analyze.py 7
>   ```



### 1.1.3  静态分析代码解析

​	见[(代码分析)GREBE-Analyzer污点分析代码解析 | Shaw (shawdox.github.io)](https://shawdox.github.io/2023/05/09/[代码分析]GREBE-Analyzer污点分析代码解析/)



# 2. Fuzzing



# 3. 错误日志

- **问题1：编译llvm时报错：**

  >Killed (program cc1plus)
  >Please submit a full bug report,
  >with preprocessed source if appropriate.
  >See <file:///usr/share/doc/gcc-5/README.Bugs> for instructions.
  >lib/DebugInfo/CodeView/CMakeFiles/LLVMDebugInfoCodeView.dir/build.make:494: recipe for target 'lib/DebugInfo/CodeView/CMakeFiles/LLVMDebugInfoCodeView.dir/EnumTables.cpp.o' failed
  >make[2]: *** [lib/DebugInfo/CodeView/CMakeFiles/LLVMDebugInfoCodeView.dir/EnumTables.cpp.o] Error 4
  >CMakeFiles/Makefile2:6769: recipe for target 'lib/DebugInfo/CodeView/CMakeFiles/LLVMDebugInfoCodeView.dir/all' failed
  >make[1]: *** [lib/DebugInfo/CodeView/CMakeFiles/LLVMDebugInfoCodeView.dir/all] Error 2

**解决方法：**

编译时虚拟机的内存与硬盘空间太小，在服务器上跑即可成功编译。

![](https://shaw-typora.oss-cn-beijing.aliyuncs.com/20230615151312.png)

  

- **问题2：在编译analyzer时报错：**

  > error: no member named 'hasNPredecessorsOrMore' in 'llvm::BasicBlock'

- **解决方法：**

  查看错误报告发现是LLVM的BasicBlock没找到对应的子数据结构`hasNPredecessorsOrMore`，首先在LLVM官网查找对应数据结构定义：

  <img src="https://shaw-typora.oss-cn-beijing.aliyuncs.com/20230413144329.png" style="zoom: 33%;" />

  ​	可以看到在`BasicBlock.cpp`的319行有该数据结构的定义，查找本机上下载的llvm源码：

  <img src="https://shaw-typora.oss-cn-beijing.aliyuncs.com/20230413144452.png" style="zoom: 50%;" />

  ​	查找对应源码是可以发现对应数据结构定义的：

  <img src="https://shaw-typora.oss-cn-beijing.aliyuncs.com/20230413144554.png" style="zoom:50%;" />

  ​    阅读报错信息，发现编译时自动搜索到了以前安装的llvm-6.0旧版本，手动更改路径，上述问题解决，但是发现仍旧报错很多：

  <img src="https://shaw-typora.oss-cn-beijing.aliyuncs.com/20230413211802.png" style="zoom:67%;" />

  ​	在llvm的github项目中找到了一样错误：[Build failure when targeting LLVM 11.0 · Issue #87 · google/autofdo (github.com)](https://github.com/google/autofdo/issues/87)。**<u>可以基本确定这是LLVM-11的问题，换回LLVM-10版本即可解决</u>**。

- **问题3：在编译analyzer时报错：**

  > ld: cannot find -lz

  **解决方法：**

```bash
sudo apt-get install zlib1g zlib1g-dev
```

- **问题4：在使用analyer时报错：**

  >/home/wx/Shaw/GREBE/analyzer/build/lib/analyzer: error loading file './case/linux-bitcode/lib/dump_stack.c.bc'

  **解决方法：**

  问题定位到KAMain.cc文件使用ParseIR()函数解析bc文件：

  ```c
  std::unique_ptr<Module> M = parseIRFile(InputFilenames[i], Err, *LLVMCtx);
  if (M == NULL) {
       errs() << argv[0] << ": error loading file '" << InputFilenames[i] << "'\n";
       continue;
  }
  ```

- **问题5：编译内核（部分版本）时报错：**

  >error New address family defined, please update secclass_map.

  **解决方法：**

  [编译错误 error New address family defined, please update secclass_map.解决-CSDN博客](https://blog.csdn.net/zhangpengfei991023/article/details/109672491)

- **问题6：编译内核（部分版本）时报错：**

  >**passing argument 1 to restrict-qualified parameter aliases with argument 5 [-Werror=restrict]**
  >
  >cc1: all warnings being treated as errors

  **解决方法：**

  对`tools/lib/str_error_r.c`打如下补丁：

  [Re: New -Werror=restrict error with incremental gcc - Laura Abbott (kernel.org)](https://lore.kernel.org/all/b5d9ea0f-3a3e-ec87-df76-10be4bd72b90@redhat.com/)

  ![](https://shaw-typora.oss-cn-beijing.aliyuncs.com/image-20230607224055657.png)

## Reference

- GREBE:
  - [GREBE/analyzer at master · Markakd/GREBE (github.com)](https://github.com/Markakd/GREBE/tree/master/analyzer)
  - [Markakd/LLVM-O0-BitcodeWriter: patch for LLVM to generate O0 bitcode (github.com)](https://github.com/Markakd/LLVM-O0-BitcodeWriter/tree/master)
- LLVM:
  - [LLVM Debian/Ubuntu packages](https://apt.llvm.org/)
- Kernel:
  - [How To Build Linux Kernel {Step-By-Step} | phoenixNAP KB](https://phoenixnap.com/kb/build-linux-kernel)
  - 