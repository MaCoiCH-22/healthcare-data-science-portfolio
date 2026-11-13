/* Synthetic portfolio walkthrough. Amounts are integer cents. */
const form = document.getElementById("demo-form");
const choice = document.getElementById("amount-column");
const status = document.getElementById("demo-status");
const results = document.getElementById("demo-results");
const output = document.getElementById("demo-output");
const control = Number(document.getElementById("control-total").dataset.cents);
const sourceRows = Array.from(document.querySelectorAll("#sample-rows tbody tr"));
const columns = { B: 2, C: 3 };
const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const formatAmount = cents => currency.format(cents / 100);

function clearResults(message = "") {
  results.hidden = true;
  output.hidden = true;
  status.textContent = message;
}

function previewOutput(rows, column) {
  const body = document.getElementById("demo-clean");
  body.replaceChildren();
  for (const row of rows) {
    const line = body.insertRow();
    for (const value of [row.account, formatAmount(row.cents), "Medicare Detail"]) {
      line.insertCell().textContent = value;
    }
  }
  const rowNumbers = rows.map(row => row.sourceRow).join(", ");
  document.getElementById("mapping-evidence").textContent =
    `Mapping evidence · Sample Hospital.xlsx · Medicare Detail · column ${column} · rows ${rowNumbers}`;
  output.hidden = false;
}

choice.addEventListener("change", () => clearResults(
  choice.value ? "Column selected. Compare totals to review this mapping." : ""
));
form.addEventListener("reset", () => clearResults("Sample reset."));
form.addEventListener("submit", event => {
  event.preventDefault();
  const column = choice.value;
  const position = columns[column];
  if (position === undefined) {
    clearResults("Select an amount column before comparing totals.");
    return;
  }
  const rows = sourceRows.map(row => ({
    sourceRow: row.cells[0].textContent,
    account: row.cells[1].textContent,
    cents: Number(row.cells[position].dataset.cents)
  }));
  const total = rows.reduce((sum, row) => sum + row.cents, 0);
  const variance = total - control;

  document.getElementById("mapped-total").textContent = formatAmount(total);
  document.getElementById("compared-total").textContent = formatAmount(control);
  document.getElementById("total-variance").textContent = formatAmount(variance);
  results.hidden = false;
  output.hidden = true;

  if (variance === 0) {
    status.textContent = `Column ${column} matches the control at ${formatAmount(control)}. The log preview is available below.`;
    previewOutput(rows, column);
  } else {
    status.textContent = `Column ${column} differs from the control by ${formatAmount(variance)}. Review the source mapping before previewing the log.`;
  }
});
form.hidden = false;
