import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  CheckCircle2,
  Database,
  FileText,
  Filter,
  Play,
  RadioTower,
  RefreshCcw,
  Save,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const DEFAULT_URL = "https://www.stats.gov.cn/sj/zxfb/202604/t20260416_1963320.html";

type Overview = {
  regions: number;
  indicators: number;
  published_values: number;
  latest_period: string | null;
};

type DataSource = {
  id: number;
  name: string;
  entry_url: string;
  source: string;
  type: string;
  enabled: boolean;
};

type Region = {
  id: number;
  name: string;
};

type Indicator = {
  id: number;
  code: string;
  name: string;
};

type CrawlJob = {
  id: number;
  data_source_id: number | null;
  target_url: string | null;
  status: string;
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

type DataSourceForm = {
  name: string;
  entry_url: string;
  source: string;
  type: string;
  enabled: boolean;
};

function App() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [regions, setRegions] = useState<Region[]>([]);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [jobs, setJobs] = useState<CrawlJob[]>([]);
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
  const [statStatus, setStatStatus] = useState("draft");
  const [jobStatus, setJobStatus] = useState("");
  const [recordKeyword, setRecordKeyword] = useState("");
  const [recordStatus, setRecordStatus] = useState("");
  const [recordFrom, setRecordFrom] = useState("");
  const [recordTo, setRecordTo] = useState("");
  const [statRegionId, setStatRegionId] = useState("");
  const [statIndicatorCode, setStatIndicatorCode] = useState("");
  const [statPeriod, setStatPeriod] = useState("");
  const [selectedStatIds, setSelectedStatIds] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [message, setMessage] = useState("");

  async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
      ...options,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || response.statusText);
    }
    return response.json();
  }

  async function refresh() {
    const [overviewRes, sourcesRes, regionsRes, indicatorsRes, jobsRes, recordsRes, statValuesRes] = await Promise.all([
      request<Overview>("/mini/dashboard/overview"),
      request<DataSource[]>("/admin/data-sources"),
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
        })}`,
      ),
    ]);
    setOverview(overviewRes);
    setDataSources(sourcesRes);
    setRegions(regionsRes);
    setIndicators(indicatorsRes);
    setJobs(jobsRes);
    setRecords(recordsRes);
    setStatValues(statValuesRes);
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
    await request<DataSource>(`/admin/data-sources/${source.id}`, {
      method: "PATCH",
      body: JSON.stringify({ enabled: !source.enabled }),
    });
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
      await request<{ published: number }>("/admin/stat-values/publish", {
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

  function toggleStatSelection(id: number) {
    setSelectedStatIds((ids) => (ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id]));
  }

  const activeJobs = useMemo(
    () => jobs.filter((job) => job.status === "pending" || job.status === "running").length,
    [jobs],
  );

  useEffect(() => {
    refresh().catch((error) => setMessage(error.message));
  }, [jobStatus, statStatus]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (activeJobs > 0) {
        refresh().catch((error) => setMessage(error.message));
      }
    }, 5000);
    return () => window.clearInterval(timer);
  }, [activeJobs, jobStatus, recordKeyword, recordStatus, recordFrom, recordTo, statStatus, statRegionId, statIndicatorCode, statPeriod]);

  return (
    <main>
      <header className="topbar">
        <div>
          <p className="eyebrow">data-trend</p>
          <h1>数据采集管理台</h1>
        </div>
        <button className="iconButton" onClick={() => refresh()} aria-label="刷新">
          <RefreshCcw size={18} />
        </button>
      </header>

      {message && <div className="notice">{message}</div>}

      <section className="metrics">
        <Metric icon={<RadioTower />} label="城市/区域" value={overview?.regions ?? 0} />
        <Metric icon={<Database />} label="指标" value={overview?.indicators ?? 0} />
        <Metric icon={<CheckCircle2 />} label="已发布数据" value={overview?.published_values ?? 0} />
        <Metric icon={<Play />} label="运行中任务" value={activeJobs} />
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
              <input
                value={sourceForm.type}
                onChange={(event) => setSourceForm({ ...sourceForm, type: event.target.value })}
                placeholder="类型"
              />
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
                  <span>{source.entry_url}</span>
                </div>
                <button className="secondary" onClick={() => toggleDataSource(source)}>
                  {source.enabled ? "启用" : "停用"}
                </button>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <h2>触发采集</h2>
          <div className="formGrid">
            <select value={selectedSourceId} onChange={(event) => setSelectedSourceId(event.target.value)}>
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
          headers={["ID", "状态", "目标", "总数", "导入", "跳过", "开始", "错误"]}
          rows={jobs.map((job) => [
            job.id,
            job.status,
            truncate(job.target_url ?? "-"),
            job.total_records,
            job.imported_records,
            job.skipped_records,
            formatDate(job.started_at),
            job.error_type ? `${job.error_type}: ${job.error_message ?? ""}` : (job.error_message ?? "-"),
          ])}
        />
      </section>

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
            <input type="date" value={statPeriod} onChange={(event) => setStatPeriod(event.target.value)} />
            <button className="secondary" onClick={() => refresh()}>
              <Filter size={16} />
              筛选
            </button>
            <button onClick={publishSelected} disabled={publishing || selectedStatIds.length === 0}>
              <CheckCircle2 size={16} />
              发布选中({selectedStatIds.length})
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

function formatDate(value: string | null) {
  return value ? value.slice(0, 19).replace("T", " ") : "-";
}

function formatDimensions(dimensions: Record<string, string>) {
  return Object.entries(dimensions)
    .map(([key, value]) => `${key}:${value}`)
    .join(" / ");
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
