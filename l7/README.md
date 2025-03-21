# llvm-pass-skeleton

This LLVM pass transforms floating-point division operations into multiplications by the reciprocal. In other words, it rewrites `x / y` as `x * (1 / y)`, which can improve performance for non-constant divisions. (Note: LLVM still automatically optimizes constant divisions.)  

## Build

```sh
$ cd llvm-pass-skeleton
$ mkdir build
$ cd build
$ cmake ..
$ make
$ cd ..

```

##  Run
Apply the pass when compiling a C file:
```sh
$ clang -fpass-plugin=`echo build/skeleton SkeletonPass.*` something.c
```

To output the transformed LLVM IR for inspection, you can use:
```sh
$ clang -fpass-plugin=`echo build/skeleton/SkeletonPass.*` -emit-llvm -S -o transformed.ll something.c
$ cat transformed.ll
```