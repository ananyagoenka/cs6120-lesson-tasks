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
    """Compute used variables in a function, including branch conditions."""
    used_vars = set()
    
    for instr in func["instrs"]:
        if "args" in instr:
            used_vars.update(instr["args"])  # ✅ Tracks arithmetic and function call args
        
        # ✅ Fix: Only check "op" if it exists
        if "op" in instr and instr["op"] == "br":  # ✅ Tracks branch conditions
            used_vars.add(instr["args"][0])  # First argument is the condition variable

    return used_vars

def remove_unused_variables(func):
    """
    Removes unused variables by working on basic blocks.
    Uses global liveness information to avoid removing needed variables.
    """
    used_vars = analyze_liveness(func)  # ✅ Use the global liveness result

    blocks = form_basic_blocks(func["instrs"])
    changed = False

    for block in blocks:
        new_block = []
        for instr in block:
            dest = instr.get("dest")

            # Always keep side-effecting instructions
            if has_side_effect(instr):
                new_block.append(instr)
                continue

            # Only remove if the destination is truly unused
            if dest and dest not in used_vars:
                changed = True
                continue  # Skip unused assignment

            new_block.append(instr)

        block[:] = new_block  # Modify block in place

    func["instrs"] = [instr for block in blocks for instr in block]
    return changed

def remove_shadowed_assignments(block, global_used_vars):
    """
    Removes assignments that are overwritten **before being used** in the same block.
    Ensures globally needed variables are not removed.
    """
    last_def = {}
    to_drop = set()

    # First pass: Identify droppable assignments
    for i, instr in enumerate(block):
        args = instr.get("args", [])
        dest = instr.get("dest")

        # Mark args as "used," preventing them from being deleted
        for arg in args:
            if arg in last_def:
                del last_def[arg]

        # If dest exists, check if a prior definition exists
        if dest:
            if dest in last_def and dest not in global_used_vars:
                to_drop.add(last_def[dest])  # Mark previous definition for removal
            last_def[dest] = i  # Update last definition

    # Second pass: Remove marked instructions
    new_block = [instr for i, instr in enumerate(block) if i not in to_drop]
    return new_block

def trivial_dce_function(func):
    """
    Iteratively applies DCE and local optimizations until no further progress.
    """
    while True:
        used_vars = analyze_liveness(func)  # ✅ Compute global used variables
        changed1 = remove_unused_variables(func)  # ✅ Now correctly considers global liveness
        changed2 = False

        blocks = form_basic_blocks(func["instrs"])
        new_instrs = []
        for block in blocks:
            optimized_block = remove_shadowed_assignments(block, used_vars)  # ✅ Now considers global liveness
            if optimized_block != block:
                changed2 = True
            new_instrs.extend(optimized_block)

        if not (changed1 or changed2):  # Stop when no more changes occur
            break

        func["instrs"] = new_instrs  # Update function instructions

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
    json.dump(program, sys.stdout, indent=2, sort_keys=True)
    #print()

if __name__ == "__main__":
    main()