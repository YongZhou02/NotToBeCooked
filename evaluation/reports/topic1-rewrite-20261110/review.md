# Query rewrite pilot comparison

Grounding is not answer correctness. Score each answer against all required facts:
0 = incorrect / missing answer; 1 = partially correct; 2 = fully correct.
For unanswerable questions, an appropriate refusal receives 2; invented answers receive 0.
Provider failures remain in end-to-end scores and must also be reported separately.

```json
{
  "questions": 15,
  "answerable": 15,
  "rewrite_attempted": 3,
  "rewrite_accepted": 2,
  "independent_model_runs": true,
  "before": {
    "grounded_rate_NOT_accuracy": 1,
    "mean_generation_ms": 14384.58503333192,
    "generation_errors": 0,
    "answerable_evidence_recall@5": 0.9444444444444444
  },
  "after": {
    "grounded_rate_NOT_accuracy": 1,
    "mean_generation_ms": 12827.757619994614,
    "generation_errors": 0,
    "answerable_evidence_recall@5": 0.9444444444444444
  }
}
```

## t1-001

What three kinds of translator are named in Topic 1?

Reference: Compiler, interpreter, and assembler.

Before:

The three kinds of translator named are Compiler, Interpreter, and Assembler. [1]

After:

The three kinds of translator named are Compiler, Interpreter, and Assembler. [1]

Rewrite attempted: False; accepted: False

Review: before None/2; after None/2; notes: 

## t1-002

What is a pass in the course's compiler model?

Reference: One complete scan through the program.

Before:

In the course's compiler model, a pass is defined as one complete scan through the program. [4]

After:

In the course's compiler model, a pass is defined as one complete scan through the program. [4]

Rewrite attempted: False; accepted: False

Review: before None/2; after None/2; notes: 

## t1-003

What is a forward reference?

Reference: A use before a later definition in source order.

Before:

A forward reference is when a use appears before its later definition in the source order. [1]

After:

A forward reference is when a use appears before its later definition in the source order. [1]

Rewrite attempted: False; accepted: False

Review: before None/2; after None/2; notes: 

## t1-011

Which identifier is mapped to id3 in the lexical example?

Reference: rate maps to id3.

Before:

The identifier **rate** is mapped to id3 in the lexical example. [1]

After:

The identifier **rate** is mapped to id3 in the lexical example. [1]

Rewrite attempted: False; accepted: False

Review: before None/2; after None/2; notes: 

## t1-012

What are the seven token classes in the Position example, in order?

Reference: Identifier, assignment, identifier, plus, identifier, multiplication, number.

Before:

The seven token classes in the Position example, in order, are: identifier, assignment symbol, identifier, plus symbol, identifier, multiplication symbol, number. [5]

After:

The seven token classes in the Position example, in order, are: identifier, assignment symbol, identifier, plus symbol, identifier, multiplication symbol, number. [3]

Rewrite attempted: True; accepted: True

Review: before None/2; after None/2; notes: 

## t1-013

Why is the integer literal 60 converted to real before multiplication by id3?

Reference: Because 60 is an integer literal while id3 is real-valued, so semantic analysis converts 60 to real before multiplication.

Before:

Because id3 is a REAL‑typed identifier while the literal 60 is an INTEGER, semantic analysis inserts a conversion node to change the integer literal to a real before the multiplication so that the operand types match. [1]

After:

The literal 60 is an integer but id3 is a real‑valued identifier, so semantic analysis inserts a conversion node to change 60 to a real before the multiplication. [1]

Rewrite attempted: False; accepted: False

Review: before None/2; after None/2; notes: 

## t1-021

What intermediate artifact lets the front part of translation hand work to the construction part?

Reference: Intermediate representation connects analysis to synthesis.

Before:

The intermediate representation is the artifact that passes the work from the front (analysis) part of translation to the construction (synthesis) part. [3] [4]

After:

The front‑end passes its results to the back‑end via the Intermediate Representation (often called intermediate code). [2] [4]

Rewrite attempted: True; accepted: True

Review: before None/2; after None/2; notes: 

## t1-022

Why can generating output immediately be difficult when a name is declared later?

Reference: A forward reference means the referenced definition may not yet be known.

Before:

Generating output immediately is hard when a name is used before its definition because the compiler may not yet know the referenced definition. [1]

Such a situation is called a forward reference, where a use appears before a later definition in the source order. [5]

After:

Generating output immediately is difficult when a name is declared later because a forward reference means the referenced definition may not be known yet. [1] [5]

Rewrite attempted: True; accepted: False

Review: before None/2; after None/2; notes: 

## t1-023

According to the diagram, does the interpreter process the source program line by line?

