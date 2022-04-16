cmake_minimum_required(VERSION 3.21)

set(LIBRARY_HEADERS
        huffman.h)

set(LIBRARY_SOURCES
        huffman.cpp)

add_library(huffman-lib ${LIBRARY_HEADERS} ${LIBRARY_SOURCES})
