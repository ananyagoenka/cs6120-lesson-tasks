#include <stdio.h>

int main()
{
  float a = 10.0, b = 2.0;
  float c = a / b;           // Should be replaced with multiplication
  float d = a / 4.0;         // Test constant divisor
  float e = a / (2.0 + 2.0); // Will LLVM still optimize this?
  float f = a / b;           // Should still transform
  return 0;
}