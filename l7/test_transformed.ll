; ModuleID = 'test.c'
source_filename = "test.c"
target datalayout = "e-m:o-i64:64-i128:128-n32:64-S128-Fn32"
target triple = "arm64-apple-macosx15.0.0"

; Function Attrs: noinline nounwind optnone ssp uwtable(sync)
define i32 @main() #0 {
  %1 = alloca i32, align 4
  %2 = alloca float, align 4
  %3 = alloca float, align 4
  %4 = alloca float, align 4
  %5 = alloca float, align 4
  %6 = alloca float, align 4
  %7 = alloca float, align 4
  store i32 0, ptr %1, align 4
  store float 1.000000e+01, ptr %2, align 4
  store float 2.000000e+00, ptr %3, align 4
  %8 = load float, ptr %2, align 4
  %9 = load float, ptr %3, align 4
  %10 = fdiv float 1.000000e+00, %9
  %11 = fmul float %8, %10
  store float %11, ptr %4, align 4
  %12 = load float, ptr %2, align 4
  %13 = fpext float %12 to double
  %14 = fmul double %13, 2.500000e-01
  %15 = fptrunc double %14 to float
  store float %15, ptr %5, align 4
  %16 = load float, ptr %2, align 4
  %17 = fpext float %16 to double
  %18 = fmul double %17, 2.500000e-01
  %19 = fptrunc double %18 to float
  store float %19, ptr %6, align 4
  %20 = load float, ptr %2, align 4
  %21 = load float, ptr %3, align 4
  %22 = fdiv float 1.000000e+00, %21
  %23 = fmul float %20, %22
  store float %23, ptr %7, align 4
  ret i32 0
}

attributes #0 = { noinline nounwind optnone ssp uwtable(sync) "frame-pointer"="non-leaf" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="apple-m1" "target-features"="+aes,+altnzcv,+ccdp,+ccidx,+complxnum,+crc,+dit,+dotprod,+flagm,+fp-armv8,+fp16fml,+fptoint,+fullfp16,+jsconv,+lse,+neon,+pauth,+perfmon,+predres,+ras,+rcpc,+rdm,+sb,+sha2,+sha3,+specrestrict,+ssbs,+v8.1a,+v8.2a,+v8.3a,+v8.4a,+v8a,+zcm,+zcz" }

!llvm.module.flags = !{!0, !1, !2, !3, !4}
!llvm.ident = !{!5}

!0 = !{i32 2, !"SDK Version", [2 x i32] [i32 15, i32 2]}
!1 = !{i32 1, !"wchar_size", i32 4}
!2 = !{i32 8, !"PIC Level", i32 2}
!3 = !{i32 7, !"uwtable", i32 1}
!4 = !{i32 7, !"frame-pointer", i32 1}
!5 = !{!"Homebrew clang version 19.1.7"}