Reference: Yes. The diagram says the interpreter handles the source program line by line.

Before:

Yes, the interpreter processes the source program line by line. [1]

After:

The interpreter processes the source program line by line. [1]

Rewrite attempted: False; accepted: False

Review: before None/2; after None/2; notes: 

## t1-031

In the syntax tree, which operands are grouped by multiplication?

Reference: id3 and 60, before addition with id2.

Before:

In the syntax tree, the multiplication operator groups the operand id3 with the literal 60. [1]

After:

The multiplication operator groups the operands id3 and 60 together. [1]

Rewrite attempted: False; accepted: False

Review: before None/2; after None/2; notes: 

## t1-032

Where is the conversion node inserted during semantic analysis?

Reference: Above literal 60 in the multiplication branch.

Before:

The conversion node is inserted above the integer literal 60 in the multiplication branch of the parse tree during semantic analysis. [1]

After:

The conversion node is inserted above the integer literal 60 in the multiplication branch of the parse tree during semantic analysis. [1]

Rewrite attempted: False; accepted: False

Review: before None/2; after None/2; notes: 

## t1-033

Does the libraries box receive output from the linker or feed into it?

Reference: It feeds into Linker / Loader from the left.

Before:

The Libraries & Object Files box feeds into the Linker / Loader rather than receiving output from it. [1]

After:

The Libraries & Object Files box feeds into the Linker / Loader rather than receiving output from it. [1]

Rewrite attempted: False; accepted: False

Review: before None/2; after None/2; notes: 

## t1-041

How do analysis and synthesis differ in their relationship to intermediate representation?

Reference: Analysis outputs IR; synthesis takes it as input and constructs output.

Before:

The analysis phase creates the intermediate representation as its output. [1]

The synthesis phase takes the intermediate representation as its input. [1]

Thus the intermediate representation serves as a bridge: it is produced by analysis and then used by synthesis to construct the target program. [1] [2]

After:

The analysis phase creates the intermediate representation as its output. [1]

The synthesis phase receives the intermediate representation as its input. [1]

Thus the intermediate representation serves as a bridge that links analysis to synthesis. [2]

Rewrite attempted: False; accepted: False

Review: before None/2; after None/2; notes: 

## t1-042

How does the example progress from source identifiers to a tree with type conversion?

Reference: Identifiers become id1/id2/id3; syntax groups multiplication; semantic analysis converts 60 to real.

Before:

The source program’s identifiers are mapped as Position → id1, initial → id2, and rate → id3, with the token order Position = initial + rate * 60. [5]

Before semantic analysis, the parse tree reflects the original operators: an assignment node (=) with left child id1 and right child a plus node (+) whose left child is id2 and right child a multiplication node (*) with children id3 and the integer literal 60. [3]

During semantic analysis, because id1, id2, and id3 are REAL‑typed while the literal 60 is INTEGER, a type‑conversion node inttoreal is inserted above the literal in the multiplication branch, yielding the tree id1 = id2 + (id3 * inttoreal(60)). [3]

The resulting typed expression tree is then ready for further intermediate‑code generation, as shown by the three‑address code decomposition with temporaries t1 = inttoreal(60), t2 = id3 * t1, t3 = t2 + id2, and id1 = t3. [1]

After:

The source expression "Position = initial + rate * 60" maps the identifiers Position, initial, and rate to the internal names id1, id2, and id3 respectively. [5]

Before semantic analysis the parse tree has an assignment node with id1 on the left and an addition node whose right child is a multiplication node combining id3 and the integer literal 60. [3]

Because id1, id2, and id3 are declared as REAL while the literal 60 is an INTEGER, semantic analysis inserts a conversion node (inttoreal) above the literal in the multiplication branch. [3]

The final typed expression tree therefore becomes id1 = id2 + (id3 * inttoreal(60)), which is later decomposed into three‑address code temporaries. [1]

Rewrite attempted: False; accepted: False

Review: before None/2; after None/2; notes: 

## t1-043

How does the optimized literal differ from the original source literal, and why?

Reference: Source uses integer 60; semantic analysis requires real conversion and optimization uses 60.0.

Before:

The optimizer changes the literal from an integer that must be converted to a real at run‑time to a real literal (60.0) that is already in the correct type. [2]

This replacement removes the integer‑to‑real conversion and some temporary variables while still preserving the expression’s result under the given assumptions. [2]

After:

The optimizer changes the original integer literal that would be converted to a real at run‑time into a real literal 60.0 in the generated code. [2]

This replacement removes the need for an integer‑to‑real conversion operation and some temporary variables, while still producing the same numeric result under the given assumptions. [2]

Rewrite attempted: False; accepted: False

Review: before None/2; after None/2; notes: 
