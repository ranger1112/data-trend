import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  CheckCircle2,
  AlertTriangle,
  Database,
  FileText,
  Filter,
  ListChecks,
  Play,
  RadioTower,
  RefreshCcw,
  Save,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const DEFAULT_URL = "https://www.stats.gov.cn/sj/zxfb/202604/t20260416_1963320.html";
const DEFAULT_CPI_URL = "https://www.stats.gov.cn/sj/zxfb/202604/t20260413_1963263.html";

type Overview = {
  regions: number;
  indicators: number;
  published_values: number;
  latest_period: string | null;
  updated_at: string | null;
  cache_ttl_seconds: number;
};

type DataSource = {
  id: number;
  name: string;
  entry_url: string;
  source: string;
  type: string;
  enabled: boolean;
};

type DataSourceHealth = {
  id: number;
  name: string;
  type: string;
  enabled: boolean;
  entry_url: string;
  latest_job_status: string | null;
  latest_job_finished_at: string | null;
  latest_error_type: string | null;
  latest_error_message: string | null;
  total_jobs: number;
  success_jobs: number;
  failed_jobs: number;
  success_rate: number;
};

type Region = {
  id: number;
  name: string;
  level: string;
  parent_id: number | null;
};

type Indicator = {
  id: number;
  code: string;
  name: string;
  display_name: string | null;
  category: string;
  unit: string | null;
  description: string | null;
  precision: number;
  sort_order: number;
  default_dimensions: Record<string, string>;
  miniapp_visible: boolean;
};

type CrawlJob = {
  id: number;
  data_source_id: number | null;
  schedule_id: number | null;
  target_url: string | null;
  status: string;
  trigger: string;
  retry_count: number;
  max_retries: number;
  next_retry_at: string | null;
  timeout_seconds: number;
  locked_at: string | null;
  locked_by: string | null;
  total_records: number;
  imported_records: number;
  skipped_records: number;
  error_type: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
};

type CrawlRecord = {
  id: number;
  title: string;
  url: string;
  status: string;
  published_at: string | null;
  parsed_at: string | null;
};

type StatValue = {
  id: number;
  region: string;
  indicator_code: string;
  indicator_name: string;
  period: string;
  value: number;
  status: string;
  dimensions: Record<string, string>;
};

type Schedule = {
  id: number;
  name: string;
  target_url: string;
  data_source_id: number | null;
  interval_minutes: number;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
};

type QualityReport = {
  id: number;
  crawl_job_id: number | null;
  period: string | null;
  status: string;
  actual_regions: number;
  expected_regions: number;
  checked_values: number;
  errors: string[];
  warnings: string[];
  details: {
    severity: string;
    rule: string;
    message: string;
    indicator?: string;
    region?: string;
    period?: string;
    value?: number;
    dimensions?: Record<string, unknown>;
  }[];
  created_at: string;
};

type DataSourceDetail = {
  data_source: DataSource;
  health: DataSourceHealth | null;
  recent_jobs: CrawlJob[];
  schedules: Schedule[];
  quality_reports: QualityReport[];
  available_actions: string[];
};

type CrawlJobDetail = {
  job: CrawlJob;
  data_source: DataSource | null;
  schedule: Schedule | null;
  quality_reports: QualityReport[];
  duration_seconds: number | null;
  retry_available: boolean;
};

type QualityReportDetail = QualityReport & {
  error_details: QualityReport["details"];
  warning_details: QualityReport["details"];
  suggested_actions: string[];
};

type AppConfig = {
  key: string;
  value: Record<string, unknown>;
  description: string | null;
  updated_at: string;
};

type PublishBatch = {
  id: number;
  action: string;
  item_count: number;
  reason: string | null;
  created_at: string;
};

type OpsSummary = {
  jobs_last_24h: number;
  failed_jobs_last_24h: number;
  pending_jobs: number;
  running_jobs: number;
  quality_failed_reports: number;
  review_pending_values: number;
  last_success_at: string | null;
  next_schedule_at: string | null;
};

type DataSourceForm = {
  name: string;
  entry_url: string;
  source: string;
  type: string;
  enabled: boolean;
};

type AuthState = {
  token: string;
  username: string;
  role: string;
};

