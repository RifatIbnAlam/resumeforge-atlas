const optimizeBtn = document.getElementById("optimizeBtn");
const parseBtn = document.getElementById("parseBtn");
const resumeFileEl = document.getElementById("resumeFile");
const parseStatusEl = document.getElementById("parseStatus");
const resumeEl = document.getElementById("resume");
const jdEl = document.getElementById("jd");
const resultPanel = document.getElementById("resultPanel");
const modeEl = document.getElementById("mode");
const summaryEl = document.getElementById("summary");
const coverageEl = document.getElementById("coverage");
const presentEl = document.getElementById("present");
const missingEl = document.getElementById("missing");
const optimizedEl = document.getElementById("optimized");
const downloadPdfBtn = document.getElementById("downloadPdfBtn");
const warningsEl = document.getElementById("warnings");

parseBtn.addEventListener("click", async () => {
  const file = resumeFileEl.files?.[0];
  if (!file) {
    alert("Please choose a PDF or DOCX file first.");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  parseBtn.disabled = true;
  parseBtn.textContent = "Parsing...";
  parseStatusEl.textContent = "";

  try {
    const res = await fetch("/api/parse-resume", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Parsing failed");
    }

    resumeEl.value = data.extracted_text;
    parseStatusEl.textContent = `Parsed ${data.filename} (${data.chars} characters extracted).`;
  } catch (err) {
    parseStatusEl.textContent = "";
    alert(err.message || "Failed to parse file.");
  } finally {
    parseBtn.disabled = false;
    parseBtn.textContent = "Parse Uploaded Resume";
  }
});

downloadPdfBtn.addEventListener("click", async () => {
  const optimized_resume = optimizedEl.value.trim();
  if (optimized_resume.length < 20) {
    alert("Please optimize your resume first.");
    return;
  }

  downloadPdfBtn.disabled = true;
  downloadPdfBtn.textContent = "Generating PDF...";

  try {
    const res = await fetch("/api/export-pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        optimized_resume,
        filename: "optimized_resume",
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "PDF generation failed");
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "optimized_resume.pdf";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(err.message || "Could not download PDF.");
  } finally {
    downloadPdfBtn.disabled = false;
    downloadPdfBtn.textContent = "Download Optimized Resume PDF";
  }
});

optimizeBtn.addEventListener("click", async () => {
  const resume_text = resumeEl.value.trim();
  const job_description = jdEl.value.trim();

  if (resume_text.length < 20 || job_description.length < 20) {
    alert("Please provide both resume and job description (20+ chars each).");
    return;
  }

  optimizeBtn.disabled = true;
  optimizeBtn.textContent = "Optimizing...";

  try {
    const res = await fetch("/api/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume_text, job_description }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Optimization failed");
    }

    modeEl.textContent = `Mode: ${data.mode}`;
    summaryEl.textContent = data.summary;
    coverageEl.textContent = `${data.keyword_report.coverage_pct}%`;
    presentEl.textContent = data.keyword_report.present_keywords.slice(0, 15).join(", ") || "None";
    missingEl.textContent = data.keyword_report.missing_keywords.slice(0, 15).join(", ") || "None";
    optimizedEl.value = data.optimized_resume;

    warningsEl.innerHTML = "";
    (data.warnings || []).forEach((w) => {
      const p = document.createElement("p");
      p.className = "warning";
      p.textContent = `Warning: ${w}`;
      warningsEl.appendChild(p);
    });

    resultPanel.hidden = false;
  } catch (err) {
    alert(err.message || "Something went wrong");
  } finally {
    optimizeBtn.disabled = false;
    optimizeBtn.textContent = "Optimize Resume";
  }
});
