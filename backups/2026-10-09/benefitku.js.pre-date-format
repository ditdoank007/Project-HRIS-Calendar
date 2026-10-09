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
  const isUangMakan = pageMode.toLowerCase().includes("uang makan");
  const benefitType = isTunkin ? "tunkin" : (isUangMakan ? "makan" : "siaga");
  const money = new Intl.NumberFormat("id-ID", {style:"currency",currency:"IDR",maximumFractionDigits:0});
  const today = new Date();
  const monthInput = document.getElementById("benefitMonth");
  const startInput = document.getElementById("benefitStart");
  const endInput = document.getElementById("benefitEnd");
  const dateValue = [today.getFullYear(),String(today.getMonth()+1).padStart(2,"0"),String(today.getDate()).padStart(2,"0")];
  if (monthInput) monthInput.value = dateValue.slice(0,2).join("-");
  if (startInput) startInput.value = dateValue.join("-");
  if (endInput) endInput.value = dateValue.join("-");

  const labels = {
    nama:"Nama Pegawai", nip:"NIP", class_id:"Kelas Jabatan", gol:"Golongan",
    status_peg:"Status Pegawai", tunjangan:"Tunjangan Kinerja",
    persen_potongan:"Persentase Potongan", nilai_potongan:"Nilai Potongan",
    total_diterima:"Total Diterima", nominal_per_hari:"Uang Makan per Hari",
    hari_kerja:"Hari Kerja", dinas_luar:"Dinas Luar", cuti:"Cuti",
    ijin:"Izin", alpa:"Alpa", sakit:"Sakit", tidak_absen:"Tidak Absen",
    ta:"Tanpa Keterangan", um_hari:"Hari Dibayar", nominal:"Nominal",
    jumlah_siaga_piket:"Jumlah Piket Siaga", hari_libur:"Piket pada Hari Libur",
    total_brutto:"Total Bruto", total_pph21:"PPh 21", total_uang_siaga:"Total Uang Siaga",
    tanggal:"Tanggal", status:"Status", kategori:"Kategori", keterangan:"Keterangan",
    tlm_tingkat:"Tingkat Terlambat", tlm_persen:"Potongan Terlambat (%)",
    psw_tingkat:"Tingkat Pulang Awal", psw_persen:"Potongan Pulang Awal (%)",
    cuti_tingkat:"Tingkat Cuti", cuti_persen:"Potongan Cuti (%)",
    sakit_tingkat:"Tingkat Sakit", sakit_persen:"Potongan Sakit (%)",
    potongan_persen:"Total Potongan (%)", shift:"Shift", fungsional:"Jabatan/Fungsional",
    quantity:"Jumlah", brutto:"Bruto", pph21:"PPh 21", netto:"Diterima"
  };
  const summaryKeys = {
    tunkin:["tunjangan","persen_potongan","nilai_potongan","total_diterima"],
    makan:["nominal_per_hari","hari_kerja","dinas_luar","cuti","ijin","alpa","sakit","tidak_absen","ta","um_hari","nominal"],
    siaga:["jumlah_siaga_piket","hari_kerja","hari_libur","total_brutto","total_pph21","total_uang_siaga"]
  };
  const detailKeys = {
    tunkin:["tanggal","ta","tlm_tingkat","tlm_persen","psw_tingkat","psw_persen","dinas_luar","cuti_tingkat","cuti_persen","sakit_tingkat","sakit_persen","ijin","potongan_persen","hari_libur","keterangan"],
    makan:["tanggal","status","kategori","keterangan"],
    siaga:["tanggal","shift","fungsional","quantity","nominal","brutto","pph21","netto","keterangan"]
  };
  function label(key) {
    return labels[key] || key.replace(/_/g," ").replace(/\b\w/g,c=>c.toUpperCase());
  }
  function textValue(value, key) {
    if (value === null || value === undefined || value === "") return "-";
    if (typeof value === "boolean") return value ? "Ya" : "Tidak";
    if (typeof value === "number") {
      if (/_persen$|^persen_potongan$|^potongan_persen$/.test(key || "")) return value.toLocaleString("id-ID") + "%";
      if (/tunjangan|nominal|diterima|brutto|pph21|netto|potongan|^total_uang_siaga$/.test(key || "")) return money.format(value);
      return value.toLocaleString("id-ID");
    }
    if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
      const [y,m,d] = value.split("-");
      return `${d}-${m}-${y}`;
    }
    return String(value);
  }
  function cell(tag, value, key) {
    const el = document.createElement(tag);
    el.textContent = tag === "th" ? label(key) : textValue(value, key);
    el.style.cssText = "padding:10px 12px;border-bottom:1px solid #e2e8f0;text-align:left;white-space:nowrap;";
    return el;
  }
  function render(payload) {
    summaryBox.replaceChildren();
    detailBox.replaceChildren();
    const data = payload && Object.prototype.hasOwnProperty.call(payload,"data") ? payload.data : payload;
    if (!data || typeof data !== "object") {
      statusBox.textContent = payload?.message || "Tidak ada data benefit untuk periode yang dipilih.";
      return;
    }
    const details = Array.isArray(data.detail) ? data.detail : [];
    (summaryKeys[benefitType] || []).forEach(key => {
      if (data[key] === undefined || data[key] === null) return;
      const card = document.createElement("div");
      card.style.cssText = "padding:14px;border:1px solid #e2e8f0;border-radius:10px;background:#fff;min-width:0;";
      const title = document.createElement("div");
      title.textContent = label(key);
      title.style.cssText = "font-size:12px;color:#64748b;margin-bottom:8px;";
      const value = document.createElement("strong");
      value.textContent = textValue(data[key], key);
      value.style.cssText = "font-size:18px;color:#0f172a;overflow-wrap:anywhere;";
      card.append(title,value); summaryBox.append(card);
    });
    if (details.length) {
      const table = document.createElement("table");
      table.style.cssText = "width:100%;border-collapse:collapse;font-size:13px;";
      const columns = detailKeys[benefitType] || [];
      const thead = document.createElement("thead"), headRow = document.createElement("tr");
      columns.forEach(key => {
        const th = cell("th",null,key);
        th.style.cssText += "background:#f1f5f9;font-weight:700;";
        headRow.append(th);
      });
      thead.append(headRow);
      const tbody = document.createElement("tbody");
      details.forEach((row,index) => {
        const tr = document.createElement("tr");
        if (index % 2) tr.style.background = "#f8fafc";
        columns.forEach(key => tr.append(cell("td",row ? row[key] : null,key)));
        tbody.append(tr);
      });
      table.append(thead,tbody); detailBox.append(table);
    }
    const period = data.effective_period;
    const periodText = period?.start && period?.end ? ` Periode efektif: ${period.start} s.d. ${period.end}.` : "";
    statusBox.textContent = details.length ? `Data berhasil dimuat. ${details.length} rincian.${periodText}` : `Data berhasil dimuat. Tidak ada rincian untuk periode ini.${periodText}`;
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