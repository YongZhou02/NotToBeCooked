// Tokenizer pattern covering:
// 1. Code: `code`
// 2. Bold/Italic: ***text***, **text**, *text*
// 3. Mentions: @[Filename] or @word
// 4. Citation markers: [1], [2], etc.
// 5. Markdown Links: [label](url)
//
// A marker stands after a space, a full stop or nothing. `arr[0]`, `dp[i][2]`
// and `f(x)[1]` are indexing: the bracket follows an identifier or a closing
// bracket. Same rule as `_MARKER` in apps/api/app/services/grounding.py, so a
// pill is drawn for exactly the markers the grounding check counted.
const INLINE_TOKEN =
  /(`[^`]+`|\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|\*[^*]+\*|__[^_]+__|_[^_]+_|@\[[^\]]+\]|@[a-zA-Z0-9_\-.]+|(?<![A-Za-z0-9_\])])\[\d+\]|\[[^\]]+\]\([^)]+\))/g

/** One line of an answer, split into the pieces MarkdownContent renders. */
export function splitInlineTokens(text: string): string[] {
  return text.split(INLINE_TOKEN)
}
