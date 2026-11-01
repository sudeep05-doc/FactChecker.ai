import jsPDF from "jspdf";

export function generateVerificationPDF({
  verdict,
  confidence = null,
  contentType,
  reportId,
  analysisSummary,
  reasoning = [],
  recommendation,
  processingTime,
}) {
  if (!verdict || !analysisSummary) {
    throw new Error("A verified verdict and its explanation are required.");
  }

  const pdf = new jsPDF("p", "mm", "a4");

  const pageWidth = 210;
  const margin = 15;
  const contentWidth = pageWidth - margin * 2;

  const blue = [25, 119, 210];
  const dark = [25, 35, 50];
  const green = [43, 165, 91];
  const red = [190, 55, 55];
  const gray = [105, 115, 128];
  const verdictColor =
    verdict === "REFUTED" ? red : verdict === "SUPPORTED" ? green : gray;
  const verdictIcon =
    verdict === "REFUTED" ? "×" : verdict === "SUPPORTED" ? "✓" : "?";
  const lightBlue = [235, 246, 255];
  const border = [190, 205, 220];

  let y = 15;

  /* =========================================
     HEADER
  ========================================== */

  pdf.setFillColor(...blue);
  pdf.roundedRect(
    margin,
    y,
    40,
    12,
    3,
    3,
    "F"
  );

  pdf.setTextColor(255, 255, 255);
  pdf.setFontSize(15);
  pdf.setFont("helvetica", "bold");

  pdf.text(
    "VeriAI",
    margin + 20,
    y + 8,
    {
      align: "center",
    }
  );

  pdf.setTextColor(...dark);
  pdf.setFontSize(16);

  pdf.text(
    "Evidence Verification Report",
    62,
    y + 5
  );

  pdf.setFontSize(9);
  pdf.setTextColor(...gray);

  pdf.text(
    `Report ID: ${reportId}`,
    62,
    y + 10
  );

  y += 22;

  /* =========================================
     REPORT SUMMARY
  ========================================== */

  pdf.setFillColor(...blue);

  pdf.roundedRect(
    margin,
    y,
    contentWidth,
    8,
    2,
    2,
    "F"
  );

  pdf.setTextColor(255, 255, 255);
  pdf.setFontSize(11);
  pdf.setFont("helvetica", "bold");

  pdf.text(
    "REPORT SUMMARY",
    margin + 4,
    y + 5.5
  );

  y += 12;

  pdf.setDrawColor(...border);

  pdf.roundedRect(
    margin,
    y,
    contentWidth,
    30,
    2,
    2,
    "S"
  );

  pdf.setTextColor(...dark);
  pdf.setFontSize(9);
  pdf.setFont("helvetica", "bold");

  pdf.text(
    "CONTENT INFORMATION",
    margin + 5,
    y + 7
  );

  pdf.setFont("helvetica", "normal");

  pdf.text(
    `Type: ${contentType}`,
    margin + 5,
    y + 14
  );

  pdf.text(
    `Report ID: ${reportId}`,
    margin + 5,
    y + 20
  );

  pdf.text(
    `Date: ${new Date().toLocaleDateString()}`,
    margin + 5,
    y + 26
  );

  pdf.setFont("helvetica", "bold");

  pdf.text(
    "TEST REQUESTED",
    margin + 78,
    y + 7
  );

  pdf.setFont("helvetica", "normal");

  pdf.text(
    "Evidence-based factual verification",
    margin + 78,
    y + 14
  );

  pdf.text(
    "Evidence verdict",
    margin + 78,
    y + 20
  );

  y += 38;

  /* =========================================
     VERIFICATION RESULTS
  ========================================== */

  pdf.setFillColor(...blue);

  pdf.roundedRect(
    margin,
    y,
    contentWidth,
    8,
    2,
    2,
    "F"
  );

  pdf.setTextColor(255, 255, 255);
  pdf.setFontSize(11);

  pdf.text(
    "VERIFICATION RESULTS",
    margin + 4,
    y + 5.5
  );

  y += 12;

  pdf.setDrawColor(...border);

  pdf.roundedRect(
    margin,
    y,
    contentWidth,
    34,
    2,
    2,
    "S"
  );

  /* Verdict */

  pdf.setDrawColor(...verdictColor);
  pdf.setLineWidth(1.5);

  pdf.circle(
    margin + 13,
    y + 17,
    6,
    "S"
  );

  pdf.setTextColor(...verdictColor);
  pdf.setFontSize(14);
  pdf.setFont("helvetica", "bold");

  pdf.text(
    verdictIcon,
    margin + 10.5,
    y + 19.5
  );

  pdf.setTextColor(...dark);
  pdf.setFontSize(8);

  pdf.text(
    "FINAL VERDICT",
    margin + 24,
    y + 10
  );

  pdf.setTextColor(...blue);
  pdf.setFontSize(17);

  pdf.text(
    verdict.toUpperCase(),
    margin + 24,
    y + 21
  );

  if (confidence != null) {
    pdf.setTextColor(...dark);
    pdf.setFontSize(8);
    pdf.text("Class probability (not factual confidence)", margin + 125, y + 10);
    pdf.setFontSize(17);
    pdf.text(`${Math.round(confidence * 100)}%`, margin + 125, y + 21);
  } else {
    pdf.setTextColor(...dark);
    pdf.setFontSize(8);
    pdf.text("Confidence", margin + 125, y + 10);
    pdf.setFontSize(12);
    pdf.text("Not available", margin + 125, y + 21);
  }

  y += 42;

  /* =========================================
     ANALYSIS SUMMARY
  ========================================== */

  pdf.setFillColor(...blue);

  pdf.roundedRect(
    margin,
    y,
    contentWidth,
    8,
    2,
    2,
    "F"
  );

  pdf.setTextColor(255, 255, 255);
  pdf.setFontSize(11);

  pdf.text(
    "EVIDENCE-BASED EXPLANATION",
    margin + 4,
    y + 5.5
  );

  y += 13;

  pdf.setFillColor(...lightBlue);

  const summaryLines =
    pdf.splitTextToSize(
      analysisSummary,
      contentWidth - 12
    );

  const summaryHeight =
    Math.max(28, summaryLines.length * 5 + 15);

  pdf.roundedRect(
    margin,
    y,
    contentWidth,
    summaryHeight,
    2,
    2,
    "F"
  );

  pdf.setTextColor(...dark);
  pdf.setFontSize(9);
  pdf.setFont("helvetica", "normal");

  pdf.text(
    summaryLines,
    margin + 6,
    y + 9
  );

  y += summaryHeight + 8;

  /* =========================================
     REASONING
  ========================================== */

  pdf.setTextColor(...dark);
  pdf.setFontSize(10);
  pdf.setFont("helvetica", "bold");

  pdf.text(
    "REASONING SUMMARY",
    margin,
    y
  );

  y += 7;

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(8);

  reasoning.forEach((item) => {
    pdf.setFillColor(...blue);

    pdf.circle(
      margin + 2,
      y - 1.5,
      1.5,
      "F"
    );

    const lines =
      pdf.splitTextToSize(
        item,
        contentWidth - 12
      );

    pdf.setTextColor(...dark);

    pdf.text(
      lines,
      margin + 7,
      y
    );

    y += lines.length * 4.5 + 2;
  });

  /* =========================================
     RECOMMENDATION
  ========================================== */

  y += 3;

  pdf.setTextColor(...dark);
  pdf.setFontSize(10);
  pdf.setFont("helvetica", "bold");

  pdf.text(
    "RECOMMENDATION",
    margin,
    y
  );

  y += 7;

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(8);

  const recommendationLines =
    pdf.splitTextToSize(
      recommendation,
      contentWidth
    );

  pdf.text(
    recommendationLines,
    margin,
    y
  );

  y +=
    recommendationLines.length * 4.5 +
    10;

  /* =========================================
     PROCESSING
  ========================================== */

  pdf.setFillColor(...lightBlue);

  pdf.roundedRect(
    margin,
    y,
    contentWidth,
    25,
    3,
    3,
    "F"
  );

  pdf.setTextColor(...dark);
  pdf.setFontSize(8);
  pdf.setFont("helvetica", "bold");

  pdf.text(
    "PROCESSING TIME",
    margin + 7,
    y + 9
  );

  pdf.setFontSize(13);

  pdf.text(
    processingTime,
    margin + 7,
    y + 18
  );

  pdf.setFontSize(8);

  pdf.text(
    "REPORT GENERATED",
    margin + 105,
    y + 9
  );

  pdf.setFont("helvetica", "normal");

  pdf.text(
    new Date().toLocaleString(),
    margin + 105,
    y + 18
  );

  /* =========================================
     FOOTER
  ========================================== */

  const footerY = 285;

  pdf.setDrawColor(...border);

  pdf.line(
    margin,
    footerY - 5,
    pageWidth - margin,
    footerY - 5
  );

  pdf.setTextColor(...gray);
  pdf.setFontSize(7);

  pdf.text(
    "FactChecker.ai Evidence Verification",
    margin,
    footerY
  );

  pdf.text(
    `Report ID: ${reportId}`,
    pageWidth / 2,
    footerY,
    {
      align: "center",
    }
  );

  pdf.text(
    "1 / 1",
    pageWidth - margin,
    footerY,
    {
      align: "right",
    }
  );

  /* =========================================
     SAVE
  ========================================== */

  pdf.save(
    `VeriAI-Verification-${reportId}.pdf`
  );
}