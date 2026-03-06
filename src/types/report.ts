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

export type ParsedSheets = {
  dailyByDay: AnalysisRow[];
  byContent: AnalysisRow[];
  byVersionSummary: AnalysisRow[];
};

export type ParsedFileResult = {
  fileName: string;
  sheets: ParsedSheets;
};

export type ParseError = {
  fileName: string;
  message: string;
};

export type ParseResponse = {
  results: ParsedFileResult[];
  errors: ParseError[];
};
