"use client";

import type { ChangeEvent } from "react";

type UploadPanelProps = {
  uploading: boolean;
  onFileChange: (files: FileList | null) => void;
  onParse: () => void;
  onDownloadCurrent: () => void;
  onDownloadZip: () => void;
  canParse: boolean;
  canDownloadCurrent: boolean;
  canDownloadZip: boolean;
};

export function UploadPanel({
  uploading,
  onFileChange,
  onParse,
  onDownloadCurrent,
  onDownloadZip,
  canParse,
  canDownloadCurrent,
  canDownloadZip
}: UploadPanelProps) {
  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    onFileChange(event.target.files);
  };

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>1) 上传并解析表格</h2>
      <p className="muted">支持 csv / tsv / xlsx / xls，可一次上传多个文件。</p>
      <input multiple type="file" accept=".csv,.tsv,.xlsx,.xls" onChange={handleFileChange} />
      <div className="actions">
        <button disabled={!canParse || uploading} onClick={onParse}>
          {uploading ? "解析中..." : "开始解析"}
        </button>
        <button disabled={!canDownloadCurrent} onClick={onDownloadCurrent}>
          下载当前结果
        </button>
        <button disabled={!canDownloadZip} onClick={onDownloadZip}>
          打包下载 ZIP
        </button>
      </div>
    </div>
  );
}
