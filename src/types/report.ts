export type AnalysisRow = {
  batch?: string;
  version: string;
  day?: string;
  content?: string;
  firstOpen: number;
  authorizedUsers: number;
  authorizationRate: number;
  uninstallUsers: number;
  uninstallRate: number;
  d0PushUsers: number;
  d0PushEvents: number;
  d0PenetrationRate: number;
  d0AvgSentPerUser: number;
  d0ClickUsers: number;
  d0ClickEvents: number;
  d0UserClickRate: number;
  d0EventClickRate: number;
  d0AvgClickPerUser: number;
  d1PushUsers: number;
  d1PushEvents: number;
  d1PenetrationRate: number;
  d1AvgSentPerUser: number;
  d1ClickUsers: number;
  d1ClickEvents: number;
  d1UserClickRate: number;
  d1EventClickRate: number;
  d1AvgClickPerUser: number;
};

export type NotifyCopyRow = {
  batch?: string;
  nthDay: "DAY0" | "DAY1";
  dateRange: string;
  projectCode: string;
  version: string;
  scene: string;
  notifyName: string;
  pushUsers: number;
  pushEvents: number;
  clickUsers: number;
  clickEvents: number;
  userClickRate: number;
  eventClickRate: number;
};

export type ParsedSheets = {
  dailyByDay: AnalysisRow[];
  byContent: AnalysisRow[];
  byVersionSummary: AnalysisRow[];
  byNotifyCopyDay: NotifyCopyRow[];
};

export type SheetKey = "dailyByDay" | "byContent" | "byVersionSummary" | "byNotifyCopyDay";

export type ParsedFileResult = {
  fileName: string;
  sheets: ParsedSheets;
};

export type ParseError = {
  fileName: string;
  code: string;
  message: string;
  stage?: "upload" | "read" | "parse" | "validate" | "upstream" | "network";
};

export type ParseResponse = {
  results: ParsedFileResult[];
  errors: ParseError[];
};
