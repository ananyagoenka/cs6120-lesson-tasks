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
        return (value[0],) + tuple(sorted(value[1:]))
    return value

def lvn_block(block):
    val_table = {}  # (op, arg1#, arg2#) -> (valnum, canonical_var)
    var2num = {}    # var_name -> valnum
    num2var = {}    # valnum -> canonical_var
    next_value_number = 0
    new_block = []

    for instr in block:
        if "label" in instr:
            new_block.append(instr)
            continue

        if has_side_effect(instr):
            if "args" in instr:
                new_args = []
                for a in instr["args"]:
                    if a in var2num:
                        val_num = var2num[a]
                        a = num2var[val_num]
                    new_args.append(a)
                new_instr = dict(instr)
                new_instr["args"] = new_args
                new_block.append(new_instr)
            else:
                new_block.append(instr)
            continue

        op = instr["op"]
        dest = instr.get("dest")
        args = instr.get("args", [])

        # ----------
        # KILL step:
        # If 'dest' was previously defined, remove old mapping.
        # ----------
        if dest and dest in var2num:
            del var2num[dest]

        # Special-case for copy propagation
        if op == "id" and dest and len(args) == 1:
            src = args[0]
            if src not in var2num:
                var2num[src] = next_value_number
                num2var[next_value_number] = src
                next_value_number += 1

            src_num = var2num[src]
            var2num[dest] = src_num

            new_block.append({
                "op": "id",
                "dest": dest,
                "type": instr["type"],
                "args": [num2var[src_num]]
            })
            continue

        # Normal LVN logic
        arg_nums = tuple(var2num[a] if a in var2num else a for a in args)
        value_repr = canonicalize((op,) + arg_nums)

        if value_repr in val_table:
            existing_num, existing_var = val_table[value_repr]
            if dest is not None:
                new_block.append({
                    "op": "id",
                    "dest": dest,
                    "type": instr["type"],
                    "args": [existing_var]
                })
                var2num[dest] = existing_num
        else:
            curr_num = next_value_number
            next_value_number += 1
            val_table[value_repr] = (curr_num, dest)

            if dest:
                var2num[dest] = curr_num
                num2var[curr_num] = dest

            new_args = [num2var[a] if a in num2var else a for a in arg_nums]
            new_instr = {
                "op": op,
                "args": new_args
            }
            if dest:
                new_instr["dest"] = dest
                new_instr["type"] = instr["type"]

            if op == "const" and "value" in instr:
                new_instr["value"] = instr["value"]

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