import json
import sys
import os
from collections import defaultdict

from tdce import trivial_dce_function, has_side_effect

sys.path.append(os.path.abspath("../l2"))
from bril_cfg import form_basic_blocks  

def canonicalize(value):
    """Sort arguments for commutative operations like add and mul."""
    if value[0] in {"add", "mul", "eq", "and", "or"}:
        num_args = sorted([x for x in value[1:] if isinstance(x, int)])
        str_args = sorted([x for x in value[1:] if isinstance(x, str)])
        return (value[0],) + tuple(num_args + str_args)  # Preserve correct order
    return value

def resolve_variable(var, var2num, num2var):
    """Recursively resolve variable chains to their canonical form."""
    seen_vars = set()
    while var in var2num and var2num[var] in num2var:
        if var in seen_vars:  # Prevent infinite loops
            break
        seen_vars.add(var)
        var = num2var[var2num[var]]
    return var

def lvn_block(block):
    """
    Perform Local Value Numbering (LVN) on a single basic block.
    Eliminates common subexpressions, performs copy propagation, and simplifies redundant assignments.
    """
    val_table = {}  # (op, arg1, arg2, ...) -> (value_number, var_name)
    var2num = {}    # var_name -> value_number
    num2var = {}    # value_number -> canonical variable name
    next_value_number = 0
    new_block = []
    computed_values = set()  # Track variables that have valid definitions

    for instr in block:
        if "label" in instr or has_side_effect(instr):
            # **Fix: Ensure print statements & function calls get correct variable replacements**
            if "args" in instr:
                instr["args"] = [resolve_variable(arg, var2num, num2var) for arg in instr["args"]]
            new_block.append(instr)
            continue

        dest = instr.get("dest")
        args = instr.get("args", [])

        # **Preserve function parameters (fix for quadratic.bril)**
        if instr["op"] == "call":
            instr["args"] = [resolve_variable(arg, var2num, num2var) for arg in args]
            new_block.append(instr)
            computed_values.update(args)
            continue

        # **Constant Tracking**
        if instr["op"] == "const" and "value" in instr:
            value_repr = ("const", instr["value"])

            if value_repr in val_table:
                existing_num, existing_var = val_table[value_repr]
                var2num[dest] = existing_num
                new_block.append({
                    "op": "id",
                    "dest": dest,
                    "type": instr["type"],
                    "args": [existing_var]
                })
            else:
                val_table[value_repr] = (next_value_number, dest)
                var2num[dest] = next_value_number
                num2var[next_value_number] = dest
                next_value_number += 1
                new_block.append(instr)

            computed_values.add(dest)
            continue

        # **Resolve arguments to their canonical forms**
        new_args = [resolve_variable(arg, var2num, num2var) for arg in args]

        # **Fix: Avoid overly aggressive `id` removal**
        if instr["op"] == "id" and len(args) == 1:
            src = new_args[0]

            # **Only propagate if the original variable is defined & distinct**
            if src in computed_values and dest != src:
                var2num[dest] = var2num.get(src, next_value_number)
                num2var[var2num[dest]] = src
                new_block.append({
                    "op": "id",
                    "dest": dest,
                    "type": instr["type"],
                    "args": [src]
                })

            computed_values.add(dest)
            continue

        # **Fix: Preserve branch conditions & jump targets**
        if instr["op"] in {"br", "jmp"}:
            new_block.append(instr)
            computed_values.update(args)
            continue

        # **Fix: Preserve function parameters as initial assignments**
        if not computed_values.intersection(set(args)) and dest:
            computed_values.add(dest)
            new_block.append(instr)
            continue

        # **Value Numbering & Optimization**
        value_repr = canonicalize((instr["op"],) + tuple(new_args))

        if value_repr in val_table:
            existing_num, existing_var = val_table[value_repr]

            # **Replace with `id` if an existing value is found**
            if dest and existing_var != dest:
                var2num[dest] = existing_num
                num2var[existing_num] = existing_var
                new_block.append({
                    "op": "id",
                    "dest": dest,
                    "type": instr["type"],
                    "args": [existing_var]
                })
            computed_values.add(dest)
        else:
            curr_num = next_value_number
            next_value_number += 1
            val_table[value_repr] = (curr_num, dest)
            var2num[dest] = curr_num
            num2var[curr_num] = dest

            instr["args"] = new_args
            new_block.append(instr)
            computed_values.add(dest)

    return new_block

def local_value_numbering(func):
    """
    Apply LVN to all basic blocks in a function.
    """
    blocks = form_basic_blocks(func["instrs"])
    new_instrs = []
    
    for block in blocks:
        optimized_block = lvn_block(block)
        new_instrs.extend(optimized_block)

    func["instrs"] = new_instrs

def optimize_program(program):
    """
    Run Local Value Numbering (LVN) and Trivial Dead Code Elimination (TDCE).
    """
    for func in program["functions"]:
        local_value_numbering(func)  # Apply LVN
        trivial_dce_function(func)   # Apply TDCE to remove dead code
    return program

def main():
    program = json.load(sys.stdin)
    program = optimize_program(program)
    json.dump(program, sys.stdout, indent=2)
    print()

if __name__ == "__main__":
    main()