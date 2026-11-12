/* Standalone demo. This fixture and its rules were written for the portfolio. */
const fixture = [
  [" A-101 ", "$120.00"], ["a-102", "85.50"], ["A-101", "120"],
  ["A-103", ""], [" A-104", "$1,020.25"],
];

function scrubRows(rows, accountColumn, amountColumn) {
  const accepted = [];
  const exceptions = [];
  const seen = new Set();
  rows.forEach((row, index) => {
    const account = row[accountColumn].trim().toUpperCase();
    const amount = row[amountColumn].trim().replace(/[$,]/g, "");
    if (!/^A-\d+$/.test(account) || !/^\d+(\.\d{1,2})?$/.test(amount)) {
      exceptions.push([index + 1, account || "—", "Missing or invalid account or balance"]);
    } else if (seen.has(account)) {
      exceptions.push([index + 1, account, "Duplicate account"]);
    } else {
      seen.add(account);
      accepted.push([account, Number(amount).toFixed(2)]);
    }
  });
  return { accepted, exceptions };
}

if (typeof module !== "undefined") module.exports = { fixture, scrubRows };

if (typeof document !== "undefined") {
  const form = document.getElementById("demo-form");
  const results = document.getElementById("demo-results");
  const status = document.getElementById("demo-status");

  function renderRows(id, rows) {
    const body = document.getElementById(id);
    body.replaceChildren(...rows.map(values => {
      const row = document.createElement("tr");
      values.forEach(value => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      });
      return row;
    }));
  }

  form.addEventListener("submit", event => {
    event.preventDefault();
    const account = Number(form.elements.account.value);
    const balance = Number(form.elements.balance.value);
    if (account === balance) {
      results.hidden = true;
      status.textContent = "Choose a different source column for each field.";
      return;
    }
    const { accepted, exceptions } = scrubRows(fixture, account, balance);
    renderRows("demo-clean", accepted);
    renderRows("demo-exceptions", exceptions);
    results.hidden = false;
    status.textContent = `${accepted.length} standardized rows and ${exceptions.length} exceptions for analyst review.`;
  });
}
