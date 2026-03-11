"use client";

import { useMemo, useState } from "react";
import type { SheetKey } from "@/types/report";
import {
  METRIC_DEFINITIONS,
  METRIC_MODULE_LABELS,
  type MetricConfigState,
  type MetricConfigItem
} from "@/lib/metric-config";

type MetricConfigPanelProps = {
  config: MetricConfigState;
  onChange: (next: MetricConfigState) => void;
  onReset: () => void;
};

export function MetricConfigPanel({ config, onChange, onReset }: MetricConfigPanelProps) {
  const [activeModule, setActiveModule] = useState<SheetKey>("dailyByDay");
  const [draggingId, setDraggingId] = useState<string>("");
  const moduleItems = config[activeModule] ?? [];
  const defsById = useMemo(
    () => new Map(METRIC_DEFINITIONS[activeModule].map((item) => [item.id, item.label])),
    [activeModule]
  );

  const updateModule = (updater: (items: MetricConfigItem[]) => MetricConfigItem[]) => {
    onChange({
      ...config,
      [activeModule]: updater(moduleItems)
    });
  };

  return (
    <div className="card">
      <div className="result-header">
        <div>
          <h2 style={{ marginTop: 0, marginBottom: 6 }}>指标配置</h2>
          <p className="muted">按表模块配置指标：勾选控制展示，拖动控制导出和展示顺序。</p>
        </div>
        <div className="actions" style={{ marginTop: 0 }}>
          <button onClick={onReset}>恢复默认</button>
        </div>
      </div>
      <div className="actions" style={{ marginTop: 10, marginBottom: 10 }}>
        {(Object.keys(METRIC_MODULE_LABELS) as SheetKey[]).map((key) => (
          <button key={key} disabled={activeModule === key} onClick={() => setActiveModule(key)}>
            {METRIC_MODULE_LABELS[key]}
          </button>
        ))}
      </div>
      <div className="metric-config-list">
        {moduleItems.map((item, index) => (
          <label
            key={item.id}
            className={`metric-item ${draggingId === item.id ? "metric-item-dragging" : ""}`}
            draggable
            onDragStart={() => setDraggingId(item.id)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={() => {
              if (!draggingId || draggingId === item.id) return;
              const from = moduleItems.findIndex((x) => x.id === draggingId);
              const to = moduleItems.findIndex((x) => x.id === item.id);
              if (from < 0 || to < 0) return;
              updateModule((items) => {
                const next = [...items];
                const [moved] = next.splice(from, 1);
                next.splice(to, 0, moved);
                return next;
              });
              setDraggingId("");
            }}
            onDragEnd={() => setDraggingId("")}
          >
            <span className="metric-item-grip">::</span>
            <input
              type="checkbox"
              checked={item.visible}
              onChange={(event) => {
                const checked = event.target.checked;
                updateModule((items) => items.map((x) => (x.id === item.id ? { ...x, visible: checked } : x)));
              }}
            />
            <span>{index + 1}. {defsById.get(item.id) ?? item.id}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

