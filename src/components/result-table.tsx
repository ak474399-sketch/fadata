"use client";

import { useEffect, useMemo, useState } from "react";
import { resolveMetricColumns, type MetricConfigState } from "@/lib/metric-config";
import type { AnalysisRow, NotifyCopyRow, ParsedFileResult } from "@/types/report";

type ResultTableProps = {
  result?: ParsedFileResult;
  metricConfig: MetricConfigState;
};

const numberFormatter = new Intl.NumberFormat("en-US");
const decimalFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
});

type TableKey = "dailyByDay" | "byContent" | "byVersionSummary" | "byNotifyCopyDay";
type LeadColumn = { key: "batch" | "version" | "day" | "content"; label: string };
type NotifyLeadColumn = {
  key: "batch" | "nthDay" | "dateRange" | "projectCode" | "version" | "scene" | "notifyName";
  label: string;
};

function formatCell(value: number, percent?: boolean, decimal?: boolean): string {
  if (percent) return `${(value * 100).toFixed(2)}%`;
  if (decimal) return decimalFormatter.format(value);
  return numberFormatter.format(value);
}

export function ResultTable({ result, metricConfig }: ResultTableProps) {
  const [activeTable, setActiveTable] = useState<TableKey>("dailyByDay");
  const safeSheets = result?.sheets ?? {
    dailyByDay: [],
    byContent: [],
    byVersionSummary: [],
    byNotifyCopyDay: []
  };

  useEffect(() => {
    setActiveTable("dailyByDay");
  }, [result?.fileName]);
  const titleMap: Record<TableKey, string> = {
    dailyByDay: "分日 PUSH 分析",
    byContent: "PUSH 内容分析",
    byVersionSummary: "分版本汇总分析",
    byNotifyCopyDay: "通知文案分天分析"
  };
  const rows = safeSheets[activeTable] as AnalysisRow[];
  const notifyRows = safeSheets.byNotifyCopyDay as NotifyCopyRow[];
  const hasBatch = useMemo(() => {
    if (activeTable === "byNotifyCopyDay") {
      return notifyRows.some((row) => Boolean(row.batch));
    }
    return rows.some((row) => Boolean(row.batch));
  }, [activeTable, notifyRows, rows]);

  const leadingColumns = useMemo(() => {
    if (activeTable === "byNotifyCopyDay") {
      return [];
    }
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

  const notifyLeadingColumns = useMemo(() => {
    const columns: NotifyLeadColumn[] = [
      { key: "nthDay", label: "第N天" },
      { key: "dateRange", label: "日期" },
      { key: "projectCode", label: "项目代号" },
      { key: "version", label: "版本" },
      { key: "scene", label: "通知场景" },
      { key: "notifyName", label: "通知命名" }
    ];
    if (hasBatch) columns.unshift({ key: "batch", label: "批次" });
    return columns;
  }, [hasBatch]);
  const metricColumns = useMemo(() => resolveMetricColumns(activeTable, metricConfig), [activeTable, metricConfig]);

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
      <p className="muted">四张表：分日 PUSH 分析 / PUSH 内容分析 / 分版本汇总分析 / 通知文案分天分析。</p>
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
        <button disabled={activeTable === "byNotifyCopyDay"} onClick={() => setActiveTable("byNotifyCopyDay")}>
          通知文案分天分析
        </button>
      </div>
      <p className="muted" style={{ marginBottom: 10 }}>
        当前：{titleMap[activeTable]}
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {activeTable === "byNotifyCopyDay" ? (
                <>
                  {notifyLeadingColumns.map((column) => (
                    <th key={column.key}>{column.label}</th>
                  ))}
                  {metricColumns.map((column) => (
                    <th key={column.id}>{column.label}</th>
                  ))}
                </>
              ) : (
                <>
                  {leadingColumns.map((column) => (
                    <th key={column.key}>{column.label}</th>
                  ))}
                  {metricColumns.map((column) => (
                    <th key={column.id}>{column.label}</th>
                  ))}
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {activeTable === "byNotifyCopyDay"
              ? notifyRows.map((row, index) => (
                  <tr key={`${row.nthDay}-${row.projectCode}-${row.version}-${row.notifyName}-${index}`}>
                    {notifyLeadingColumns.map((column) => (
                      <td key={column.key}>{row[column.key] ?? "-"}</td>
                    ))}
                    {metricColumns.map((column) => (
                      <td key={column.id}>
                        {formatCell(
                          Number(row[column.id as keyof NotifyCopyRow] ?? 0),
                          column.percent,
                          column.decimal
                        )}
                      </td>
                    ))}
                  </tr>
                ))
              : rows.map((row, index) => (
                  <tr key={`${row.version}-${row.day ?? ""}-${row.content ?? ""}-${index}`}>
                    {leadingColumns.map((column) => (
                      <td key={column.key}>{row[column.key] ?? "-"}</td>
                    ))}
                    {metricColumns.map((column) => (
                      <td key={column.id}>
                        {formatCell(
                          Number(row[column.id as keyof AnalysisRow] ?? 0),
                          column.percent,
                          column.decimal
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
            {((activeTable === "byNotifyCopyDay" && notifyRows.length === 0) ||
              (activeTable !== "byNotifyCopyDay" && rows.length === 0)) && (
              <tr>
                <td
                  colSpan={
                    activeTable === "byNotifyCopyDay"
                      ? notifyLeadingColumns.length + metricColumns.length
                      : leadingColumns.length + metricColumns.length
                  }
                >
                  当前表暂无数据。
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