function App() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [dataSourceTypes, setDataSourceTypes] = useState<string[]>([]);
  const [sourceHealth, setSourceHealth] = useState<DataSourceHealth[]>([]);
  const [regions, setRegions] = useState<Region[]>([]);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [jobs, setJobs] = useState<CrawlJob[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [qualityReports, setQualityReports] = useState<QualityReport[]>([]);
  const [configs, setConfigs] = useState<AppConfig[]>([]);
  const [publishBatches, setPublishBatches] = useState<PublishBatch[]>([]);
  const [opsSummary, setOpsSummary] = useState<OpsSummary | null>(null);
  const [records, setRecords] = useState<CrawlRecord[]>([]);
  const [statValues, setStatValues] = useState<StatValue[]>([]);
  const [sourceForm, setSourceForm] = useState<DataSourceForm>({
    name: "国家统计局房价指数",
    entry_url: DEFAULT_URL,
    source: "国家统计局",
    type: "housing_price",
    enabled: true,
  });
  const [selectedSourceId, setSelectedSourceId] = useState<string>("");
  const [adHocUrl, setAdHocUrl] = useState(DEFAULT_URL);
  const [statStatus, setStatStatus] = useState("ready_for_review");
  const [jobStatus, setJobStatus] = useState("");
  const [recordKeyword, setRecordKeyword] = useState("");
  const [recordStatus, setRecordStatus] = useState("");
  const [recordFrom, setRecordFrom] = useState("");
  const [recordTo, setRecordTo] = useState("");
  const [statRegionId, setStatRegionId] = useState("");
  const [statIndicatorCode, setStatIndicatorCode] = useState("");
  const [statPeriod, setStatPeriod] = useState("");
  const [statHouseType, setStatHouseType] = useState("");
  const [statAreaType, setStatAreaType] = useState("");
  const [statDataSourceId, setStatDataSourceId] = useState("");
  const [scheduleName, setScheduleName] = useState("每日房价抓取");
  const [scheduleUrl, setScheduleUrl] = useState(DEFAULT_URL);
  const [scheduleInterval, setScheduleInterval] = useState("1440");
  const [rejectReason, setRejectReason] = useState("");
  const [selectedStatIds, setSelectedStatIds] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [message, setMessage] = useState("");
  const [auth, setAuth] = useState<AuthState | null>(() => {
    const raw = window.localStorage.getItem("dataTrendAdminAuth");
    return raw ? JSON.parse(raw) : null;
  });
  const [loginForm, setLoginForm] = useState({ username: "admin", password: "admin" });
  const [sourceDetail, setSourceDetail] = useState<DataSourceDetail | null>(null);
  const [jobDetail, setJobDetail] = useState<CrawlJobDetail | null>(null);
  const [qualityDetail, setQualityDetail] = useState<QualityReportDetail | null>(null);
  const [configDrafts, setConfigDrafts] = useState<Record<string, string>>({});
  const [indicatorDrafts, setIndicatorDrafts] = useState<Record<string, Partial<Indicator>>>({});

  async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(auth?.token ? { Authorization: `Bearer ${auth.token}` } : {}),
        ...(options?.headers ?? {}),
      },
      ...options,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || response.statusText);
    }
    return response.json();
  }

  async function login(event: React.FormEvent) {
    event.preventDefault();
    const response = await fetch(`${API_BASE}/admin/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(loginForm),
    });
    if (!response.ok) {
      setMessage("登录失败");
      return;
    }
    const body = await response.json();
    const nextAuth = { token: body.access_token, username: body.username, role: body.role };
    window.localStorage.setItem("dataTrendAdminAuth", JSON.stringify(nextAuth));
    setAuth(nextAuth);
    setMessage("");
  }

  function logout() {
    window.localStorage.removeItem("dataTrendAdminAuth");
    setAuth(null);
  }

  async function refresh() {
    const [
      overviewRes,
      sourcesRes,
      sourceTypesRes,
      sourceHealthRes,
      regionsRes,
      indicatorsRes,
      jobsRes,
      recordsRes,
      statValuesRes,
      schedulesRes,
      reportsRes,
      configsRes,
      batchesRes,
      opsSummaryRes,
    ] = await Promise.all([
      request<Overview>("/mini/dashboard/overview"),
      request<DataSource[]>("/admin/data-sources"),
      request<string[]>("/admin/data-source-types"),
      request<DataSourceHealth[]>("/admin/data-sources/health"),
      request<Region[]>("/mini/regions"),
      request<Indicator[]>("/mini/indicators"),
      request<CrawlJob[]>(`/admin/crawl-jobs${buildQuery({ status: jobStatus })}`),
      request<CrawlRecord[]>(
        `/admin/crawl-records${buildQuery({
          status: recordStatus,
          keyword: recordKeyword,
          published_from: recordFrom,
          published_to: recordTo,
        })}`,
      ),
      request<StatValue[]>(
        `/admin/stat-values${buildQuery({
          status: statStatus,
          region_id: statRegionId,
          indicator_code: statIndicatorCode,
          period: statPeriod,
          house_type: statHouseType,
          area_type: statAreaType,
          data_source_id: statDataSourceId,
        })}`,
      ),
      request<Schedule[]>("/admin/schedules"),
      request<QualityReport[]>("/admin/quality-reports"),
      request<AppConfig[]>("/admin/configs"),
      request<PublishBatch[]>("/admin/publish-batches"),
      request<OpsSummary>("/admin/ops/summary"),
    ]);
    setOverview(overviewRes);
    setDataSources(sourcesRes);
    setDataSourceTypes(sourceTypesRes);
    setSourceHealth(sourceHealthRes);
    setRegions(regionsRes);
    setIndicators(indicatorsRes);
    setJobs(jobsRes);
    setRecords(recordsRes);
    setStatValues(statValuesRes);
    setSchedules(schedulesRes);
    setQualityReports(reportsRes);
    setConfigs(configsRes);
    setConfigDrafts((drafts) => {
      const next = { ...drafts };
      configsRes.forEach((config) => {
        if (!next[config.key]) next[config.key] = JSON.stringify(config.value, null, 2);
      });
      return next;
    });
    setPublishBatches(batchesRes);
    setOpsSummary(opsSummaryRes);
    setSelectedStatIds((ids) => ids.filter((id) => statValuesRes.some((value) => value.id === id)));
  }

  async function createDataSource(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      await request<DataSource>("/admin/data-sources", {
        method: "POST",
        body: JSON.stringify(sourceForm),
      });
      setMessage("数据源已保存");
      await refresh();
    } finally {
      setSaving(false);
    }
  }

  async function toggleDataSource(source: DataSource) {
    if (!window.confirm(`${source.enabled ? "停用" : "启用"}数据源「${source.name}」？`)) return;
    await request<DataSource>(`/admin/data-sources/${source.id}`, {
      method: "PATCH",
      body: JSON.stringify({ enabled: !source.enabled }),
    });
    await refresh();
  }

  async function loadSourceDetail(id: number) {
    const detail = await request<DataSourceDetail>(`/admin/data-sources/${id}/detail`);
    setSourceDetail(detail);
  }

  async function loadJobDetail(id: number) {
    const detail = await request<CrawlJobDetail>(`/admin/crawl-jobs/${id}/detail`);
    setJobDetail(detail);
  }

  async function loadQualityDetail(id: number) {
    const detail = await request<QualityReportDetail>(`/admin/quality-reports/${id}`);
    setQualityDetail(detail);
  }

  async function saveConfig(config: AppConfig) {
    let value: Record<string, unknown>;
    try {
      value = JSON.parse(configDrafts[config.key] ?? "{}");
    } catch {
      setMessage(`${config.key} 不是合法 JSON`);
      return;
    }
    await request<AppConfig>(`/admin/configs/${config.key}`, {
      method: "PATCH",
      body: JSON.stringify({ value, description: config.description }),
    });
    setMessage("配置已保存");
    await refresh();
  }

  async function saveIndicator(indicator: Indicator) {
    const draft = indicatorDrafts[indicator.code] || {};
    await request<Indicator>(`/admin/indicators/${indicator.code}`, {
      method: "PATCH",
      body: JSON.stringify(draft),
    });
    setMessage("指标配置已保存");
    await refresh();
  }

  async function runImport() {
    setRunning(true);
    try {
      const payload =
        selectedSourceId.length > 0
          ? { data_source_id: Number(selectedSourceId), run_now: true }
          : { url: adHocUrl, run_now: true };
      await request<CrawlJob>("/admin/crawl-jobs", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setMessage("抓取任务已提交");
      await refresh();
    } finally {
      setRunning(false);
    }
  }

  async function patchStatValue(id: number, value: number) {
    await request<StatValue>(`/admin/stat-values/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ value }),
    });
    await refresh();
  }

  async function publishSelected() {
    if (selectedStatIds.length === 0) return;
    setPublishing(true);
    try {
      await request<{ published: number }>("/admin/review-batches/publish", {
        method: "POST",
        body: JSON.stringify({ ids: selectedStatIds }),
      });
      setMessage("已发布选中数据");
      setSelectedStatIds([]);
      await refresh();
    } finally {
      setPublishing(false);
    }
  }

  async function rejectSelected() {
    if (selectedStatIds.length === 0) return;
    await request<{ rejected: number }>("/admin/review-batches/reject", {
      method: "POST",
      body: JSON.stringify({ ids: selectedStatIds, reason: rejectReason || "人工驳回" }),
    });
    setMessage("已驳回选中数据");
    setSelectedStatIds([]);
    await refresh();
  }

  async function createSchedule(event: React.FormEvent) {
    event.preventDefault();
    await request<Schedule>("/admin/schedules", {
      method: "POST",
      body: JSON.stringify({
        name: scheduleName,
        target_url: scheduleUrl,
        interval_minutes: Number(scheduleInterval),
        enabled: true,
      }),
    });
    setMessage("调度配置已创建");
    await refresh();
  }

  async function toggleSchedule(schedule: Schedule) {
    if (!window.confirm(`${schedule.enabled ? "停用" : "启用"}调度「${schedule.name}」？`)) return;
    await request<Schedule>(`/admin/schedules/${schedule.id}`, {
      method: "PATCH",
      body: JSON.stringify({ enabled: !schedule.enabled }),
    });
    await refresh();
  }

  async function runDueSchedules() {
    const jobs = await request<CrawlJob[]>("/admin/schedules/run-due", { method: "POST" });
    setMessage(`已创建 ${jobs.length} 个到期任务`);
    await refresh();
  }

  async function retryJob(id: number) {
    await request<CrawlJob>(`/admin/crawl-jobs/${id}/retry`, { method: "POST" });
    setMessage("已提交重试任务");
    await refresh();
  }

  async function cancelJob(id: number) {
    if (!window.confirm(`取消任务 #${id}？`)) return;
    await request<CrawlJob>(`/admin/crawl-jobs/${id}/cancel`, { method: "POST" });
    setMessage("任务已取消");
    await refresh();
  }

  function toggleStatSelection(id: number) {
    setSelectedStatIds((ids) => (ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id]));
  }

  const activeJobs = useMemo(
    () => jobs.filter((job) => job.status === "pending" || job.status === "running").length,
    [jobs],
  );
  const healthBySourceId = useMemo(
    () => new Map(sourceHealth.map((item) => [item.id, item])),
    [sourceHealth],
  );

  useEffect(() => {
    if (auth) refresh().catch((error) => setMessage(error.message));
  }, [auth, jobStatus, statStatus]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (activeJobs > 0) {
        refresh().catch((error) => setMessage(error.message));
      }
    }, 5000);
    return () => window.clearInterval(timer);
  }, [activeJobs, jobStatus, recordKeyword, recordStatus, recordFrom, recordTo, statStatus, statRegionId, statIndicatorCode, statPeriod, statHouseType, statAreaType, statDataSourceId]);

  if (!auth) {
    return (
      <main>
        <section className="loginPanel">
          <p className="eyebrow">data-trend</p>
          <h1>管理端登录</h1>
          {message && <div className="notice">{message}</div>}
          <form className="formGrid" onSubmit={login}>
            <input
              value={loginForm.username}
              onChange={(event) => setLoginForm({ ...loginForm, username: event.target.value })}
              placeholder="用户名"
            />
            <input
              type="password"
              value={loginForm.password}
              onChange={(event) => setLoginForm({ ...loginForm, password: event.target.value })}
              placeholder="密码"
            />
            <button type="submit">登录</button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main>
      <header className="topbar">
        <div>
          <p className="eyebrow">data-trend</p>
          <h1>数据采集管理台</h1>
        </div>
        <div className="actions">
          <span className="roleTag">{auth.username} / {auth.role}</span>
          <button className="secondary" onClick={logout}>退出</button>
          <button className="iconButton" onClick={() => refresh()} aria-label="刷新">
            <RefreshCcw size={18} />
          </button>
        </div>
      </header>

      {message && <div className="notice">{message}</div>}

      <section className="metrics">
        <Metric icon={<RadioTower />} label="城市/区域" value={overview?.regions ?? 0} />
        <Metric icon={<Database />} label="指标" value={overview?.indicators ?? 0} />
        <Metric icon={<CheckCircle2 />} label="已发布数据" value={overview?.published_values ?? 0} />
        <Metric icon={<ListChecks />} label="质量报告" value={qualityReports.length} />
        <Metric icon={<Play />} label="运行中任务" value={activeJobs} />
      </section>

      <section className="opsStrip">
        <OpsCard
          tone={(opsSummary?.failed_jobs_last_24h ?? 0) > 0 ? "danger" : "normal"}
          label="24h 失败任务"
          value={opsSummary?.failed_jobs_last_24h ?? 0}
          detail={`总任务 ${opsSummary?.jobs_last_24h ?? 0}`}
        />
        <OpsCard
          tone={(opsSummary?.quality_failed_reports ?? 0) > 0 ? "danger" : "normal"}
          label="质量失败"
          value={opsSummary?.quality_failed_reports ?? 0}
          detail="报告累计"
        />
        <OpsCard
          tone={(opsSummary?.review_pending_values ?? 0) > 0 ? "warning" : "normal"}
          label="待审核"
          value={opsSummary?.review_pending_values ?? 0}
          detail="数据积压"
        />
        <OpsCard
          tone={(opsSummary?.pending_jobs ?? 0) + (opsSummary?.running_jobs ?? 0) > 0 ? "warning" : "normal"}
          label="排队/运行"
          value={`${opsSummary?.pending_jobs ?? 0}/${opsSummary?.running_jobs ?? 0}`}
          detail={`下次 ${formatDate(opsSummary?.next_schedule_at ?? null)}`}
        />
        <OpsCard
          tone="normal"
          label="最近成功"
          value={formatDate(opsSummary?.last_success_at ?? null)}
          detail="抓取完成时间"
        />
      </section>

      <section className="grid">
        <article className="panel">
          <h2>数据源</h2>
          <form className="formGrid" onSubmit={createDataSource}>
            <input
              value={sourceForm.name}
              onChange={(event) => setSourceForm({ ...sourceForm, name: event.target.value })}
              placeholder="数据源名称"
            />
            <input
              value={sourceForm.entry_url}
              onChange={(event) => setSourceForm({ ...sourceForm, entry_url: event.target.value })}
              placeholder="入口 URL"
            />
            <div className="inlineFields">
              <input
                value={sourceForm.source}
                onChange={(event) => setSourceForm({ ...sourceForm, source: event.target.value })}
                placeholder="来源"
              />
              <select
                value={sourceForm.type}
                onChange={(event) => setSourceForm({ ...sourceForm, type: event.target.value })}
              >
                {(dataSourceTypes.length ? dataSourceTypes : ["housing_price", "cpi"]).map((type) => (
                  <option key={type} value={type}>
                    {formatSourceType(type)}
                  </option>
                ))}
              </select>
            </div>
            <div className="presetActions">
              <button
                type="button"
                className="secondary"
                onClick={() =>
                  setSourceForm({
                    name: "国家统计局 CPI",
                    entry_url: DEFAULT_CPI_URL,
                    source: "国家统计局",
                    type: "cpi",
                    enabled: true,
                  })
                }
              >
                CPI 模板
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() =>
                  setSourceForm({
                    name: "国家统计局房价指数",
                    entry_url: DEFAULT_URL,
                    source: "国家统计局",
                    type: "housing_price",
                    enabled: true,
                  })
                }
              >
                房价模板
              </button>
            </div>
            <button type="submit" disabled={saving}>
              <Save size={16} />
              {saving ? "保存中" : "保存数据源"}
            </button>
          </form>
          <div className="list">
            {dataSources.map((source) => (
              <div className="listItem" key={source.id}>
                <div>
                  <strong>{source.name}</strong>
                  <span>{formatSourceType(source.type)} / {source.entry_url}</span>
                  <small>
                    {formatHealth(healthBySourceId.get(source.id))}
                  </small>
                </div>
                <div className="actions">
                  <button className="secondary" onClick={() => loadSourceDetail(source.id)}>
                    详情
                  </button>
                  <button className="secondary" onClick={() => toggleDataSource(source)}>
                    {source.enabled ? "停用" : "启用"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <h2>触发采集</h2>
          <div className="formGrid">
            <select value={statDataSourceId} onChange={(event) => setStatDataSourceId(event.target.value)}>
              <option value="">临时 URL</option>
              {dataSources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.name}
                </option>
              ))}
            </select>
            <input value={adHocUrl} onChange={(event) => setAdHocUrl(event.target.value)} disabled={!!selectedSourceId} />
            <button onClick={runImport} disabled={running}>
              <Play size={16} />
              {running ? "提交中" : "提交任务"}
            </button>
          </div>
        </article>
      </section>

      <section className="panel">
        <div className="panelHead">
          <h2>任务调度</h2>
          <button className="secondary" onClick={runDueSchedules}>
            <Play size={16} />
            生成到期任务
          </button>
        </div>
        <form className="formGrid" onSubmit={createSchedule}>
          <input value={scheduleName} onChange={(event) => setScheduleName(event.target.value)} placeholder="调度名称" />
          <input value={scheduleUrl} onChange={(event) => setScheduleUrl(event.target.value)} placeholder="目标 URL" />
          <input
            type="number"
            value={scheduleInterval}
            onChange={(event) => setScheduleInterval(event.target.value)}
            placeholder="间隔分钟"
          />
          <button type="submit">
            <Save size={16} />
            保存调度
          </button>
        </form>
        <DataTable
          headers={["ID", "名称", "状态", "间隔", "上次运行", "下次运行", "操作"]}
          rows={schedules.map((schedule) => [
            schedule.id,
            schedule.name,
            schedule.enabled ? "enabled" : "disabled",
            `${schedule.interval_minutes} 分钟`,
            formatDate(schedule.last_run_at),
            formatDate(schedule.next_run_at),
            <button className="secondary" onClick={() => toggleSchedule(schedule)}>
              {schedule.enabled ? "停用" : "启用"}
            </button>,
          ])}
        />
      </section>

      <section className="panel">
        <div className="panelHead">
          <h2>最近任务</h2>
          <select value={jobStatus} onChange={(event) => setJobStatus(event.target.value)}>
            <option value="">全部状态</option>
            <option value="pending">pending</option>
            <option value="running">running</option>
            <option value="success">success</option>
            <option value="failed">failed</option>
          </select>
        </div>
        <DataTable
          headers={["ID", "状态", "触发", "重试", "目标", "总数", "导入", "开始", "错误", "操作"]}
          rows={jobs.map((job) => [
            job.id,
            job.status,
            job.trigger,
            `${job.retry_count}/${job.max_retries}`,
            truncate(job.target_url ?? "-"),
            job.total_records,
            job.imported_records,
            formatDate(job.started_at),
            job.error_type ? `${job.error_type}: ${job.error_message ?? ""}` : (job.error_message ?? "-"),
            <div className="actions">
              <button className="secondary" onClick={() => loadJobDetail(job.id)}>
                详情
              </button>
              {job.status === "failed" && (
                <button className="secondary" onClick={() => retryJob(job.id)}>
                  重试
                </button>
              )}
              {(job.status === "pending" || job.status === "running") && (
                <button className="secondary" onClick={() => cancelJob(job.id)}>
                  取消
                </button>
              )}
            </div>,
          ])}
        />
      </section>

      <section className="panel">
        <h2>质量报告</h2>
        <DataTable
          headers={["ID", "任务", "周期", "状态", "城市", "数据量", "问题明细", "时间"]}
          rows={qualityReports.map((report) => [
            report.id,
            report.crawl_job_id ?? "-",
            report.period ?? "-",
            report.status,
            `${report.actual_regions}/${report.expected_regions}`,
            report.checked_values,
            formatQualityDetails(report),
            <button className="secondary" onClick={() => loadQualityDetail(report.id)}>
              查看详情
            </button>,
            formatDate(report.created_at),
          ])}
        />
      </section>

      {(sourceDetail || jobDetail || qualityDetail) && (
        <section className="panel detailGrid">
          {sourceDetail && (
            <DetailPanel title={`数据源详情 #${sourceDetail.data_source.id}`} onClose={() => setSourceDetail(null)}>
              <KeyValue label="名称" value={sourceDetail.data_source.name} />
              <KeyValue label="类型" value={formatSourceType(sourceDetail.data_source.type)} />
              <KeyValue label="入口" value={sourceDetail.data_source.entry_url} />
              <KeyValue label="健康" value={formatHealth(sourceDetail.health ?? undefined)} />
              <KeyValue label="可操作" value={sourceDetail.available_actions.join(" / ")} />
              <strong>最近任务</strong>
              <ul className="compactList">
                {sourceDetail.recent_jobs.map((job) => (
                  <li key={job.id}>#{job.id} {job.status} / {formatDate(job.finished_at)}</li>
                ))}
              </ul>
            </DetailPanel>
          )}
          {jobDetail && (
            <DetailPanel title={`任务详情 #${jobDetail.job.id}`} onClose={() => setJobDetail(null)}>
              <KeyValue label="状态" value={jobDetail.job.status} />
              <KeyValue label="数据源" value={jobDetail.data_source?.name ?? "-"} />
              <KeyValue label="耗时" value={jobDetail.duration_seconds === null ? "-" : `${jobDetail.duration_seconds}s`} />
              <KeyValue label="锁" value={jobDetail.job.locked_by ? `${jobDetail.job.locked_by} / ${formatDate(jobDetail.job.locked_at)}` : "-"} />
              <KeyValue label="重试" value={`${jobDetail.job.retry_count}/${jobDetail.job.max_retries}`} />
              <KeyValue label="导入" value={`${jobDetail.job.imported_records}/${jobDetail.job.total_records}`} />
              <KeyValue label="错误" value={jobDetail.job.error_type ? `${jobDetail.job.error_type}: ${jobDetail.job.error_message ?? ""}` : "-"} />
            </DetailPanel>
          )}
          {qualityDetail && (
            <DetailPanel title={`质量报告 #${qualityDetail.id}`} onClose={() => setQualityDetail(null)}>
              <KeyValue label="状态" value={qualityDetail.status} />
              <KeyValue label="建议" value={qualityDetail.suggested_actions.join(" / ")} />
              <strong>Errors</strong>
              <ul className="compactList">
                {qualityDetail.error_details.map((detail, index) => (
                  <li key={index}>{detail.rule} / {detail.indicator ?? "-"} / {detail.region ?? "-"} / {detail.period ?? "-"}</li>
                ))}
              </ul>
              <strong>Warnings</strong>
              <ul className="compactList">
                {qualityDetail.warning_details.map((detail, index) => (
                  <li key={index}>{detail.rule} / {detail.message}</li>
                ))}
              </ul>
            </DetailPanel>
          )}
        </section>
      )}

      <section className="panel">
        <div className="panelHead">
          <h2>采集记录</h2>
          <div className="actions wideActions">
            <input value={recordKeyword} onChange={(event) => setRecordKeyword(event.target.value)} placeholder="标题关键字" />
            <select value={recordStatus} onChange={(event) => setRecordStatus(event.target.value)}>
              <option value="">全部状态</option>
              <option value="parsed">parsed</option>
              <option value="failed">failed</option>
              <option value="skipped">skipped</option>
            </select>
            <input type="date" value={recordFrom} onChange={(event) => setRecordFrom(event.target.value)} />
            <input type="date" value={recordTo} onChange={(event) => setRecordTo(event.target.value)} />
            <button className="secondary" onClick={() => refresh()}>
              <Filter size={16} />
              筛选
            </button>
          </div>
        </div>
        <DataTable
          headers={["ID", "标题", "状态", "发布日期", "解析时间"]}
          rows={records.map((record) => [
            record.id,
            <a href={record.url} target="_blank" rel="noreferrer">
              {record.title}
            </a>,
            record.status,
            formatDate(record.published_at),
            formatDate(record.parsed_at),
          ])}
        />
      </section>

      <section className="panel">
        <div className="panelHead">
          <h2>数据审核</h2>
          <div className="actions wideActions">
            <select value={statStatus} onChange={(event) => setStatStatus(event.target.value)}>
              <option value="draft">待发布</option>
              <option value="ready_for_review">待审核</option>
              <option value="quality_failed">质量失败</option>
              <option value="published">已发布</option>
              <option value="rejected">已拒绝</option>
            </select>
            <select value={statRegionId} onChange={(event) => setStatRegionId(event.target.value)}>
              <option value="">全部城市</option>
              {regions.map((region) => (
                <option key={region.id} value={region.id}>
                  {region.name}
                </option>
              ))}
            </select>
            <select value={statIndicatorCode} onChange={(event) => setStatIndicatorCode(event.target.value)}>
              <option value="">全部指标</option>
              {indicators.map((indicator) => (
                <option key={indicator.code} value={indicator.code}>
                  {indicator.name}
                </option>
              ))}
            </select>
            <select value={selectedSourceId} onChange={(event) => setSelectedSourceId(event.target.value)}>
              <option value="">全部数据源</option>
              {dataSources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.name}
                </option>
              ))}
            </select>
            <input type="date" value={statPeriod} onChange={(event) => setStatPeriod(event.target.value)} />
            <select value={statHouseType} onChange={(event) => setStatHouseType(event.target.value)}>
              <option value="">全部住宅</option>
              <option value="new_house">新建商品住宅</option>
              <option value="second_hand">二手住宅</option>
            </select>
            <select value={statAreaType} onChange={(event) => setStatAreaType(event.target.value)}>
              <option value="">全部面积</option>
              <option value="none">不分面积</option>
              <option value="under_90">90㎡以下</option>
              <option value="between_90_144">90-144㎡</option>
              <option value="over_144">144㎡以上</option>
            </select>
            <button className="secondary" onClick={() => refresh()}>
              <Filter size={16} />
              筛选
            </button>
            <button onClick={publishSelected} disabled={publishing || selectedStatIds.length === 0}>
              <CheckCircle2 size={16} />
              发布选中({selectedStatIds.length})
            </button>
            <input value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} placeholder="驳回原因" />
            <button className="secondary" onClick={rejectSelected} disabled={selectedStatIds.length === 0}>
              驳回选中
            </button>
          </div>
        </div>
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>选择</th>
                <th>城市</th>
                <th>指标</th>
                <th>周期</th>
                <th>数值</th>
                <th>维度</th>
              </tr>
            </thead>
            <tbody>
              {statValues.map((item) => (
                <tr key={item.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedStatIds.includes(item.id)}
                      onChange={() => toggleStatSelection(item.id)}
                    />
                  </td>
                  <td>{item.region}</td>
                  <td>{item.indicator_name}</td>
                  <td>{item.period}</td>
                  <td>
                    <input
                      className="valueInput"
                      type="number"
                      defaultValue={item.value}
                      onBlur={(event) => patchStatValue(item.id, Number(event.target.value))}
                    />
                  </td>
                  <td>{formatDimensions(item.dimensions)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h2>指标展示配置</h2>
        <DataTable
          headers={["指标", "分类", "展示名", "单位", "排序", "小程序", "操作"]}
          rows={indicators.map((indicator) => {
            const draft = indicatorDrafts[indicator.code] || {};
            return [
              indicator.code,
              <input
                value={(draft.category as string | undefined) ?? indicator.category}
                onChange={(event) =>
                  setIndicatorDrafts({
                    ...indicatorDrafts,
                    [indicator.code]: { ...draft, category: event.target.value },
                  })
                }
              />,
              <input
                value={(draft.display_name as string | undefined) ?? indicator.display_name ?? indicator.name}
                onChange={(event) =>
                  setIndicatorDrafts({
                    ...indicatorDrafts,
                    [indicator.code]: { ...draft, display_name: event.target.value },
                  })
                }
              />,
              <input
                value={(draft.unit as string | undefined) ?? indicator.unit ?? ""}
                onChange={(event) =>
                  setIndicatorDrafts({
                    ...indicatorDrafts,
                    [indicator.code]: { ...draft, unit: event.target.value },
                  })
                }
              />,
              <input
                type="number"
                value={(draft.sort_order as number | undefined) ?? indicator.sort_order}
                onChange={(event) =>
                  setIndicatorDrafts({
                    ...indicatorDrafts,
                    [indicator.code]: { ...draft, sort_order: Number(event.target.value) },
                  })
                }
              />,
              <input
                type="checkbox"
                checked={(draft.miniapp_visible as boolean | undefined) ?? indicator.miniapp_visible}
                onChange={(event) =>
                  setIndicatorDrafts({
                    ...indicatorDrafts,
                    [indicator.code]: { ...draft, miniapp_visible: event.target.checked },
                  })
                }
              />,
              <button className="secondary" onClick={() => saveIndicator(indicator)}>
                保存
              </button>,
            ];
          })}
        />
      </section>

      <section className="panel">
        <h2>发布批次</h2>
        <DataTable
          headers={["ID", "动作", "数量", "原因", "时间"]}
          rows={publishBatches.map((batch) => [
            batch.id,
            batch.action,
            batch.item_count,
            batch.reason ?? "-",
            formatDate(batch.created_at),
          ])}
        />
      </section>

      <section className="panel">
        <h2>运营配置</h2>
        <div className="configGrid">
          {configs.map((config) => (
            <article className="configItem" key={config.key}>
              <div className="panelHead">
                <div>
                  <strong>{config.key}</strong>
                  <span>{config.description ?? "配置项"}</span>
                </div>
                <button className="secondary" onClick={() => saveConfig(config)}>
                  保存
                </button>
              </div>
              <textarea
                value={configDrafts[config.key] ?? ""}
                onChange={(event) => setConfigDrafts({ ...configDrafts, [config.key]: event.target.value })}
              />
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <article className="metric">
      <div className="metricIcon">{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function OpsCard({
  tone,
  label,
  value,
  detail,
}: {
  tone: "normal" | "warning" | "danger";
  label: string;
  value: number | string;
  detail: string;
}) {
  return (
    <article className={`opsCard ${tone}`}>
      <div className="opsIcon">
        <AlertTriangle size={18} />
      </div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function DataTable({ headers, rows }: { headers: string[]; rows: React.ReactNode[][] }) {
  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DetailPanel({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <article className="detailPanel">
      <div className="panelHead">
        <h2>{title}</h2>
        <button className="secondary" onClick={onClose}>关闭</button>
      </div>
      <div className="detailBody">{children}</div>
    </article>
  );
}

function KeyValue({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="keyValue">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatDate(value: string | null) {
  return value ? value.slice(0, 19).replace("T", " ") : "-";
}

function formatDimensions(dimensions: Record<string, string>) {
  return Object.entries(dimensions)
    .map(([key, value]) => `${key}:${value}`)
    .join(" / ");
}

function formatSourceType(type: string) {
  const labels: Record<string, string> = {
    housing_price: "房价指数",
    cpi: "居民消费价格 CPI",
  };
  return labels[type] ?? type;
}

function formatHealth(health: DataSourceHealth | undefined) {
  if (!health) return "暂无任务";
  const status = health.latest_job_status ?? "暂无任务";
  const successRate = `${Math.round(health.success_rate * 100)}%`;
  const error = health.latest_error_type ? ` / ${health.latest_error_type}` : "";
  return `最近 ${status} / 成功率 ${successRate}${error}`;
}

function formatQualityDetails(report: QualityReport) {
  if (report.details.length) {
    return report.details
      .slice(0, 3)
      .map((detail) => {
        const scope = [
          detail.indicator,
          detail.region,
          detail.period,
          detail.dimensions ? JSON.stringify(detail.dimensions) : "",
        ]
          .filter(Boolean)
          .join(" / ");
        return `${detail.severity}:${detail.rule} ${scope || detail.message}`;
      })
      .join("；");
  }
  return [...report.errors, ...report.warnings].join("；") || "-";
}

function buildQuery(params: Record<string, string>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) query.set(key, value);
  });
  const value = query.toString();
  return value ? `?${value}` : "";
}

function truncate(value: string) {
  return value.length > 58 ? `${value.slice(0, 58)}...` : value;
}

createRoot(document.getElementById("root")!).render(<App />);
