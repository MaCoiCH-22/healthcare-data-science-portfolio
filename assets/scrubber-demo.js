/* Public simulation of one fictional run. Monetary calculations use integer cents. */
const element = id => document.getElementById(id);
const form = element("demo-form");
const stepList = element("run-steps");
const sections = [...form.querySelectorAll("[data-step]")];
const steps = [...stepList.children];
const choice = element("amount-column");
const status = element("demo-status");
const preview = element("demo-output");
const auditButton = element("prepare-audit");
const control = Number(element("control-total").dataset.cents);
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const dollars = cents => money.format(cents / 100);
const sum = values => values.reduce((total, amount) => total + amount, 0);

function readTab(tableId, tab, column, logType) {
  const position = { B: 2, C: 3 }[column];
  const rows = [...element(tableId).tBodies[0].rows].map(row => ({
    account: row.cells[1].textContent,
    raw: Number(row.cells[position].dataset.cents),
    cell: column + row.cells[0].textContent,
    tab,
    logType
  }));
  const flip = logType !== "Recovery" && rows.every(row => row.raw < 0);
  return {
    rows: rows.map(row => ({ ...row, amount: flip ? -row.raw : row.raw })),
    rule: flip ? "All negative · converted to positive" : logType === "Recovery" ? "Negative recovery · source sign kept" : "All positive · source sign kept"
  };
}

function moveTo(step, message = "", focus = true) {
  sections.forEach((section, index) => {
    section.hidden = index !== step;
    if (index === step) steps[index].setAttribute("aria-current", "step");
    else steps[index].removeAttribute("aria-current");
  });
  status.textContent = message;
  if (focus) sections[step].querySelector("h3").focus();
}

function evidence(label, detail) {
  const row = document.createElement("div");
  const term = document.createElement("dt");
  const value = document.createElement("dd");
  term.textContent = label;
  value.textContent = detail;
  row.append(term, value);
  return row;
}

function renderPreview(rows) {
  const body = element("demo-clean");
  body.replaceChildren();
  for (const row of rows) {
    const line = body.insertRow();
    for (const value of [row.account, "Inpatient", row.logType, dollars(row.amount), "Sample Hospital.xlsx - " + row.tab, row.cell]) {
      line.insertCell().textContent = value;
    }
  }
  preview.hidden = false;
}

element("inspect").addEventListener("click", () => moveTo(1, "Inspection complete. Two detail tabs, one control summary and one hidden archive."));
element("review-mapping").addEventListener("click", () => {
  preview.hidden = true;
  moveTo(1, "Confirm the mapping to run reconciliation again.");
});
element("back-recon").addEventListener("click", () => moveTo(2));
auditButton.addEventListener("click", () => moveTo(3, "Audit prep ready for review. HCRIS comparison is pending."));
choice.addEventListener("change", () => { status.textContent = ""; });
form.addEventListener("reset", () => {
  element("demo-clean").replaceChildren();
  preview.hidden = true;
  auditButton.disabled = true;
  moveTo(0, "Sample run reset.");
});

form.addEventListener("submit", event => {
  event.preventDefault();
  if (sections[1].hidden) return;
  const column = choice.value;
  if (!["B", "C"].includes(column)) {
    status.textContent = "Choose the source column before scrubbing.";
    choice.focus();
    return;
  }
  const detail = readTab("detail-rows", "Medicare Detail", column, "Traditional");
  const recovery = readTab("recovery-rows", "Recoveries", "B", "Recovery");
  const detailTotal = sum(detail.rows.map(row => row.amount));
  const recoveryTotal = sum(recovery.rows.map(row => row.amount));
  const variance = detailTotal - control;
  const list = document.createElement("dl");
  list.className = "audit-evidence";
  list.append(
    evidence("Medicare Detail · column " + column, detail.rule + " · " + dollars(sum(detail.rows.map(row => row.raw))) + " source → " + dollars(detailTotal) + " scrubbed"),
    evidence("Control Summary · positive basis", dollars(control) + " control · " + dollars(variance) + " difference"),
    evidence("Recoveries · column B", recovery.rule + " · " + dollars(recoveryTotal) + " scrubbed")
  );
  element("recon-tabs").replaceChildren(list);
  const matched = variance === 0;
  auditButton.disabled = !matched;
  preview.hidden = !matched;
  element("recon-note").textContent = matched
    ? "The detail tab ties to its control. The separate recovery keeps its source sign."
    : "This demo leaves the run incomplete while the amount differs from the control. Review the physical column mapping to continue.";
  if (matched) {
    renderPreview([...detail.rows, ...recovery.rows]);
    element("tab-evidence").textContent = "Medicare Detail " + column + "6:" + column + "8 · Recoveries B4 · Archive excluded";
    element("total-evidence").textContent = dollars(detailTotal) + " traditional and " + dollars(recoveryTotal) + " recovery · " + dollars(detailTotal + recoveryTotal) + " signed log total";
  }
  moveTo(2, matched ? "Reconciliation complete. Four rows are available for audit prep." : "Reconciliation needs review. Audit prep is unavailable for this run.");
});

stepList.hidden = false;
form.hidden = false;
moveTo(0, "", false);
