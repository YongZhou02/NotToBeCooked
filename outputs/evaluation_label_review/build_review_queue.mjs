import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const sourcePath = "evaluation/datasets/cpt316/topic1/questions.jsonl";
const outputPath = "outputs/evaluation_label_review/NTBC_Topic1_Label_Review.xlsx";
const previewPath = "outputs/evaluation_label_review/NTBC_Topic1_Label_Review_preview.png";
const queuePreviewPath = "outputs/evaluation_label_review/NTBC_Topic1_Label_Review_queue_preview.png";
const source = await fs.readFile(sourcePath, "utf8");
const questions = source.trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);

const flattenEvidence = (question) => question.evidence_groups.flatMap((group) =>
  group.alternatives.map((item) => ({ ...item, group_id: group.id })),
);

const stats = { dev: { questions: 0, quotes: 0 }, test: { questions: 0, quotes: 0 } };
for (const question of questions) {
  stats[question.split].questions += 1;
  stats[question.split].quotes += question.evidence_groups.length;
}

const workbook = Workbook.create();
const summary = workbook.worksheets.add("Summary");
const queue = workbook.worksheets.add("Review Queue");
summary.showGridLines = false;
queue.showGridLines = false;
summary.tabColor = "#0F766E";
queue.tabColor = "#D97706";

const font = "Arial";
const dark = "#17324D";
const teal = "#0F766E";
const amber = "#FFF3CD";
const lightBlue = "#E8F1F8";
const lightGreen = "#E8F5EE";
const lightRed = "#FCE8E6";
const line = "#D8E0E7";
const muted = "#5E6B76";

summary.getRange("A2:F2").merge();
summary.getRange("A2").values = [["NTBC Topic 1 label review"]];
summary.getRange("A2:F2").format = {
  font: { name: font, size: 16, bold: true, color: dark },
  verticalAlignment: "center",
};
summary.getRange("A4:F4").merge();
summary.getRange("A4").values = [["Start in Review Queue. Filter Review status = Pending, then verify the question, answer key, required facts and gold quotes."]];
summary.getRange("A4:F4").format = { font: { name: font, size: 10, color: muted, italic: true }, wrapText: true };

