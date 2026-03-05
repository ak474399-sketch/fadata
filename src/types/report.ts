export type ParsedRow = {
  day: string;
  notificationContent: string;
  d0PushSent: number;
  d0Click: number;
  d0ClickRate: number;
  d1PushSent: number;
  d1Click: number;
  d1ClickRate: number;
};

export type ParsedFileResult = {
  fileName: string;
  rows: ParsedRow[];
};

export type ParseError = {
  fileName: string;
  message: string;
};

export type ParseResponse = {
  results: ParsedFileResult[];
  errors: ParseError[];
};
