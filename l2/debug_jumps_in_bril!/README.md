# Bril Jump Tracing Tool

This tool **modifies a Bril program** by **inserting print statements before every `jmp` and `br` instruction**.  
It helps debug **control flow behavior** by tracking jumps in execution.

## 📌 Features
- **Inserts `print` statements before `jmp` and `br` instructions**  
- **Preserves the original program logic**  
- **Outputs modified Bril in JSON format**  
- **Helps visualize control flow changes in Bril programs**  

---

## Usage

Step 1: Convert Bril to JSON

Before running the tool, convert your Bril program into JSON format:

bril2json < input.bril > input.json

Step 2: Run the Transformation

Run the script to add print statements before jumps:

python trace_jumps.py input.json > output.json

Step 3: Convert Back to Bril

Convert the modified JSON back to Bril’s text format:

bril2txt < output.json > output.bril

Step 4: Execute the Modified Bril Program

Run the modified Bril program:

bril2json < output.bril | brili

🔬 Example

🔹 Input Bril (input.bril)

@main {
  v0: int = const 10;
  br v0 .then .else;
.then:
  print v0;
  jmp .end;
.else:
  v1: int = const 20;
  print v1;
  jmp .end;
.end:
}

🔹 Transformed Bril (output.bril)

@main {
  v0: int = const 10;
  print "Jumping to .then or .else";
  br v0 .then .else;
.then:
  print v0;
  print "Jumping to .end";
  jmp .end;
.else:
  v1: int = const 20;
  print v1;
  print "Jumping to .end";
  jmp .end;
.end:
}