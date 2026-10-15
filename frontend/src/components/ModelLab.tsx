import { useEffect, useState } from "react";
import { ArrowRight, BrainCircuit, ChartNoAxesColumn, CircleAlert, FlaskConical, Gauge, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { fetchMLDataset, fetchMLEvaluation, fetchMLFeatures, fetchMLModel, fetchScenarioPredictions, type MLDatasetInfo, type MLEvaluationReport, type MLFeatureInfo, type MLModelInfo, type ScenarioPredictionSet, type ScenarioState } from "../api/client";
import { Badge, Panel } from "./ui";

export default function ModelLab({ scenario }: { scenario: ScenarioState | null }) {
  const [dataset, setDataset] = useState<MLDatasetInfo | null>(null);
  const [model, setModel] = useState<MLModelInfo | null>(null);
  const [evaluation, setEvaluation] = useState<MLEvaluationReport | null>(null);
  const [features, setFeatures] = useState<MLFeatureInfo[]>([]);
  const [predictions, setPredictions] = useState<ScenarioPredictionSet | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    const c = new AbortController();
    fetchMLModel(c.signal).then(setModel).catch((reason: unknown) => { if (!c.signal.aborted) setError(reason instanceof Error ? reason.message : "Local model status unavailable."); });
    Promise.all([fetchMLDataset(c.signal), fetchMLEvaluation(c.signal), fetchMLFeatures(c.signal)]).then(([d, e, f]) => { setDataset(d); setEvaluation(e); setFeatures(f); }).catch((reason: unknown) => { if (!c.signal.aborted) setError(reason instanceof Error ? reason.message : "Local ML service unavailable."); });
    return () => c.abort();
  }, []);
  useEffect(() => {
    setPredictions(null);
    if (!scenario) return;
    const c = new AbortController();
    fetchScenarioPredictions(scenario, undefined, c.signal).then((p) => { if (p.scenario_id === scenario.id && p.scenario_state_version === scenario.state_version && p.scenario_tick === scenario.tick) { setPredictions(p); setSelectedId((old) => p.predictions.some((x) => x.building_id === old) ? old : p.predictions[0]?.building_id ?? ""); } }).catch((reason: unknown) => { if (!c.signal.aborted) setError(reason instanceof Error ? reason.message : "Predictions unavailable."); });
    return () => c.abort();
  }, [scenario, scenario?.id, scenario?.state_version, scenario?.tick]);
  const selected = predictions?.predictions.find((p) => p.building_id === selectedId);
  const metrics = (evaluation?.test_metrics ?? {}) as Record<string, unknown>;
  const baselines = (evaluation?.test_baselines ?? {}) as Record<string, unknown>;
  const candidates = (evaluation?.validation_candidates ?? {}) as Record<string, unknown>;
  const confusion = (metrics.confusion_matrix ?? {}) as Record<string, number>;
  return <main className="model-lab">
    <div className="page-heading"><div><div className="breadcrumb">INTELLIGENCE <ArrowRight size={12}/> MODEL EVIDENCE</div><h1>Model Intelligence Lab<span className="heading-dot"/></h1><p>A locally trained flood exposure model, evaluated on unseen simulated scenarios.</p></div><Badge tone={error ? "amber" : "green"}>{error ? "Data unavailable" : "Synthetic evaluation"}</Badge></div>
    {error && <div className="connection-banner" role="alert"><CircleAlert size={17}/><span>{error}</span></div>}
    <section className="ml-hero"><div className="ml-hero-icon"><BrainCircuit size={27}/></div><div><span className="eyebrow">LOCAL MODEL · {model?.model_version ?? dataset?.dataset_version ?? "LOADING"}</span><h2>{model?.model_name ?? "Flood exposure classifier"}</h2><p>{model?.algorithm?.replaceAll("_", " ") ?? evaluation?.selected_model.replaceAll("_", " ") ?? "Local model"} · predicts whether a building crosses the simulated 0.05 m flood exposure threshold six five-minute ticks ahead.</p><p>{model?.training_scenarios ?? dataset?.scenario_count ?? "—"} training scenarios · {model?.observation_count?.toLocaleString() ?? dataset?.observation_count.toLocaleString() ?? "—"} observations · trained {model?.trained_at_utc ? new Date(model.trained_at_utc).toLocaleDateString() : "date not recorded"}</p></div><div className="ml-status"><Badge tone={model?.status === "ready" ? "green" : "amber"}>{model?.status === "ready" ? "Artifact ready" : model?.unavailable_reason ?? "Checking artifact"}</Badge><small>Inference stays on this machine</small></div></section>
    <div className="ml-stats">
      <Metric label="Scenario groups" value={dataset?.scenario_count} note="Independent generated runs" icon={<FlaskConical/>}/><Metric label="Observations" value={dataset?.observation_count?.toLocaleString()} note="Building and time samples" icon={<ChartNoAxesColumn/>}/><Metric label="Held-out F1" value={number(metrics.f1)} note={`${evaluation?.test_scenario_count ?? "—"} unseen test scenarios`} icon={<Gauge/>}/><Metric label="Inference latency" value={evaluation ? `${evaluation.inference_latency_ms_per_observation.toFixed(3)} ms` : "—"} note="Measured on saved evaluation batch" icon={<ShieldCheck/>}/>
    </div>
    <div className="ml-columns">
      <Panel title="Held-out evaluation" eyebrow={evaluation?.test_set_label ?? "TEST SET"} action={<Badge>Scenario grouped</Badge>}>
        <div className="ml-metric-grid">{[["Precision", metrics.precision],["Recall", metrics.recall],["Balanced accuracy", metrics.balanced_accuracy],["ROC-AUC", metrics.roc_auc],["PR-AUC", metrics.pr_auc_average_precision],["F1 score", metrics.f1]].map(([name, value]) => <div key={String(name)}><small>{String(name)}</small><strong>{number(value)}</strong></div>)}</div>
        <h3>Confusion matrix · actual × predicted</h3><div className="confusion"><span/><span>Not exposed</span><span>Exposed</span><b>Not exposed</b><strong>{confusion.true_negative ?? "—"}</strong><strong>{confusion.false_positive ?? "—"}</strong><b>Exposed</b><strong>{confusion.false_negative ?? "—"}</strong><strong>{confusion.true_positive ?? "—"}</strong></div>
        <p className="activity-note">Test class support: {evaluation?.test_negative_count.toLocaleString() ?? "—"} not exposed · {evaluation?.test_positive_count.toLocaleString() ?? "—"} exposed.</p>
        <h3>Baseline comparison · held-out F1</h3>{Object.entries(baselines).map(([name, result]) => { const row = result as Record<string, unknown>; return <div className="baseline-row" key={name}><span>{name.replaceAll("_", " ")}</span><div><i style={{ width: `${Math.max(2, metricNumber(row.f1) * 100)}%` }}/></div><strong>{number(row.f1)}</strong></div>; })}
        <h3>Candidate model selection · validation F1</h3>{Object.entries(candidates).map(([name, result]) => { const row = result as Record<string, unknown>; return <div className="baseline-row" key={name}><span>{name.replaceAll("_", " ")}</span><div><i style={{ width: `${Math.max(2, metricNumber(row.f1) * 100)}%` }}/></div><strong>{number(row.f1)}</strong></div>; })}
      </Panel>
      <Panel title="Prediction inspector" eyebrow="LIVE DIGITAL TWIN STATE" action={<Badge tone={predictions ? "green" : "amber"}>{predictions ? `v${predictions.scenario_state_version} · tick ${predictions.scenario_tick}` : "Updating"}</Badge>}>
        {predictions?.predictions.length ? <><label className="ml-select-label">Building<select aria-label="Choose a building" value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>{predictions.predictions.map((p) => <option key={p.building_id} value={p.building_id}>{p.building_id}</option>)}</select></label>{selected && <div className="inspector-result"><div className="inspector-compare"><div><small>Current simulated exposure</small><strong>{selected.current_exposed ? selected.current_exposure_category : "Not exposed"}</strong><span>{selected.current_max_depth_m.toFixed(2)} m depth</span></div><ArrowRight/><div><small>Predicted in {predictions.horizon_minutes} minutes</small><strong className={selected.predicted_future_exposed ? "future-high" : ""}>{selected.predicted_future_exposed ? "Exposed" : "Not exposed"}</strong><span>Threshold ≥ 0.05 m</span></div></div><p>Uncalibrated model score <b>{selected.uncalibrated_model_score.toFixed(3)}</b> · not a probability</p><h3>Feature values with global importance</h3>{selected.influential_features.map((f) => <div className="feature-value" key={f.name}><span>{f.name.replaceAll("_", " ")}</span><b>{f.value.toFixed(2)}</b><small>importance {f.global_permutation_importance.toFixed(3)}</small></div>)}</div>}</> : <p className="muted">Waiting for predictions for the current scenario state.</p>}
        <p className="activity-note">Current exposure is calculated by the flood engine. The classifier estimates a separate future label and never changes water simulation.</p>
      </Panel>
    </div>
    <div className="ml-columns">
      <Panel title="Feature intelligence" eyebrow="GLOBAL PERMUTATION IMPORTANCE" action={<Badge>Held-out test set</Badge>}>
        {(evaluation?.permutation_importance ?? []).slice(0, 8).map((item) => { const row = item as Record<string, unknown>; const top = metricNumber(evaluation?.permutation_importance?.[0]?.importance_mean) || 1; const amount = metricNumber(row.importance_mean); return <div className="importance-row" key={String(row.feature)}><span>{String(row.feature).replaceAll("_", " ")}</span><div><i style={{ width: `${Math.max(1, amount / Math.max(0.001, top) * 100)}%` }}/></div><b>{amount.toFixed(3)}</b></div>; })}
        <div className="feature-definitions">{features.slice(0, 8).map((f) => <div key={f.name}><b>{f.name.replaceAll("_", " ")}</b><span>{f.description} · {f.units}</span></div>)}</div><p className="activity-note">Permutation importance describes global test-set dependence; it does not establish causation or explain one building by itself.</p>
      </Panel>
      <Panel title="Training evidence & limits" eyebrow="REPRODUCIBLE · OFFLINE">
        <div className="evidence-list"><div><b>Dataset provenance</b><span>{dataset?.provenance ?? "Generated from the deterministic local flood engine."}</span></div><div><b>Training workflow</b><span>Group split by scenario ID; final test groups excluded from fitting and selection.</span></div><div><b>Target</b><span>{dataset?.label_definition ?? "Future building exposure from the simulated flood engine."}</span></div><div><b>Reproduce</b><code>python -m app.ml.generate_dataset<br/>python -m app.ml.train</code></div><div><b>Data boundary</b><span>Synthetic simulation only. Not trained or validated on observed disaster outcomes.</span></div></div>
      </Panel>
    </div>
    <div className="ml-footer-link"><span>Inspect the current city and scenario state.</span><Link to="/">Command Center <ArrowRight size={15}/></Link></div>
  </main>;
}
function Metric({ label, value, note, icon }: { label: string; value?: string | number; note: string; icon: React.ReactNode }) { return <div className="ml-stat"><span>{icon}</span><small>{label}</small><strong>{value ?? "—"}</strong><p>{note}</p></div>; }
function metricNumber(value: unknown) { return typeof value === "number" ? value : 0; }
function number(value: unknown) { return typeof value === "number" ? value.toFixed(3) : "—"; }
