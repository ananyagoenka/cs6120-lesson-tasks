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
        # Separate numbers and strings for correct sorting
        num_args = sorted([x for x in value[1:] if isinstance(x, int)])
        str_args = sorted([x for x in value[1:] if isinstance(x, str)])
        return (value[0],) + tuple(num_args + str_args)  # Preserve correct order
    return value

def lvn_block(block):
    """
    Perform Local Value Numbering on a single basic block.
    Eliminates common subexpressions and performs copy propagation.
    """
    val_table = {}  # Maps (op, arg1, arg2, ...) -> (value_number, var_name)
    var2num = {}    # Maps variable names to value numbers
    num2var = {}    # Maps value numbers to canonical variable names
    next_value_number = 0
    new_block = []

    for instr in block:
        if "label" in instr or has_side_effect(instr):
            new_block.append(instr)
            continue

        dest = instr.get("dest")
        args = instr.get("args", [])

        # Special case: Constants must be tracked separately
        if instr["op"] == "const" and "value" in instr:
            value_repr = ("const", instr["value"])

            if value_repr in val_table:
                existing_num, existing_var = val_table[value_repr]
                new_block.append({
                    "op": "id",
                    "dest": dest,
                    "type": instr["type"],
                    "args": [existing_var]
                })
                var2num[dest] = existing_num  # Map dest to existing constant
            else:
                val_table[value_repr] = (next_value_number, dest)
                var2num[dest] = next_value_number
                num2var[next_value_number] = dest
                next_value_number += 1
                new_instr = {
                    "op": "const",
                    "dest": dest,
                    "type": instr["type"],
                    "value": instr["value"]
                }
                new_block.append(new_instr)
            continue  # Skip generic LVN processing for constants

        # Generic LVN processing
        arg_nums = tuple(var2num.get(arg, arg) for arg in args)
        value = canonicalize((instr["op"],) + arg_nums)

        if value in val_table:
            existing_num, existing_var = val_table[value]

            # Ensure we don't incorrectly merge distinct variables
            if dest and existing_var != dest:
                new_block.append({
                    "op": "id",
                    "dest": dest,
                    "type": instr["type"],
                    "args": [existing_var]
                })
            
            var2num[dest] = existing_num  # Map dest to existing value number
        else:
            curr_num = next_value_number
            next_value_number += 1
            val_table[value] = (curr_num, dest)
            var2num[dest] = curr_num
            num2var[curr_num] = dest  # Properly track canonical variable

            new_args = [num2var.get(arg, arg) for arg in arg_nums]

            new_instr = {
                "op": instr["op"],
                "args": new_args
            }
            if dest:
                new_instr["dest"] = dest
                new_instr["type"] = instr["type"]

            new_block.append(new_instr)

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

def trivial_dce(program):
    """
    Apply Trivial Dead Code Elimination after LVN.
    """
    for func in program["functions"]:
        trivial_dce_function(func)
    return program

def optimize_program(program):
    """
    Run Local Value Numbering (LVN) and Trivial Dead Code Elimination (TDCE).
    """
    for func in program["functions"]:
        local_value_numbering(func)  # Apply LVN
        trivial_dce_function(func)   # can turn on/off DCE using this
    return program

def main():
    program = json.load(sys.stdin)
    program = optimize_program(program)
    json.dump(program, sys.stdout, indent=2)
    print()

if __name__ == "__main__":
    main()