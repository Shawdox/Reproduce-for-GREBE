CUR_DIR = $(shell pwd)
SRC_DIR := ${CURDIR}/src
BUILD_DIR := ${CURDIR}/build


include Makefile.inc

NPROC := ${shell nproc}

build_ka_func = \
	(mkdir -p ${2} \
		&& cd ${2} \
        &&    cmake ${1} \
				-DCMAKE_CXX_COMPILER=/home/wx/Shaw/llvm/patched_llvm_11/bin/clang++\
				-DCMAKE_C_COMPILER=/home/wx/Shaw/llvm/patched_llvm_11/bin/clang\
                -DCMAKE_BUILD_TYPE=Release \
                -DCMAKE_CXX_FLAGS_RELEASE="-std=c++14 -fno-rtti -fpic -g" \
		&& make -j${NPROC})

all: analyzer

analyzer:
	$(call build_ka_func, ${SRC_DIR}, ${BUILD_DIR})
