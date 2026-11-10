import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const path = "D:/Downloads/NTBC_Topic1_50_Labels_Individually_Verified.xlsx";
const input = await FileBlob.load(path);
const workbook = await SpreadsheetFile.importXlsx(input);
const overview = await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 8000,
  tableMaxRows: 8,
  tableMaxCols: 20,
  tableMaxCellChars: 180,
});
console.log(overview.ndjson);

for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange(true);
  if (!used) continue;
  const region = await workbook.inspect({
    kind: "region",
    sheetId: sheet.name,
    range: used.address,
    maxChars: 30000,
    tableMaxRows: 80,
    tableMaxCols: 30,
    tableMaxCellChars: 500,
  });
  console.log(JSON.stringify({ sheet: sheet.name, address: used.address }));
  console.log(region.ndjson);
}

const audit = workbook.worksheets.getItem("50-Question Detailed Audit").getRange("A1:K51").values;
const headers = audit[0];
console.log("AUDIT_HEADERS", JSON.stringify(headers));
const auditRows = audit.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]])));
console.log("AUDIT_JSON_START");
console.log(JSON.stringify(auditRows));
console.log("AUDIT_JSON_END");
console.log("VERDICT_GROUPS_START");
const verdictGroups = {};
for (const row of auditRows) {
  (verdictGroups[row.Verdict] ??= []).push(row["Question ID"]);
}
console.log(JSON.stringify(verdictGroups));
console.log("VERDICT_GROUPS_END");
console.log("TARGET_REVISIONS_START");
console.log(JSON.stringify(auditRows.filter((row) => ["t1-010", "t1-013", "t1-023", "t1-025", "t1-027", "t1-036", "t1-048"].includes(row["Question ID"])), null, 2));
console.log("TARGET_REVISIONS_END");
