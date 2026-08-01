export const researchWarningLabels: Record<string, string> = {
  partial_search_failure: "部分搜索请求失败",
  partial_crawl_failure: "部分参考页面无法读取",
  search_unavailable: "联网搜索暂不可用",
  crawl_unavailable: "网页读取服务暂不可用",
  all_crawls_failed: "参考页面均无法读取",
  reference_extraction_empty: "未提取到可用参考资料",
  reference_relevance_empty: "获取到的资料与当前主题不匹配",
  partial_reference_mismatch: "部分同名或无关资料已自动移除",
  reference_timeout: "联网参考获取超时",
  reference_unavailable: "联网参考暂不可用",
  storyboard_planning_timeout: "联网分镜规划超时，已自动改用普通分镜生成",
  storyboard_planning_unavailable: "联网分镜规划暂不可用，已自动改用普通分镜生成",
  partial_storyboard_prompt_fallback: "个别镜头生成超时，已按对应旁白安全补全",
  storyboard_prompt_fallback: "分镜模型暂不可用，已按每段旁白安全补全",
};

export function researchWarningLabel(warning: string) {
  return researchWarningLabels[warning] ?? "联网参考处理时出现问题";
}
