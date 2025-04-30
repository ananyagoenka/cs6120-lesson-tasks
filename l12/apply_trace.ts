// apply_trace.ts
/**
 * Usage:
 *   deno run --allow-read apply_trace.ts \
 *     armstrong.json trace.json \
 *     > armstrong_traced.json
 */
import type * as bril from "../../bril-ts/bril.ts";

if (Deno.args.length !== 2) {
  console.error("USAGE: apply_trace.ts <program.json> <trace.json>");
  Deno.exit(1);
}
const [progPath, tracePath] = Deno.args;
const progText = Deno.readTextFileSync(progPath);
const traceText = Deno.readTextFileSync(tracePath);
const prog = JSON.parse(progText) as bril.Program;
const traceOps = JSON.parse(traceText) as bril.Operation[];

// Locate main
const main = prog.functions.find((f) => f.name === "main");
if (!main) {
  console.error("No function named 'main'");
  Deno.exit(1);
}

// Prepare defs = parameters of main
const defs = new Set<string>(main.args?.map((a) => a.name) ?? []);

// Rewriting pass
const specOps: bril.Instruction[] = [];
for (const op of traceOps) {
  // Helper: are all used args defined?
  const uses = op.args ?? [];
  if (!uses.every((v) => defs.has(v))) {
    continue; // skip ops using undefined vars
  }
  switch (op.op) {
    // Pure ops we copy & record their dest
    case "const":
    case "id":
    case "add":
    case "sub":
    case "mul":
    case "div":
    case "lt":
    case "le":
    case "gt":
    case "ge":
    case "eq":
    case "not":
    case "and":
    case "or":
    case "fadd":
    case "fsub":
    case "fmul":
    case "fdiv":
    case "fle":
    case "flt":
    case "fge":
    case "fgt":
    case "feq":
    case "print":
      specOps.push(op);
      if ("dest" in op && op.dest) defs.add(op.dest);
      break;

    // Convert branches into guards (only if cond was defined)
    case "br": {
      const cond = op.args![0];
      specOps.push({
        op: "guard",
        args: [cond],
        labels: ["trace_fail"],
      });
      break;
    }

    // Drop everything else (calls, rets, jmps, labels…)
    default:
      break;
  }
}

// Build new main body
const injected: bril.Instruction[] = [];
injected.push({ op: "speculate" });
injected.push(...specOps);
injected.push({ op: "commit" });
injected.push({ op: "jmp", labels: ["after_trace"] });
injected.push({ label: "trace_fail" });
injected.push(...main.instrs);
injected.push({ label: "after_trace" });

main.instrs = injected;
console.log(JSON.stringify(prog, null, 2));