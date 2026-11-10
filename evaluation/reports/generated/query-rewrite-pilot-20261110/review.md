# Query rewrite pilot comparison

Grounding is not answer correctness. Score each answer against all required facts:
0 = incorrect / missing answer; 1 = partially correct; 2 = fully correct.
For unanswerable questions, an appropriate refusal receives 2; invented answers receive 0.
Provider failures remain in end-to-end scores and must also be reported separately.

```json
{
  "questions": 15,
  "answerable": 13,
  "rewrite_attempted": 2,
  "rewrite_accepted": 0,
  "independent_model_runs": true,
  "before": {
    "grounded_rate_NOT_accuracy": 0.8666666666666667,
    "mean_generation_ms": 13662.579726662565,
    "generation_errors": 0,
    "answerable_evidence_recall@5": 0.6794871794871795
  },
  "after": {
    "grounded_rate_NOT_accuracy": 0.8666666666666667,
    "mean_generation_ms": 3345.0331866721776,
    "generation_errors": 0,
    "answerable_evidence_recall@5": 0.6794871794871795
  }
}
```

## t2-001

A compiler meets `total_count` for the first time as raw characters. Which component should group them into one meaningful unit before grammar rules are considered?

Reference: The lexical analyzer/scanner groups characters into a lexeme and returns an identifier token to the parser.

Before:

The lexical analyzer groups raw input characters into meaningful units (lexemes) before any grammar rules are applied. [4]

After:

The lexical analyzer groups raw characters into meaningful units (lexemes/tokens) before any grammar rules are applied. [5]

Rewrite attempted: False; accepted: False

Review: before __/2; after __/2; notes: __

## t2-002

A lexer occasionally needs one character beyond a token boundary to decide what it just recognized. What implementation need does that create?

Reference: It needs lookahead and efficient input buffering so it can examine extra characters without excessive per-character reading overhead.

Before:

Because a lexer sometimes must examine one or more characters beyond the end of the current token, it requires an input buffering mechanism that can provide look‑ahead without re‑reading the source file. [1]

To avoid the huge time cost of repeatedly accessing a large source program, specialized buffering techniques are used to support this look‑ahead capability. [1]

After:

Because a lexer sometimes must examine one or more characters beyond the end of the current token, it requires an input‑buffering mechanism that can provide look‑ahead without re‑reading the source file. [1]

To avoid the huge time cost of repeatedly accessing a large source program, specialized buffering techniques are used to support this look‑ahead. [1]

Rewrite attempted: False; accepted: False

Review: before __/2; after __/2; notes: __

## t2-003

Two patterns look similar: `letter(letter|digit)*` and `letter letter|digit*`. Why could they match different strings without any character class changing?

Reference: Grouping and operator precedence change how alternatives and repetition bind: the first starts with a letter then any number of letters/digits; the ungrouped expression follows precedence and does not express the same requirement.

Before:

In a regular expression, the Kleene star (*) binds tighter than the alternation operator (|), so writing `letter letter|digit*` is interpreted as `(letter) | (digit*)` rather than `letter (letter|digit)*`. [5]

Therefore `letter(letter|digit)*` matches a string that starts with a letter and is followed by any number (including zero) of letters or digits, while `letter letter|digit*` matches either a single letter or any number of digits, which can be completely different strings. [5]

After:

The two regular expressions have different operator precedence, so they are parsed differently. [5]

**letter(letter|digit)*** groups the alternation **letter|digit** before applying the Kleene star, meaning the star repeats the whole group of a letter followed by any number of letters or digits. [5]

**letter letter|digit*** is parsed as **(letter letter) | (digit*)** because concatenation has higher precedence than alternation, so the star applies only to **digit**, not to the preceding **letter**. [5]

Therefore the first pattern matches strings that start with a letter and then have any sequence of letters or digits, while the second pattern matches either two consecutive letters or any number of digits, leading to different matched strings even though the character classes are unchanged. [5]

Rewrite attempted: False; accepted: False

Review: before __/2; after __/2; notes: __

## t2-004

A scanner examines `<` and then another character. Why might it need to retract a character before returning the less-than token?

Reference: If the next character is not `=` or `>`, that lookahead character belongs to the following lexeme; the relop diagram marks retract on the other-character transition.

Before:

When the scanner sees a '<' it reads the following character to decide whether the token is just '<' or part of a multi‑character operator such as '<='. [3] [1]

If the next character does not belong to the '<' token, the scanner must retract (move the input pointer back by one) so that the extra character can be processed as the start of the next lexeme. [3] [1]

After:

