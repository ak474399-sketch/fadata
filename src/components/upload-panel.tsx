"use client";

import { useRef, useState, type ChangeEvent, type DragEvent } from "react";

type UploadPanelProps = {
  uploading: boolean;
  parseProgress: number;
  files: File[];
  onFileChange: (files: FileList | null) => void;
  onParse: () => void;
  canParse: boolean;
};

export function UploadPanel({
  uploading,
  parseProgress,
  files,
  onFileChange,
  onParse,
  canParse
}: UploadPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [samplePassword, setSamplePassword] = useState("");
  const [sampleError, setSampleError] = useState("");

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    onFileChange(event.target.files);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
    onFileChange(event.dataTransfer.files);
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(true);
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
  };

  const handleSampleDownload = async () => {
    setSampleError("");
    const response = await fetch(`/api/sample-data?password=${encodeURIComponent(samplePassword)}`);
    if (!response.ok) {
      let message = "示例文件下载失败。";
      try {
        const data = (await response.json()) as { message?: string };
        if (data.message) message = data.message;
      } catch {
        // ignore parse error
      }
      setSampleError(message);
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "DATA1.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>1) 上传并解析表格</h2>
      <div className="upload-grid">
        <div>
          <p className="muted">支持 csv / tsv / xlsx / xls，可一次上传多个文件。</p>
          <div className="sample-row">
            <span className="muted">示例文件：DATA1.csv</span>
            <input
              className="sample-password"
              type="password"
              placeholder="输入示例密码"
              value={samplePassword}
              onChange={(event) => setSamplePassword(event.target.value)}
            />
            <button type="button" onClick={handleSampleDownload}>
              下载示例
            </button>
          </div>
          {sampleError && (
            <p className="muted" style={{ marginTop: 8 }}>
              {sampleError}
            </p>
          )}
          <div
            className={`dropzone ${dragActive ? "dropzone-active" : ""}`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => inputRef.current?.click()}
          >
            拖拽文件到此处，或点击选择文件
          </div>
          <input
            ref={inputRef}
            className="hidden-file-input"
            multiple
            type="file"
            accept=".csv,.tsv,.xlsx,.xls"
            onChange={handleFileChange}
          />
          <div className="actions">
            <button disabled={!canParse || uploading} onClick={onParse}>
              {uploading ? "解析中..." : "开始解析"}
            </button>
          </div>
          {uploading && (
            <div style={{ marginTop: 12 }}>
              <div className="muted" style={{ marginBottom: 6 }}>
                解析进度：{Math.round(parseProgress)}%
              </div>
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${Math.max(0, Math.min(100, parseProgress))}%` }} />
              </div>
            </div>
          )}
        </div>
        <div>
          <strong>已上传文件</strong>
          <div style={{ marginTop: 10 }}>
            {files.length === 0 && <p className="muted">暂无文件</p>}
            {files.map((file) => (
              <span className="chip" key={file.name}>
                {file.name}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
