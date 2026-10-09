(function () {
  "use strict";
  const form = document.getElementById("benefitFilter");
  if (!form) return;
  const statusBox = document.getElementById("benefitStatus");
  const summaryBox = document.getElementById("benefitSummary");
  const detailBox = document.getElementById("benefitDetail");
  const mode = document.body.dataset.benefitMode || "";
  const pageMode = document.querySelector(".breadcrumb-card strong")?.textContent || "";
  const isTunkin = pageMode.toLowerCase().includes("tunjangan kinerja");
  const money = new Intl.NumberFormat("id-ID", {style:"currency",currency:"IDR",maximumFractionDigits:0});
  const today = new Date();
  const monthInput = document.getElementById("benefitMonth");
  const startInput = document.getElementById("benefitStart");
  const endInput = document.getElementById("benefitEnd");
  const dateValue = [today.getFullYear(),String(today.getMonth()+1).padStart(2,"0"),String(today.getDate()).padStart(2,"0")];
  if (monthInput) monthInput.value = dateValue.slice(0,2).join("-");
  if (startInput) startInput.value = dateValue.join("-");
  if (endInput) endInput.value = dateValue.join("-");

  function textValue(value) {
    if (value === null || value === undefined || value === "") return "-";
    if (typeof value === "object") return JSON.stringify(value);
    if (typeof value === "number") return value.toLocaleString("id-ID");
    return String(value);
  }
  function cell(tag, value) {
    const el = document.createElement(tag);
    el.textContent = textValue(value);
    el.style.cssText = "padding:10px 12px;border-bottom:1px solid #e2e8f0;text-align:left;white-space:nowrap;";
    return el;
  }
  function render(payload) {
    summaryBox.replaceChildren();
    detailBox.replaceChildren();
    const data = payload && Object.prototype.hasOwnProperty.call(payload,"data") ? payload.data : payload;
    if (!data || typeof data !== "object") {
      statusBox.textContent = "Tidak ada data benefit untuk periode yang dipilih.";
      return;
    }
    const details = Array.isArray(data.detail) ? data.detail : [];
    Object.entries(data).filter(([key,value]) => key !== "detail" && value !== null && typeof value !== "object").forEach(([key,value]) => {
      const card = document.createElement("div");
      card.style.cssText = "padding:14px;border:1px solid #e2e8f0;border-radius:10px;background:#fff;";
      const label = document.createElement("div");
      label.textContent = key.replace(/_/g," ");
      label.style.cssText = "font-size:12px;color:#64748b;text-transform:capitalize;margin-bottom:8px;";
      const number = document.createElement("strong");
      number.textContent = typeof value === "number" && /total|nominal|diterima|brutto|pph|netto|potongan/i.test(key) ? money.format(value) : textValue(value);
      number.style.cssText = "font-size:18px;color:#0f172a;overflow-wrap:anywhere;";
      card.append(label,number); summaryBox.append(card);
    });
    if (details.length) {
      const table = document.createElement("table");
      table.style.cssText = "width:100%;border-collapse:collapse;font-size:13px;";
      const columns = [...new Set(details.flatMap(row => Object.keys(row || {})))];
      const thead = document.createElement("thead"), headRow = document.createElement("tr");
      columns.forEach(key => {
        const th = cell("th",key.replace(/_/g," "));
        th.style.cssText += "background:#f1f5f9;font-weight:700;text-transform:capitalize;";
        headRow.append(th);
      });
      thead.append(headRow);
      const tbody = document.createElement("tbody");
      details.forEach((row,index) => {
        const tr = document.createElement("tr");
        if (index % 2) tr.style.background = "#f8fafc";
        columns.forEach(key => tr.append(cell("td",row ? row[key] : null)));
        tbody.append(tr);
      });
      table.append(thead,tbody); detailBox.append(table);
    }
    statusBox.textContent = details.length ? "Data berhasil dimuat." : "Data berhasil dimuat. Tidak ada rincian untuk periode ini.";
  }
  form.addEventListener("submit", async event => {
    event.preventDefault();
    summaryBox.replaceChildren(); detailBox.replaceChildren();
    statusBox.textContent = "Memuat data…";
    let url;
    if (isTunkin) {
      const start = startInput.value, end = endInput.value;
      if (!start || !end || start > end) { statusBox.textContent = "Tanggal mulai dan selesai harus valid."; return; }
      url = "/api/benefitku/tunjangan-kinerja?start="+encodeURIComponent(start)+"&end="+encodeURIComponent(end);
    } else {
      const value = monthInput.value;
      if (!value) { statusBox.textContent = "Pilih periode terlebih dahulu."; return; }
      const [year,month] = value.split("-");
      const slug = pageMode.toLowerCase().includes("uang makan") ? "uang-makan" : "uang-siaga";
      url = "/api/benefitku/"+slug+"?year="+year+"&month="+month;
    }
    try {
      const response = await fetch(url,{credentials:"same-origin"});
      const payload = await response.json();
      if (!response.ok || payload.status !== "success") throw new Error(payload.message || "Gagal mengambil data benefit.");
      render(payload);
    } catch (error) {
      statusBox.textContent = error.message || "Layanan Benefit tidak dapat diakses.";
    }
  });
  form.requestSubmit();
})();