summary.getRange("A7:F7").values = [["Split", "Questions", "Gold evidence groups", "Verified", "Needs fix", "Remaining"]];
summary.getRange("A8:C10").values = [
  ["Dev", stats.dev.questions, stats.dev.quotes],
  ["Test", stats.test.questions, stats.test.quotes],
  ["Total", questions.length, stats.dev.quotes + stats.test.quotes],
];
summary.getRange("D8:F8").formulas = [[
  '=COUNTIFS(\'Review Queue\'!$C$6:$C$55,"dev",\'Review Queue\'!$A$6:$A$55,"Verified")',
  '=COUNTIFS(\'Review Queue\'!$C$6:$C$55,"dev",\'Review Queue\'!$A$6:$A$55,"Needs fix")',
  '=COUNTIFS(\'Review Queue\'!$C$6:$C$55,"dev",\'Review Queue\'!$A$6:$A$55,"Pending")',
]];
summary.getRange("D9:F9").formulas = [[
  '=COUNTIFS(\'Review Queue\'!$C$6:$C$55,"test",\'Review Queue\'!$A$6:$A$55,"Verified")',
  '=COUNTIFS(\'Review Queue\'!$C$6:$C$55,"test",\'Review Queue\'!$A$6:$A$55,"Needs fix")',
  '=COUNTIFS(\'Review Queue\'!$C$6:$C$55,"test",\'Review Queue\'!$A$6:$A$55,"Pending")',
]];
summary.getRange("D10:F10").formulas = [["=SUM(D8:D9)", "=SUM(E8:E9)", "=SUM(F8:F9)"]];
summary.getRange("A7:F7").format = {
  fill: dark,
  font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
summary.getRange("A8:F10").format = {
  font: { name: font, size: 11, color: dark },
  verticalAlignment: "center",
  borders: { insideHorizontal: { style: "thin", color: line }, bottom: { style: "thin", color: line } },
};
summary.getRange("B8:F10").format.horizontalAlignment = "center";
summary.getRange("A10:F10").format.font = { name: font, size: 11, bold: true, color: dark };
summary.getRange("A13:F13").merge();
summary.getRange("A13").values = [["Review fields"]];
summary.getRange("A13:F13").format = { fill: teal, font: { name: font, size: 11, bold: true, color: "#FFFFFF" } };
summary.getRange("A14:B18").values = [
  ["Question clear?", "Is the wording precise and unambiguous?"],
  ["Answer key correct?", "Does it fully answer the question?"],
  ["Evidence supports?", "Do the gold quotes directly support the answer?"],
  ["Needs fix", "Enter the corrected answer or explanation before verifying."],
  ["Verified", "All three checks are Yes and no correction is needed."],
];
summary.getRange("A14:B18").format = { font: { name: font, size: 10, color: dark }, wrapText: true, verticalAlignment: "top" };
summary.getRange("A14:A18").format.font = { name: font, size: 10, bold: true, color: dark };
summary.getRange("A1:F20").format.font = { name: font };
summary.getRange("A1:F20").format.rowHeight = 21;
summary.getRange("A4:F4").format.rowHeight = 42;
summary.getRange("A:A").format.columnWidth = 24;
summary.getRange("B:B").format.columnWidth = 54;
summary.getRange("C:F").format.columnWidth = 18;

queue.getRange("A2:R2").merge();
queue.getRange("A2").values = [["Human verification queue"]];
queue.getRange("A2:R2").format = { font: { name: font, size: 16, bold: true, color: dark } };
queue.getRange("A3:R3").merge();
queue.getRange("A3").values = [["Yellow columns require human input. Filter by split, category or status. One row represents one labelled question."]];
queue.getRange("A3:R3").format = { font: { name: font, size: 10, color: muted, italic: true } };
queue.getRange("A5:R5").values = [[
  "Review status", "Question ID", "Split", "Category", "Origin", "Difficulty",
  "Question", "Answer key", "Required facts", "Evidence groups", "PDF pages",
  "Gold quotes", "Question clear?", "Answer key correct?", "Evidence supports?",
  "Corrected answer key", "Reviewer notes", "Generation review?",
]];

const rows = questions.map((question) => {
  const evidence = flattenEvidence(question);
  const pages = [...new Set(evidence.map((item) => item.pdf_page))].sort((a, b) => a - b);
  const quotes = evidence.map((item) => `[${item.group_id}] p.${item.pdf_page}: ${item.quote}`).join("\n\n");
  return [
    "Pending", question.id, question.split, question.category, "Synthetic", "Normal",
    question.question, question.reference_answer, question.required_facts.join("\n"),
    question.evidence_groups.length, pages.join(", "), quotes, "", "", "", "", "",
    question.generation_review ? "Yes" : "No",
  ];
});
queue.getRange(`A6:R${5 + rows.length}`).values = rows;
const lastRow = 5 + rows.length;
const table = queue.tables.add(`A5:R${lastRow}`, true, "LabelReviewQueue");
table.style = "TableStyleMedium2";
table.showFilterButton = true;

queue.getRange("A5:R5").format = {
  fill: dark,
  font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
queue.getRange(`A6:R${lastRow}`).format = {
  font: { name: font, size: 10, color: dark },
  verticalAlignment: "top",
  wrapText: true,
  borders: { insideHorizontal: { style: "thin", color: line } },
};
queue.getRange(`A6:A${lastRow}`).format.fill = amber;
queue.getRange(`M6:Q${lastRow}`).format.fill = amber;
queue.getRange(`C6:C${lastRow}`).format.horizontalAlignment = "center";
queue.getRange(`J6:K${lastRow}`).format.horizontalAlignment = "center";
queue.getRange(`R6:R${lastRow}`).format.horizontalAlignment = "center";
queue.getRange(`A6:A${lastRow}`).dataValidation = { rule: { type: "list", values: ["Pending", "Verified", "Needs fix", "Reject"] } };
queue.getRange(`M6:O${lastRow}`).dataValidation = { rule: { type: "list", values: ["Yes", "No"] } };
queue.getRange(`E6:E${lastRow}`).dataValidation = { rule: { type: "list", values: ["Synthetic", "Human"] } };
queue.getRange(`F6:F${lastRow}`).dataValidation = { rule: { type: "list", values: ["Normal", "Hard"] } };
queue.getRange(`A6:A${lastRow}`).conditionalFormats.add("containsText", { text: "Verified", format: { fill: lightGreen, font: { color: "#166534", bold: true } } });
queue.getRange(`A6:A${lastRow}`).conditionalFormats.add("containsText", { text: "Needs fix", format: { fill: amber, font: { color: "#92400E", bold: true } } });
queue.getRange(`A6:A${lastRow}`).conditionalFormats.add("containsText", { text: "Reject", format: { fill: lightRed, font: { color: "#991B1B", bold: true } } });
queue.getRange(`C6:C${lastRow}`).conditionalFormats.add("containsText", { text: "dev", format: { fill: lightBlue, font: { color: "#1E3A5F", bold: true } } });
queue.getRange(`C6:C${lastRow}`).conditionalFormats.add("containsText", { text: "test", format: { fill: "#EEEAF8", font: { color: "#4C3C78", bold: true } } });

queue.getRange(`A6:R${lastRow}`).format.rowHeight = 76;
queue.getRange("A:A").format.columnWidth = 16;
queue.getRange("B:B").format.columnWidth = 13;
queue.getRange("C:C").format.columnWidth = 9;
queue.getRange("D:D").format.columnWidth = 17;
queue.getRange("E:F").format.columnWidth = 12;
queue.getRange("G:G").format.columnWidth = 42;
queue.getRange("H:H").format.columnWidth = 40;
queue.getRange("I:I").format.columnWidth = 38;
queue.getRange("J:J").format.columnWidth = 13;
queue.getRange("K:K").format.columnWidth = 12;
queue.getRange("L:L").format.columnWidth = 58;
queue.getRange("M:O").format.columnWidth = 18;
queue.getRange("P:P").format.columnWidth = 40;
queue.getRange("Q:Q").format.columnWidth = 32;
queue.getRange("R:R").format.columnWidth = 17;
queue.freezePanes.freezeRows(5);
queue.freezePanes.freezeColumns(2);

workbook.recalculate();
const check = await workbook.inspect({
  kind: "table",
  range: "Review Queue!A5:R12",
  include: "values,formulas",
  tableMaxRows: 8,
  tableMaxCols: 18,
  maxChars: 8000,
});
console.log(check.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);
const preview = await workbook.render({ sheetName: "Summary", range: "A1:F18", scale: 1.5, format: "png" });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
const queuePreview = await workbook.render({ sheetName: "Review Queue", range: "A1:R10", scale: 0.8, format: "png" });
await fs.writeFile(queuePreviewPath, new Uint8Array(await queuePreview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, previewPath, queuePreviewPath, rows: questions.length, stats }));