When the scanner sees a '<' it reads the following character to see if the two together form a multi‑character operator such as "<=" or "<<". [2]

If the next character does not belong to that operator, the scanner must put it back (retract) so that it will be the first character of the next token rather than being lost. [2]

Retracting works because the scanner maintains a forward pointer that can be moved ahead to look ahead and then moved back to the correct start of the next lexeme. [1]

Rewrite attempted: False; accepted: False

Review: before __/2; after __/2; notes: __

## t2-005

For `score`, distinguish the actual letters seen in source code from the category passed downstream and any optional metadata.

Reference: `score` is the lexeme; its token name is id/identifier; an attribute may point to the corresponding symbol-table entry.

Before:

The characters ‘s’, ‘c’, ‘o’, ‘r’, ‘e’ are the actual letters (lexeme) that appear in the source code for the identifier score. [2] [4] [3]

The lexical analyzer passes downstream the token category ‘id’ to represent that lexeme. [4] [3]

A token is a pair consisting of the token name and an optional attribute value, which can hold the lexeme string as metadata. [2]

After:

The characters **s**, **c**, **o**, **r**, **e** are the actual letters seen in the source code for the identifier. [2] [4]

Downstream the lexical analyzer provides a token whose category (token name) is **id**, indicating an identifier. [3] [4]

The token can also carry an optional attribute value that stores the original lexeme "score" as metadata. [2]

Rewrite attempted: False; accepted: False

Review: before __/2; after __/2; notes: __

## t2-006

If the programmer writes `fi` where they intended `if`, why might the first compiler phase accept it rather than diagnosing a misspelled keyword?

Reference: `fi` matches an identifier pattern; the lexical analyzer returns an id token and leaves any contextual error to the parser or another phase.

Before:

The lexical analyzer often cannot detect misspelled keywords because it treats the character sequence as a valid lexeme for some token type and therefore returns that token to the parser for further analysis. [1]

After:

The lexical analyzer does not flag `fi` as an error because `fi` matches a valid token pattern, so it treats it as a legitimate lexeme and passes the token to the parser, which must later detect the misspelling. [1]

Rewrite attempted: False; accepted: False

Review: before __/2; after __/2; notes: __

## t2-007

Which exact DFA minimization algorithm, including every partition-refinement step, is mandated by this lecturer for the transition diagrams?

Reference: NOT IN SOURCE. The outline names DFA minimization, but the provided Topic 2 pages do not specify a step-by-step minimization algorithm.

Before:

The supplied lecture material does not specify any particular DFA minimization algorithm or its partition‑refinement steps.

After:

The supplied material does not specify which DFA minimization algorithm, including its partition‑refinement steps, the lecturer mandates for the transition diagrams.

Rewrite attempted: True; accepted: False

Review: before __/2; after __/2; notes: __

## t2-008

A sequence `aabba` and the set `{a,b}` play different roles in language specification. What is the distinction?

Reference: `{a,b}` can be an alphabet (available symbols); `aabba` is a string (ordered finite sequence over that alphabet).

Before:

The set {a,b} is the alphabet, i.e., the collection of characters that may appear, while aabba is a string, a finite sequence of characters drawn from that alphabet. [1]

After:

The set {a,b} is an alphabet, i.e., the collection of characters that may be used in the language. [1]

The sequence aabba is a string, a finite ordered list of symbols taken from that alphabet. [1]

Thus, the alphabet defines the possible symbols, while a string is a concrete instance built from those symbols. [1]

Rewrite attempted: False; accepted: False

Review: before __/2; after __/2; notes: __

## t2-009

A parser is becoming cluttered with blank spaces and comments. Which earlier processing responsibility could be relocated, and what broader design benefit does the lecture claim?

Reference: Scanning can remove comments and compact whitespace before tokenization, simplifying the parser; separating lexical analysis also improves portability and efficiency.

Before:

The removal of blank spaces and comments should be handled by the scanner’s simple scanning phase rather than the parser. [2]

Doing so leads to a simpler parser design because unnecessary tokens are eliminated earlier. [1]

After:

The removal of blank spaces and comments should be handled by the scanner’s simple scanning phase rather than the parser. [2]

Doing so leads to a simpler parser design because unnecessary tokens are eliminated earlier. [1]

Rewrite attempted: False; accepted: False

Review: before __/2; after __/2; notes: __

## t2-010

A system repeatedly pauses token recognition whenever its only character buffer is refilled. Which lecture design reduces that interruption and by what mechanism?

Reference: The two-buffer approach processes one buffer while loading the other with the next chunk, alternately refilling the two buffers.

Before:

