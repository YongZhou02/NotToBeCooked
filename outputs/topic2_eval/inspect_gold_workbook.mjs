import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import fs from "node:fs";

const source = "D:/Downloads/NTBC_Topic2_50_Paraphrased_Gold_Labels.xlsx";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const overview = await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 12000,
  tableMaxRows: 10,
  tableMaxCols: 20,
  tableMaxCellChars: 500,
});
console.log(overview.ndjson);
for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange(true);
  if (!used) continue;
  console.log(`SHEET ${sheet.name} ${used.address}`);
  const region = await workbook.inspect({
    kind: "region",
    sheetId: sheet.name,
    range: used.address,
    maxChars: 50000,
    tableMaxRows: 80,
    tableMaxCols: 30,
    tableMaxCellChars: 1000,
  });
  console.log(region.ndjson);
}

const values = workbook.worksheets
  .getItem("Topic2_50_Gold_Labels")
  .getRange("A1:J51").values;
const headers = values[0];
const rows = values.slice(1).map((row) =>
  Object.fromEntries(headers.map((header, index) => [header, row[index]])),
);
fs.writeFileSync(
  "outputs/topic2_eval/workbook_gold_rows.json",
  JSON.stringify(rows, null, 2) + "\n",
);
