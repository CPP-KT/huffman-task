cmake_minimum_required(VERSION 3.21)

set(TOOL_HEADERS
        )

set(TOOL_SOURCES
        main.cpp)

add_executable(huffman-tool ${TOOL_HEADERS} ${TOOL_SOURCES})
