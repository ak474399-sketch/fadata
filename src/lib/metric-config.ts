import type { SheetKey } from "@/types/report";

export type MetricColumnDef = {
  id: string;
  label: string;
  percent?: boolean;
  decimal?: boolean;
};

export type MetricConfigItem = {
  id: string;
  visible: boolean;
};

export type MetricConfigState = Record<SheetKey, MetricConfigItem[]>;

const ANALYSIS_METRICS: MetricColumnDef[] = [
  { id: "firstOpen", label: "first open" },
  { id: "authorizedUsers", label: "通知授权用户数" },
  { id: "authorizationRate", label: "授权率", percent: true },
  { id: "uninstallUsers", label: "卸载用户数" },
  { id: "uninstallRate", label: "卸载率", percent: true },
  { id: "d0PushUsers", label: "DAY0发送用户数" },
  { id: "d0PushEvents", label: "DAY0发送事件数" },
  { id: "d0PenetrationRate", label: "DAY0通知渗透率", percent: true },
  { id: "d0AvgSentPerUser", label: "DAY0人均发送", decimal: true },
  { id: "d0ClickUsers", label: "DAY0点击用户数" },
  { id: "d0ClickEvents", label: "DAY0点击事件数" },
  { id: "d0UserClickRate", label: "DAY0用户点击率", percent: true },
  { id: "d0EventClickRate", label: "DAY0事件点击率", percent: true },
  { id: "d0AvgClickPerUser", label: "DAY0人均点击数", decimal: true },
  { id: "d1PushUsers", label: "DAY1发送用户数" },
  { id: "d1PushEvents", label: "DAY1发送事件数" },
  { id: "d1PenetrationRate", label: "DAY1通知渗透率", percent: true },
  { id: "d1AvgSentPerUser", label: "DAY1人均发送", decimal: true },
  { id: "d1ClickUsers", label: "DAY1点击用户数" },
  { id: "d1ClickEvents", label: "DAY1点击事件数" },
  { id: "d1UserClickRate", label: "DAY1用户点击率", percent: true },
  { id: "d1EventClickRate", label: "DAY1事件点击率", percent: true },
  { id: "d1AvgClickPerUser", label: "DAY1人均点击数", decimal: true }
];

const NOTIFY_COPY_METRICS: MetricColumnDef[] = [
  { id: "pushUsers", label: "通知用户数" },
  { id: "pushEvents", label: "通知事件数" },
  { id: "clickUsers", label: "点击用户数" },
  { id: "clickEvents", label: "点击事件数" },
  { id: "userClickRate", label: "点击率(用户)", percent: true },
  { id: "eventClickRate", label: "点击率(事件)", percent: true }
];

export const METRIC_MODULE_LABELS: Record<SheetKey, string> = {
  dailyByDay: "分日 PUSH 分析",
  byContent: "PUSH 内容分析",
  byVersionSummary: "分版本汇总分析",
  byNotifyCopyDay: "通知文案分天分析"
};

export const METRIC_DEFINITIONS: Record<SheetKey, MetricColumnDef[]> = {
  dailyByDay: ANALYSIS_METRICS,
  byContent: ANALYSIS_METRICS,
  byVersionSummary: ANALYSIS_METRICS,
  byNotifyCopyDay: NOTIFY_COPY_METRICS
};

export function createDefaultMetricConfig(): MetricConfigState {
  const out = {} as MetricConfigState;
  (Object.keys(METRIC_DEFINITIONS) as SheetKey[]).forEach((key) => {
    out[key] = METRIC_DEFINITIONS[key].map((item) => ({ id: item.id, visible: true }));
  });
  return out;
}

export function resolveMetricColumns(sheet: SheetKey, config?: MetricConfigState): MetricColumnDef[] {
  const defs = METRIC_DEFINITIONS[sheet];
  if (!config || !config[sheet]?.length) return defs;
  const byId = new Map(defs.map((item) => [item.id, item]));
  return config[sheet]
    .filter((item) => item.visible)
    .map((item) => byId.get(item.id))
    .filter((item): item is MetricColumnDef => Boolean(item));
}

