# RUN: bril2json < fib_recursive.bril | python trace_jumps.py | bril2txt | diff - fib_recusive_transformed.bril