Using a double‑buffer (two‑buffer) arrangement reduces the pause caused by refilling the only buffer. [1]

In this design the second buffer is loaded with the next characters while the lexical analyzer continues processing the first buffer, so processing can continue uninterrupted as buffers are swapped. [1]

After:

Using a two‑buffer (double‑buffer) arrangement eliminates the pause that occurs when a single buffer must be refilled. [1]

In this design the second buffer is loaded concurrently while the first is being scanned, and a sentinel character (eof) at the end of each half signals when the other buffer must be reloaded, allowing seamless continuation of token recognition. [2]

Rewrite attempted: False; accepted: False

Review: before __/2; after __/2; notes: __

## t2-011

A proposed recognizer accepts strings of length exactly two over `{a,b}`. How can the lecture’s notation express that set without listing every word?

Reference: `(a|b)(a|b)`; it produces aa, ab, ba, bb.

Before:

The set of all strings of length exactly two over the alphabet {a,b} can be expressed with the regular expression (a|b)(a|b). [1]

After:

The set of all strings of length exactly two over the alphabet {a,b} can be expressed as the regular expression (a|b)(a|b). [1]

Rewrite attempted: False; accepted: False

Review: before __/2; after __/2; notes: __

## t2-012

Under the relational-operator machine drawn in the slides, how are `<=`, `<>`, and `>=` distinguished even though they are all two-character inputs?

Reference: They lead to distinct final token outputs: LE for <=, NE for <>, and GE for >=.

Before:

The relational‑operator machine reads the first character and then looks ahead one position; if the second character is ‘=’ it returns the LE token for ‘<=’, if it is ‘>’ it returns the NE token for ‘<>’, and otherwise it retracts the extra character and returns the LT token for ‘<’. The same look‑ahead and possible retraction is used for ‘>’ to distinguish ‘>=’ (returning GE) from ‘>’ (returning GT). [1]

After:

The machine reads the first character and then looks at the next character to decide which two‑character relational operator it is: if the first character is ‘<’ and the second is ‘=’ it returns the token LE (≤); if the first is ‘<’ and the second is ‘>’ it returns the token NE (<>); if the first is ‘>’ and the second is ‘=’ it returns the token GE (≥). Single‑character operators are handled by retracting the extra input character when the second character does not form a two‑character operator. [1]

Rewrite attempted: False; accepted: False

Review: before __/2; after __/2; notes: __

## t2-013

According to this lecture, what numerical benchmark proves the two-buffer technique is 37% faster than a single buffer?

Reference: NOT IN SOURCE. No measured percentage or benchmark is given; only qualitative efficiency arguments.

Before:

The supplied lecture material does not provide a numerical benchmark showing that the two‑buffer technique is 37% faster than a single buffer.

After:

The supplied lecture material does not provide a numerical benchmark showing that the two‑buffer technique is 37% faster than a single buffer.

Rewrite attempted: True; accepted: False

Review: before __/2; after __/2; notes: __

## t2-014

Two names, `pi` and `score`, are different spellings but may still produce the same token name. Why is that not a contradiction?

Reference: Lexemes are concrete character sequences; a shared pattern/token category such as id can match different lexemes, with attributes distinguishing entries.

Before:

A token consists of a token name and an optional attribute value, while a lexeme is the actual character sequence that matches the token’s pattern. [1]

Both `pi` and `score` match the pattern for identifiers, so the lexical analyzer classifies each as the token name `<id>` with different attribute values (e.g., pointers to their symbol‑table entries). [3]

Thus, having different spellings produce the same token name is not a contradiction because the token name denotes the category (identifier), and the differing spellings are captured by the attribute values of that token. [1] [3]

After:

A token is defined by its token name, while the actual characters that appear in the source program are called lexemes. [1]

Different spellings such as `pi` and `score` are distinct lexemes, but both match the pattern for the token named *identifier*, so the lexical analyzer assigns them the same token name. [3]

Rewrite attempted: False; accepted: False

Review: before __/2; after __/2; notes: __

## t2-015

What kind of malformed input can stop the scanner itself, rather than simply produce a valid token that later proves misplaced?

Reference: A remaining input prefix that matches none of the available token patterns can be recognized as a lexical error.

Before:

Input that does not match any token pattern—i.e., when no token pattern matches a prefix of the remaining input—can halt the scanner itself. [2]

After:

Input where no token pattern matches the next characters—i.e., a prefix of the remaining input that fits none of the defined token patterns—can halt the scanner itself. [2]

Rewrite attempted: False; accepted: False

Review: before __/2; after __/2; notes: __
