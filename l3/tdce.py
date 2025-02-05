import json
import sys
import os
from collections import defaultdict

sys.path.append(os.path.abspath("../l2"))
from bril_cfg import form_basic_blocks  

SIDE_EFFECT_OPS = {"print", "store", "call", "ret", "jmp", "br"}

def has_side_effect(instr):
    """Check if an instruction has side effects (e.g., print, store)."""
    return 'op' in instr and instr['op'] in SIDE_EFFECT_OPS

def analyze_liveness(func):
    """
    Compute globally used variables in a function.
    Returns:
    - A set of variables that are used anywhere in the function.
    """
    used_vars = set()
    for instr in func["instrs"]:
        if "args" in instr:
            used_vars.update(instr["args"])
    return used_vars

def remove_unused_variables(func):
    """
    Removes instructions whose assigned variables are never used.
    """
    used_vars = analyze_liveness(func)
    new_instrs = []

    for instr in func["instrs"]:
        dest = instr.get("dest")
        if dest and not has_side_effect(instr):
            if dest not in used_vars:
                continue  

        new_instrs.append(instr)

    func["instrs"] = new_instrs

def remove_shadowed_assignments(block):
    """
    Removes assignments that are later overwritten **within the same basic block**.
    """
    last_def = {}  
    new_block = []

    for instr in block:
        if "label" in instr:
            new_block.append(instr)
            continue

        dest = instr.get("dest")
        args = instr.get("args", [])

        for arg in args:
            if arg in last_def:
                last_def[arg]["used"] = True

        if dest and not has_side_effect(instr):
            if dest in last_def and not last_def[dest]["used"]:
                new_block[last_def[dest]["index"]] = None

            last_def[dest] = {"index": len(new_block), "used": False}

        new_block.append(instr)

    return [instr for instr in new_block if instr is not None]

def trivial_dce_function(func):
    """
    Runs both dead code elimination passes iteratively until no more changes occur.
    """
    changed = True
    while changed:
        changed = False

        # First pass: Remove unused variables (global analysis)
        before = len(func["instrs"])
        remove_unused_variables(func)
        after = len(func["instrs"])
        if before != after:
            changed = True

        # Second pass: Remove shadowed variables (local analysis)
        blocks = form_basic_blocks(func["instrs"])
        new_instrs = []
        for block in blocks:
            optimized_block = remove_shadowed_assignments(block)
            new_instrs.extend(optimized_block)

        if new_instrs != func["instrs"]:
            changed = True
            func["instrs"] = new_instrs

def trivial_dce(program):
    """
    Apply DCE to all functions in the program.
    """
    for func in program["functions"]:
        trivial_dce_function(func)
    return program

def main():
    program = json.load(sys.stdin)
    program = trivial_dce(program)
    json.dump(program, sys.stdout, indent=2)
    print()

if __name__ == "__main__":
    main()