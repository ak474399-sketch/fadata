"use client";

import { useEffect, useMemo, useState } from "react";
import type { ParsedFileResult } from "@/types/report";

type ResultTableProps = {
  result?: ParsedFileResult;
};

const numberFormatter = new Intl.NumberFormat("en-US");

export function ResultTable({ result }: ResultTableProps) {
  const [selectedDay, setSelectedDay] = useState<string>("all");
  const [selectedContent, setSelectedContent] = useState<string>("all");

  useEffect(() => {
    setSelectedDay("all");
    setSelectedContent("all");
  }, [result?.fileName]);

  if (!result) {
    return (
      <div className="card">
        <h2 style={{ marginTop: 0 }}>2) 解析结果</h2>
        <p className="muted">暂无数据，请先上传文件并解析。</p>
      </div>
    );
  }

  const days = useMemo(
    () => Array.from(new Set(result.rows.map((item) => item.day))).sort(),
    [result.rows]
  );
  const contents = useMemo(
    () => Array.from(new Set(result.rows.map((item) => item.notificationContent))).sort(),
    [result.rows]
  );
  const filteredRows = useMemo(
    () =>
      result.rows.filter(
        (item) =>
          (selectedDay === "all" || item.day === selectedDay) &&
          (selectedContent === "all" || item.notificationContent === selectedContent)
      ),
    [result.rows, selectedDay, selectedContent]
  );

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>2) 解析结果 - {result.fileName}</h2>
      <p className="muted">维度：天 + 通知内容；指标：D0 / D1 发送、点击、点击率。</p>
      <div className="actions" style={{ marginBottom: 12 }}>
        <label>
          天：
          <select style={{ marginLeft: 8 }} value={selectedDay} onChange={(e) => setSelectedDay(e.target.value)}>
            <option value="all">全部</option>
            {days.map((day) => (
              <option key={day} value={day}>
                {day}
              </option>
            ))}
          </select>
        </label>
        <label>
          通知内容：
          <select
            style={{ marginLeft: 8 }}
            value={selectedContent}
            onChange={(e) => setSelectedContent(e.target.value)}
          >
            <option value="all">全部</option>
            {contents.map((content) => (
              <option key={content} value={content}>
                {content}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>天</th>
              <th>通知内容</th>
              <th>D0 PUSH 发送数</th>
              <th>D0 点击数</th>
              <th>D0 点击率</th>
              <th>D1 发送数</th>
              <th>D1 点击数</th>
              <th>D1 点击率</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => (
              <tr key={`${row.day}-${row.notificationContent}`}>
                <td>{row.day}</td>
                <td>{row.notificationContent}</td>
                <td>{numberFormatter.format(row.d0PushSent)}</td>
                <td>{numberFormatter.format(row.d0Click)}</td>
                <td>{(row.d0ClickRate * 100).toFixed(2)}%</td>
                <td>{numberFormatter.format(row.d1PushSent)}</td>
                <td>{numberFormatter.format(row.d1Click)}</td>
                <td>{(row.d1ClickRate * 100).toFixed(2)}%</td>
              </tr>
            ))}
            {filteredRows.length === 0 && (
              <tr>
                <td colSpan={8}>当前筛选条件下暂无数据。</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
