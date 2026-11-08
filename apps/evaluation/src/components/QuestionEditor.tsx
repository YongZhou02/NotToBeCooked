import { useId, type ReactNode } from "react"

import { Button } from "@workspace/ui/components/button"
import { cn } from "@workspace/ui/lib/utils"
import { Field, FieldLabel } from "@workspace/ui/components/field"
import { Textarea } from "@workspace/ui/components/textarea"
import { resolveDocument, type SourceDocument } from "@/lib/documents"
import {
  CATEGORIES,
  blankEvidenceGroup,
  type Draft,
  type EditorState,
} from "@/lib/editor"
import type { EvidenceAlternative, Split } from "@/types"

function LabeledField({
  label,
  className,
  children,
}: {
  label: string
  className?: string
  children: (id: string) => ReactNode
}) {
  const id = useId()
  return (
    <Field className={cn("gap-1", className)}>
      <FieldLabel htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </FieldLabel>
      {children(id)}
    </Field>
  )
}

const selectClass =
  "h-8 min-w-0 rounded-md border border-input bg-background px-2 text-sm"

export function QuestionEditor({
  editor,
  registry,
  currentDocId,
  currentPage,
  readSelection,
  onChange,
  onCancel,
  onSave,
  onCheck,
}: {
  editor: EditorState
  registry: readonly SourceDocument[]
  /** The PDF and page the reader is showing now. */
  currentDocId: string
  currentPage: number
  /** The text selected in the PDF, or an empty string. */
  readSelection: () => string
  onChange: (next: EditorState) => void
  onCancel: () => void
  onSave: () => void
  onCheck: (alt: EvidenceAlternative) => void
}) {
  const { draft } = editor

  const setDraft = (patch: Partial<Draft>, message = editor.message) =>
    onChange({ ...editor, message, draft: { ...draft, ...patch } })

  const setAlt = (
    groupIndex: number,
    altIndex: number,
    patch: Partial<EvidenceAlternative>,
    message = editor.message
  ) =>
    setDraft(
      {
        evidence_groups: draft.evidence_groups.map((g, gi) =>
          gi !== groupIndex
            ? g
            : {
                ...g,
                alternatives: g.alternatives.map((a, ai) =>
                  ai === altIndex ? { ...a, ...patch } : a
                ),
              }
        ),
      },
      message
    )

  const heading =
    editor.mode === "edit"
      ? `Edit ${editor.id}`
      : editor.isHardCase
        ? "New hard case"
        : "New question"

  return (
    <section
      data-testid="question-editor"
      className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-(--line) bg-(--bg-canvas)"
    >
      <div className="flex flex-none items-center gap-2 border-b border-(--line) px-3 py-2">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold">{heading}</h3>
          {editor.message && (
            <p role="alert" className="text-xs text-(--cite)">
              {editor.message}
            </p>
          )}
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="button" size="sm" onClick={onSave}>
          Save
        </Button>
      </div>

      <div className="grid min-h-0 flex-1 content-start gap-3 overflow-y-auto p-3">
        <LabeledField label="Question">
          {(id) => (
            <Textarea
              id={id}
              rows={2}
              placeholder="Write the question..."
              value={draft.question}
              onChange={(e) => setDraft({ question: e.target.value })}
              className="min-h-0 md:text-sm"
            />
          )}
        </LabeledField>
        <LabeledField label="Answer key">
          {(id) => (
            <Textarea
              id={id}
              rows={2}
              placeholder="Write the expected answer..."
              value={draft.reference_answer}
              onChange={(e) => setDraft({ reference_answer: e.target.value })}
              className="min-h-0 md:text-sm"
            />
          )}
        </LabeledField>

        <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
          <LabeledField label="Split" className="w-auto">
            {(id) => (
              <select
                id={id}
                value={draft.split}
                onChange={(e) => setDraft({ split: e.target.value as Split })}
                className={selectClass}
              >
                <option value="test">Test</option>
                <option value="dev">Dev</option>
              </select>
            )}
          </LabeledField>
          <LabeledField label="Category" className="w-auto">
            {(id) => (
              <select
                id={id}
                value={draft.category}
                onChange={(e) => setDraft({ category: e.target.value })}
                className={selectClass}
              >
                {[
                  ...(CATEGORIES.includes(draft.category)
                    ? []
                    : [draft.category]),
                  ...CATEGORIES,
                ].map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            )}
          </LabeledField>
          <label className="flex items-center gap-1.5 pb-1 text-sm">
            <input
              type="checkbox"
              checked={draft.is_hard_case}
              onChange={(e) => setDraft({ is_hard_case: e.target.checked })}
              className="accent-(--acc)"
            />
            Hard case
          </label>
          <label className="flex items-center gap-1.5 pb-1 text-sm">
            <input
              type="checkbox"
              checked={draft.verified}
              onChange={(e) => setDraft({ verified: e.target.checked })}
              className="accent-(--acc)"
            />
            Answer key verified
          </label>
        </div>

        <div className="grid gap-1.5">
          <p className="text-xs font-semibold tracking-widest text-(--tx-dim) uppercase">
            Gold evidence &amp; supporting context
          </p>
          <p className="text-xs text-muted-foreground">
            Every required evidence must be found. Alternatives inside one are
            either/or.
          </p>

          {draft.evidence_groups.map((group, groupIndex) => (
            <div
              key={groupIndex}
              className="grid gap-2 rounded-md border border-(--line) p-2"
            >
              <div className="flex flex-wrap items-center gap-1">
                <span className="mr-auto text-sm font-medium">
                  Required evidence {groupIndex + 1}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="xs"
                  title="Another quote that would satisfy this same requirement"
                  onClick={() =>
                    setDraft({
                      evidence_groups: draft.evidence_groups.map((g, gi) =>
                        gi === groupIndex
                          ? {
                              ...g,
                              alternatives: [
                                ...g.alternatives,
                                blankEvidenceGroup(currentDocId, currentPage)
                                  .alternatives[0]!,
                              ],
                            }
                          : g
                      ),
                    })
                  }
                >
                  + Alternative
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="xs"
                  className="text-destructive"
                  onClick={() =>
                    setDraft({
                      evidence_groups: draft.evidence_groups.filter(
                        (_, gi) => gi !== groupIndex
                      ),
                    })
                  }
                >
                  Remove
                </Button>
              </div>

              {group.alternatives.map((alt, altIndex) => (
                <div key={altIndex} className="grid gap-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="w-4 text-xs text-muted-foreground">
                      {altIndex > 0 ? "or" : ""}
                    </span>
                    <select
                      aria-label="Source document"
                      value={
                        resolveDocument(registry, alt.document_id)?.id ??
                        alt.document_id
                      }
                      onChange={(e) =>
                        setAlt(groupIndex, altIndex, {
                          document_id: e.target.value,
                        })
                      }
                      className={`${selectClass} max-w-[10rem]`}
                    >
                      {registry.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.label}
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      min={1}
                      aria-label="PDF page"
                      value={alt.pdf_page}
                      onChange={(e) =>
                        setAlt(groupIndex, altIndex, {
                          pdf_page: Math.max(
                            1,
                            parseInt(e.target.value, 10) || 1
                          ),
                        })
                      }
                      className="h-8 w-16 rounded-md border border-input bg-background px-1.5 text-sm"
                    />
                    <Button
                      type="button"
                      variant="secondary"
                      size="xs"
                      title="Fill this quote, document and page from the text selected in the PDF"
                      // Pressing a button must not clear the selection it is about to read.
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => {
                        const text = readSelection()
                        if (!text) {
                          setAlt(
                            groupIndex,
                            altIndex,
                            {},
                            "Select the quote in the PDF first, then press Use PDF selection."
                          )
                        } else {
                          setAlt(
                            groupIndex,
                            altIndex,
                            {
                              quote: text,
                              document_id: currentDocId,
                              pdf_page: currentPage,
                            },
                            ""
                          )
                        }
                      }}
                    >
                      Use PDF selection
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="xs"
                      title="Open this page and highlight the quote. A warning appears if the text does not match."
                      onClick={() =>
                        onCheck({ ...alt, quote: alt.quote.trim() })
                      }
                    >
                      Check in PDF
                    </Button>
                    {group.alternatives.length > 1 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="xs"
                        className="text-destructive"
                        title="Remove this alternative"
                        aria-label="Remove this alternative"
                        onClick={() =>
                          setDraft({
                            evidence_groups: draft.evidence_groups.map(
                              (g, gi) =>
                                gi === groupIndex
                                  ? {
                                      ...g,
                                      alternatives: g.alternatives.filter(
                                        (_, ai) => ai !== altIndex
                                      ),
                                    }
                                  : g
                            ),
                          })
                        }
                      >
                        ×
                      </Button>
                    )}
                  </div>
                  <Textarea
                    rows={2}
                    aria-label="Gold evidence quote"
                    placeholder="Exact quote from the PDF..."
                    value={alt.quote}
                    onChange={(e) =>
                      setAlt(groupIndex, altIndex, { quote: e.target.value })
                    }
                    className="min-h-0 md:text-sm"
                  />
                </div>
              ))}
            </div>
          ))}

          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="w-fit"
            onClick={() =>
              setDraft({
                evidence_groups: [
                  ...draft.evidence_groups,
                  blankEvidenceGroup(currentDocId, currentPage),
                ],
              })
            }
          >
            + Add required evidence
          </Button>
        </div>

        <LabeledField label="Required scoring facts (one per line)">
          {(id) => (
            <Textarea
              id={id}
              rows={3}
              placeholder="One fact a good answer must contain, per line..."
              value={draft.facts_text}
              onChange={(e) => setDraft({ facts_text: e.target.value })}
              className="min-h-0 md:text-sm"
            />
          )}
        </LabeledField>
      </div>
    </section>
  )
}
