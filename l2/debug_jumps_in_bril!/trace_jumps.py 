import json
import sys

def trace_jumps(bril_program):
    """Modifies a Bril program to insert a print instruction before each jmp or br."""
    for function in bril_program.get("functions", []):
        new_instrs = []
        for instr in function.get("instrs", []):
            if instr.get("op") in ["jmp", "br"]:
                # Insert print instruction before jump
                print_instr = {
                    "op": "print",
                    "args": [],
                    "funcs": [],
                    "labels": [],
                    "type": None,
                    "value": f"Jumping to {instr['labels']}"
                }
                new_instrs.append(print_instr)

            new_instrs.append(instr)  # Add original instruction
        function["instrs"] = new_instrs  # Replace instructions with modified version

    return bril_program

def main():
    if len(sys.argv) < 2:
        print("Usage: python transform_jumps.py <bril_json_file>")
        sys.exit(1)

    # Load Bril JSON file
    with open(sys.argv[1], "r") as f:
        bril_program = json.load(f)

    # Transform Bril program
    modified_program = insert_print_before_jumps(bril_program)

    # Print the modified Bril program (as JSON)
    json.dump(modified_program, sys.stdout, indent=2)

if __name__ == "__main__":
    main()