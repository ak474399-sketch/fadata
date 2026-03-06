"use client";

import { useEffect, useMemo, useState } from "react";
import type { AnalysisRow, ParsedFileResult } from "@/types/report";

type ResultTableProps = {
  result?: ParsedFileResult;
};

const numberFormatter = new Intl.NumberFormat("en-US");
const decimalFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
});

type TableKey = "dailyByDay" | "byContent" | "byVersionSummary";
type LeadColumn = { key: "batch" | "version" | "day" | "content"; label: string };

const PATH_COLUMNS: Array<{ key: keyof AnalysisRow; label: string; percent?: boolean; decimal?: boolean }> = [
  { key: "firstOpen", label: "first open" },
  { key: "authorizedUsers", label: "通知授权用户数" },
  { key: "authorizationRate", label: "授权率", percent: true },
  { key: "uninstallUsers", label: "卸载用户数" },
  { key: "uninstallRate", label: "卸载率", percent: true },
  { key: "d0PushUsers", label: "DAY0发送用户数" },
  { key: "d0PushEvents", label: "DAY0发送事件数" },
  { key: "d0PenetrationRate", label: "DAY0通知渗透率", percent: true },
  { key: "d0AvgSentPerUser", label: "DAY0人均发送", decimal: true },
  { key: "d0ClickUsers", label: "DAY0点击用户数" },
  { key: "d0ClickEvents", label: "DAY0点击事件数" },
  { key: "d0UserClickRate", label: "DAY0用户点击率", percent: true },
  { key: "d0EventClickRate", label: "DAY0事件点击率", percent: true },
  { key: "d0AvgClickPerUser", label: "DAY0人均点击数", decimal: true },
  { key: "d1PushUsers", label: "DAY1发送用户数" },
  { key: "d1PushEvents", label: "DAY1发送事件数" },
  { key: "d1PenetrationRate", label: "DAY1通知渗透率", percent: true },
  { key: "d1AvgSentPerUser", label: "DAY1人均发送", decimal: true },
  { key: "d1ClickUsers", label: "DAY1点击用户数" },
  { key: "d1ClickEvents", label: "DAY1点击事件数" },
  { key: "d1UserClickRate", label: "DAY1用户点击率", percent: true },
  { key: "d1EventClickRate", label: "DAY1事件点击率", percent: true },
  { key: "d1AvgClickPerUser", label: "DAY1人均点击数", decimal: true }
];

function formatCell(value: number, percent?: boolean, decimal?: boolean): string {
  if (percent) return `${(value * 100).toFixed(2)}%`;
  if (decimal) return decimalFormatter.format(value);
  return numberFormatter.format(value);
}

export function ResultTable({ result }: ResultTableProps) {
  const [activeTable, setActiveTable] = useState<TableKey>("dailyByDay");
  const safeSheets = result?.sheets ?? { dailyByDay: [], byContent: [], byVersionSummary: [] };

  useEffect(() => {
    setActiveTable("dailyByDay");
  }, [result?.fileName]);
  const titleMap: Record<TableKey, string> = {
    dailyByDay: "分日 PUSH 分析",
    byContent: "PUSH 内容分析",
    byVersionSummary: "分版本汇总分析"
  };
  const rows = safeSheets[activeTable];
  const hasBatch = useMemo(() => rows.some((row) => Boolean(row.batch)), [rows]);

  const leadingColumns = useMemo(() => {
    if (activeTable === "dailyByDay") {
      const columns: LeadColumn[] = [
        { key: "version", label: "版本号" },
        { key: "day", label: "天" }
      ];
      if (hasBatch) columns.unshift({ key: "batch" as const, label: "批次" });
      return columns;
    }
    if (activeTable === "byContent") {
      const columns: LeadColumn[] = [
        { key: "version", label: "版本号" },
        { key: "content", label: "内容" }
      ];
      if (hasBatch) columns.unshift({ key: "batch" as const, label: "批次" });
      return columns;
    }
    const columns: LeadColumn[] = [{ key: "version", label: "版本号" }];
    if (hasBatch) columns.unshift({ key: "batch" as const, label: "批次" });
    return columns;
  }, [activeTable, hasBatch]);

  if (!result) {
    return (
      <div className="card">
        <h2 style={{ marginTop: 0 }}>2) 解析结果</h2>
        <p className="muted">暂无数据，请先上传文件并解析。</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>2) 解析结果 - {result.fileName}</h2>
      <p className="muted">三张表：分日 PUSH 分析 / PUSH 内容分析 / 分版本汇总分析。</p>
      <div className="actions" style={{ marginBottom: 12 }}>
        <button disabled={activeTable === "dailyByDay"} onClick={() => setActiveTable("dailyByDay")}>
          分日 PUSH 分析
        </button>
        <button disabled={activeTable === "byContent"} onClick={() => setActiveTable("byContent")}>
          PUSH 内容分析
        </button>
        <button
          disabled={activeTable === "byVersionSummary"}
          onClick={() => setActiveTable("byVersionSummary")}
        >
          分版本汇总分析
        </button>
      </div>
      <p className="muted" style={{ marginBottom: 10 }}>
        当前：{titleMap[activeTable]}
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {leadingColumns.map((column) => (
                <th key={column.key}>{column.label}</th>
              ))}
              {PATH_COLUMNS.map((column) => (
                <th key={String(column.key)}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.version}-${row.day ?? ""}-${row.content ?? ""}-${index}`}>
                {leadingColumns.map((column) => (
                  <td key={column.key}>{row[column.key] ?? "-"}</td>
                ))}
                {PATH_COLUMNS.map((column) => (
                  <td key={String(column.key)}>
                    {formatCell(row[column.key] as number, column.percent, column.decimal)}
                  </td>
                ))}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={leadingColumns.length + PATH_COLUMNS.length}>当前表暂无数据。</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
