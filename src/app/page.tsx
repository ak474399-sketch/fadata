"use client";

import { useMemo, useState } from "react";
import { ResultTable } from "@/components/result-table";
import { UploadPanel } from "@/components/upload-panel";
import type { ParseResponse, ParsedFileResult } from "@/types/report";

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function HomePage() {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [data, setData] = useState<ParseResponse>({ results: [], errors: [] });
  const [selectedFileName, setSelectedFileName] = useState<string>("");
  const [reportMsg, setReportMsg] = useState("");

  const selectedResult = useMemo<ParsedFileResult | undefined>(
    () => data.results.find((item) => item.fileName === selectedFileName) ?? data.results[0],
    [data.results, selectedFileName]
  );

  const canParse = files.length > 0;

  const handleFileChange = (incoming: FileList | null) => {
    setFiles(incoming ? Array.from(incoming) : []);
    setReportMsg("");
  };

  const handleParse = async () => {
    if (!files.length) return;
    setUploading(true);
    setReportMsg("");
    setData({ results: [], errors: [] });
    const form = new FormData();
    for (const file of files) form.append("files", file);

    try {
      const response = await fetch("/api/parse", { method: "POST", body: form });
      let result: ParseResponse;
      try {
        result = (await response.json()) as ParseResponse;
      } catch {
        result = {
          results: [],
          errors: [{ fileName: "-", message: "解析接口返回异常，无法解析响应内容。" }]
        };
      }

      if (!response.ok && result.errors.length === 0) {
        result.errors.push({ fileName: "-", message: `解析失败（HTTP ${response.status}）。` });
      }

      setData(result);
      if (result.results.length) {
        setSelectedFileName(result.results[0].fileName);
      }
    } catch {
      setData({
        results: [],
        errors: [{ fileName: "-", message: "网络异常，解析请求未成功发出。" }]
      });
    } finally {
      setUploading(false);
    }
  };

  const handleDownload = async (mode: "single" | "zip") => {
    const payload = {
      mode,
      selectedFileName: selectedResult?.fileName,
      results: data.results
    };
    const response = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) return;
    const blob = await response.blob();
    const fallback = mode === "single" ? "parsed_result.csv" : "parsed_results.zip";
    const headerName = response.headers.get("content-disposition");
    const fileName = headerName?.split("filename=")[1]?.replaceAll("\"", "") ?? fallback;
    downloadBlob(blob, fileName);
  };

  const handleGenerateReport = async () => {
    if (!selectedResult) return;
    const response = await fetch("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fileName: selectedResult.fileName, rows: selectedResult.rows })
    });
    const result = (await response.json()) as { message: string };
    setReportMsg(result.message);
  };

  return (
    <main className="container">
      <h1 className="title">Next + Python 通知数据解析服务</h1>
      <p className="muted">先完成上传、解析与下载，报告生成功能当前为占位接口。</p>

      <UploadPanel
        uploading={uploading}
        onFileChange={handleFileChange}
        onParse={handleParse}
        onDownloadCurrent={() => handleDownload("single")}
        onDownloadZip={() => handleDownload("zip")}
        canParse={canParse}
        canDownloadCurrent={Boolean(selectedResult)}
        canDownloadZip={data.results.length > 1}
      />

      {files.length > 0 && (
        <div className="card">
          <strong>已上传文件</strong>
          <div style={{ marginTop: 10 }}>
            {files.map((file) => (
              <span className="chip" key={file.name}>
                {file.name}
              </span>
            ))}
          </div>
        </div>
      )}

      {data.results.length > 0 && (
        <div className="card">
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
      )}

      {data.errors.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>解析异常</h3>
          {data.errors.map((error) => (
            <p key={`${error.fileName}-${error.message}`} className="muted">
              {error.fileName}: {error.message}
            </p>
          ))}
        </div>
      )}

      <ResultTable result={selectedResult} />

      <div className="card">
        <h2 style={{ marginTop: 0 }}>3) 生成报告（占位）</h2>
        <p className="muted">下一阶段接入 Gemini API。当前仅返回占位消息和调用链路。</p>
        <div className="actions">
          <button disabled={!selectedResult} onClick={handleGenerateReport}>
            生成报告
          </button>
        </div>
        {reportMsg && <p style={{ marginBottom: 0 }}>{reportMsg}</p>}
      </div>
    </main>
  );
}
