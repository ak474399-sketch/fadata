"use client";

import { useMemo, useState, type CSSProperties } from "react";
import { MetricConfigPanel } from "@/components/metric-config-panel";
import { ResultTable } from "@/components/result-table";
import { UploadPanel } from "@/components/upload-panel";
import { createDefaultMetricConfig, type MetricConfigState } from "@/lib/metric-config";
import type { ParseError, ParseResponse, ParsedFileResult } from "@/types/report";

const REPORT_TYPES = [
  "PUSH 分析报告",
  "版本迭代报告",
  "产品漏斗分析",
  "商业化分析",
  "周报",
  "月报",
  "半年报",
  "年报"
] as const;

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

function parseDownloadFileName(contentDisposition: string | null, fallback: string): string {
  if (!contentDisposition) return fallback;
  const encodedMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encodedMatch?.[1]) {
    try {
      return decodeURIComponent(encodedMatch[1]);
    } catch {
      // ignore decode errors and continue to fallback parsing
    }
  }
  const plainMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
  return plainMatch?.[1] ?? fallback;
}

function escapeCsvCell(value: string): string {
  const safe = value.replaceAll("\"", "\"\"");
  return /[",\n]/.test(safe) ? `"${safe}"` : safe;
}

function toErrorCsv(errors: ParseError[]): string {
  const header = ["文件名", "错误码", "阶段", "错误信息"];
  const rows = errors.map((item) => [
    item.fileName,
    item.code,
    item.stage ?? "",
    item.message
  ]);
  return [header, ...rows].map((row) => row.map((cell) => escapeCsvCell(String(cell))).join(",")).join("\n");
}

export default function HomePage() {
  const [files, setFiles] = useState<Array<{ id: string; file: File }>>([]);
  const [uploading, setUploading] = useState(false);
  const [data, setData] = useState<ParseResponse>({ results: [], errors: [] });
  const [selectedFileName, setSelectedFileName] = useState<string>("");
  const [reportMsg, setReportMsg] = useState("");
  const [parseProgress, setParseProgress] = useState(0);
  const [showCelebration, setShowCelebration] = useState(false);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");
  const [showMergeTipsModal, setShowMergeTipsModal] = useState(false);
  const [metricConfig, setMetricConfig] = useState<MetricConfigState>(createDefaultMetricConfig());

  const selectedResult = useMemo<ParsedFileResult | undefined>(
    () => data.results.find((item) => item.fileName === selectedFileName) ?? data.results[0],
    [data.results, selectedFileName]
  );

  const canParse = files.length > 0;

  const handleFileChange = (incoming: FileList | null) => {
    const next =
      incoming?.length
        ? Array.from(incoming).map((file, index) => ({
            id: `${file.name}-${file.size}-${file.lastModified}-${index}-${Date.now()}`,
            file
          }))
        : [];
    setFiles(next);
    setReportMsg("");
  };

  const handleRemoveFile = (fileId: string) => {
    setFiles((prev) => prev.filter((file) => file.id !== fileId));
    setReportMsg("");
  };

  const handleParse = async (mergeMode = false) => {
    if (!files.length) return;
    if (mergeMode && files.length <= 1) {
      setShowMergeTipsModal(true);
      return;
    }
    setUploading(true);
    setParseProgress(8);
    setReportMsg("");
    setData({ results: [], errors: [] });
    const form = new FormData();
    for (const item of files) form.append("files", item.file);
    form.append("mergeMode", mergeMode ? "true" : "false");
    const progressTimer = window.setInterval(() => {
      setParseProgress((prev) => (prev >= 90 ? prev : prev + 6));
    }, 250);

    try {
      const response = await fetch("/api/parse", { method: "POST", body: form });
      let result: ParseResponse;
      try {
        result = (await response.json()) as ParseResponse;
      } catch {
        result = {
          results: [],
          errors: [
            {
              fileName: "-",
              code: "E_PARSE_BAD_RESPONSE",
              stage: "upstream",
              message: "解析接口返回异常，无法解析响应内容。"
            }
          ]
        };
      }

      if (!response.ok && result.errors.length === 0) {
        result.errors.push({
          fileName: "-",
          code: "E_PARSE_HTTP",
          stage: "upstream",
          message: `解析失败（HTTP ${response.status}）。`
        });
      }

      setData(result);
      if (result.results.length) {
        const preferred =
          mergeMode
            ? result.results.find((item) => item.fileName === "并表分析")?.fileName ?? result.results[0].fileName
            : result.results[0].fileName;
        setSelectedFileName(preferred);
        const totalRows = result.results.reduce((acc, item) => {
          return (
            acc +
            item.sheets.dailyByDay.length +
            item.sheets.byContent.length +
            item.sheets.byVersionSummary.length +
            (item.sheets.byNotifyCopyDay?.length ?? 0)
          );
        }, 0);
        setSuccessMessage(`解析完成：${result.results.length} 个文件，共 ${totalRows} 行分析数据。`);
        setShowSuccessModal(true);
        setShowCelebration(true);
        window.setTimeout(() => setShowCelebration(false), 2200);
      }
      setParseProgress(100);
    } catch {
      setData({
        results: [],
        errors: [
          {
            fileName: "-",
            code: "E_PARSE_NETWORK",
            stage: "network",
            message: "网络异常，解析请求未成功发出。"
          }
        ]
      });
      setParseProgress(100);
    } finally {
      window.clearInterval(progressTimer);
      setUploading(false);
      window.setTimeout(() => setParseProgress(0), 500);
    }
  };

  const handleDownload = async (mode: "single" | "zip") => {
    const payload = {
      mode,
      selectedFileName: selectedResult?.fileName,
      results: data.results,
      metricConfig
    };
    const response = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      setReportMsg(`下载失败（HTTP ${response.status}），请重试。`);
      return;
    }
    const blob = await response.blob();
    const fallback = mode === "single" ? "parsed_result.xlsx" : "parsed_results.zip";
    const fileName = parseDownloadFileName(response.headers.get("content-disposition"), fallback);
    downloadBlob(blob, fileName);
  };

  const handleGenerateReport = async (reportType: (typeof REPORT_TYPES)[number]) => {
    if (!selectedResult) return;
    const response = await fetch("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fileName: selectedResult.fileName, sheets: selectedResult.sheets, reportType })
    });
    const result = (await response.json()) as { message: string };
    setReportMsg(result.message);
  };

  const handleDownloadErrors = () => {
    if (data.errors.length === 0) return;
    const csv = toErrorCsv(data.errors);
    const blob = new Blob([`\ufeff${csv}`], { type: "text/csv;charset=utf-8;" });
    const stamp = new Date().toISOString().slice(0, 19).replaceAll(":", "").replace("T", "_");
    downloadBlob(blob, `parse_errors_${stamp}.csv`);
  };

  return (
    <main className="container">
      {showCelebration && (
        <div className="celebration-layer" aria-hidden="true">
          {Array.from({ length: 28 }).map((_, index) => (
            <span
              key={index}
              className="confetti-piece"
              style={
                {
                  left: `${(index * 17) % 100}%`,
                  animationDelay: `${(index % 7) * 0.08}s`,
                  animationDuration: `${1.8 + (index % 5) * 0.25}s`
                } as CSSProperties
              }
            />
          ))}
        </div>
      )}
      <h1 className="title">峰哥帮你出报告</h1>
      <p className="muted">先完成上传、解析与下载，报告生成功能当前为占位接口。</p>

      <UploadPanel
        uploading={uploading}
        parseProgress={parseProgress}
        files={files.map((item) => ({ id: item.id, name: item.file.name }))}
        onFileChange={handleFileChange}
        onRemoveFile={handleRemoveFile}
        onParse={() => handleParse(false)}
        onMergeParse={() => handleParse(true)}
        canParse={canParse}
      />

      {data.results.length > 0 && (
        <div className="card">
          <div className="result-header">
            <div>
              <strong>选择结果文件：</strong>
              <select
                value={selectedResult?.fileName}
                onChange={(event) => setSelectedFileName(event.target.value)}
                style={{ marginLeft: 8 }}
              >
                {data.results.map((result) => (
                  <option key={result.fileName} value={result.fileName}>
                    {result.fileName}
                  </option>
                ))}
              </select>
            </div>
            <div className="actions" style={{ marginTop: 0 }}>
              <button disabled={!selectedResult} onClick={() => handleDownload("single")}>
                下载当前结果
              </button>
              <button disabled={data.results.length <= 1} onClick={() => handleDownload("zip")}>
                打包下载 ZIP
              </button>
            </div>
          </div>
        </div>
      )}

      {data.errors.length > 0 && (
        <div className="card">
          <div className="result-header">
            <h3 style={{ marginTop: 0, marginBottom: 0 }}>解析异常</h3>
            <div className="actions" style={{ marginTop: 0 }}>
              <button onClick={handleDownloadErrors}>下载错误明细 CSV</button>
            </div>
          </div>
          {data.errors.map((error) => (
            <p key={`${error.fileName}-${error.code}-${error.message}`} className="muted">
              [{error.code}] {error.fileName} ({error.stage ?? "parse"}): {error.message}
            </p>
          ))}
        </div>
      )}

      {data.results.length > 0 && (
        <MetricConfigPanel
          config={metricConfig}
          onChange={setMetricConfig}
          onReset={() => setMetricConfig(createDefaultMetricConfig())}
        />
      )}

      <ResultTable result={selectedResult} metricConfig={metricConfig} />

      <div className="card">
        <h2 style={{ marginTop: 0 }}>3) 生成报告（占位）</h2>
        <p className="muted">下一阶段接入 Gemini API。当前仅返回占位消息和调用链路。</p>
        <div className="actions">
          {REPORT_TYPES.map((reportType) => (
            <button key={reportType} disabled={!selectedResult} onClick={() => handleGenerateReport(reportType)}>
              {reportType}
            </button>
          ))}
        </div>
        {reportMsg && <p style={{ marginBottom: 0 }}>{reportMsg}</p>}
      </div>

      {showSuccessModal && (
        <div className="modal-backdrop" onClick={() => setShowSuccessModal(false)}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <h3 style={{ marginTop: 0, marginBottom: 8 }}>解析成功</h3>
            <p className="muted" style={{ marginBottom: 16 }}>
              {successMessage}
            </p>
            <div className="actions" style={{ marginTop: 0 }}>
              <button onClick={() => setShowSuccessModal(false)}>我知道了</button>
            </div>
          </div>
        </div>
      )}

      {showMergeTipsModal && (
        <div className="modal-backdrop" onClick={() => setShowMergeTipsModal(false)}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <h3 style={{ marginTop: 0, marginBottom: 8 }}>并表解析提示</h3>
            <p className="muted" style={{ marginBottom: 16 }}>
              并表解析需要至少上传 2 张表，请先补充文件后再试。
            </p>
            <div className="actions" style={{ marginTop: 0 }}>
              <button onClick={() => setShowMergeTipsModal(false)}>好的</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
