add_llvm_pass_plugin(SkeletonPass
    # List your source files here.
    Skeleton.cpp
)

set(CMAKE_C_COMPILER "/opt/homebrew/opt/llvm/bin/clang")
set(CMAKE_CXX_COMPILER "/opt/homebrew/opt/llvm/bin/clang++")
include_directories(/opt/homebrew/opt/llvm/include)