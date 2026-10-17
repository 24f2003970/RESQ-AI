import { useEffect, useState } from "react";
import { ArrowRight, BrainCircuit, ChartNoAxesColumn, CircleAlert, FlaskConical, Gauge, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { fetchMLDataset, fetchMLEvaluation, fetchMLFeatures, fetchMLModel, fetchMLReliability, fetchMLSensitivity, fetchScenarioPredictions, type MLDatasetInfo, type MLEvaluationReport, type MLFeatureInfo, type MLModelInfo, type ReliabilityEvidence, type ScenarioPredictionSet, type ScenarioState, type SensitivityEvidence } from "../api/client";
import { Badge, Panel } from "./ui";

export default function ModelLab({ scenario }: { scenario: ScenarioState | null }) {
  const [dataset, setDataset] = useState<MLDatasetInfo | null>(null);
  const [model, setModel] = useState<MLModelInfo | null>(null);
  const [evaluation, setEvaluation] = useState<MLEvaluationReport | null>(null);
  const [features, setFeatures] = useState<MLFeatureInfo[]>([]);
  const [predictions, setPredictions] = useState<ScenarioPredictionSet | null>(null);
  const [reliability, setReliability] = useState<ReliabilityEvidence | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityEvidence | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [failureKey, setFailureKey] = useState("");
  const [sensitivityIndex, setSensitivityIndex] = useState(0);
  const [error, setError] = useState("");
  useEffect(() => {
    const c = new AbortController();
    fetchMLModel(c.signal).then(setModel).catch((reason: unknown) => { if (!c.signal.aborted) setError(reason instanceof Error ? reason.message : "Local model status unavailable."); });
    Promise.all([fetchMLDataset(c.signal), fetchMLEvaluation(c.signal), fetchMLFeatures(c.signal), fetchMLReliability(c.signal), fetchMLSensitivity(c.signal)]).then(([d, e, f, r, s]) => { setDataset(d); setEvaluation(e); setFeatures(f); setReliability(r); setSensitivity(s); }).catch((reason: unknown) => { if (!c.signal.aborted) setError(reason instanceof Error ? reason.message : "Local ML service unavailable."); });
    return () => c.abort();
  }, []);
  useEffect(() => {
    setPredictions(null);
    if (!scenario) return;
    const c = new AbortController();
    fetchScenarioPredictions(scenario, undefined, c.signal).then((p) => { if (p.scenario_id === scenario.id && p.scenario_epoch === scenario.epoch && p.scenario_state_version === scenario.state_version && p.scenario_tick === scenario.tick && (!model?.model_version || p.model_version === model.model_version)) { setPredictions(p); setSelectedId((old) => p.predictions.some((x) => x.building_id === old) ? old : p.predictions[0]?.building_id ?? ""); } }).catch((reason: unknown) => { if (!c.signal.aborted) setError(reason instanceof Error ? reason.message : "Predictions unavailable."); });
    return () => c.abort();
  }, [scenario, scenario?.id, scenario?.epoch, scenario?.state_version, scenario?.tick, model?.model_version]);
  const currentPredictions = scenario && predictions?.scenario_id === scenario.id && predictions.scenario_epoch === scenario.epoch && predictions.scenario_state_version === scenario.state_version && predictions.scenario_tick === scenario.tick && predictions.model_version === model?.model_version ? predictions : null;
  const selected = currentPredictions?.predictions.find((p) => p.building_id === selectedId);
  const metrics = (evaluation?.test_metrics ?? {}) as Record<string, unknown>;
  const baselines = (evaluation?.test_baselines ?? {}) as Record<string, unknown>;
  const candidates = (evaluation?.validation_candidates ?? {}) as Record<string, unknown>;
  const confusion = (metrics.confusion_matrix ?? {}) as Record<string, number>;
  const reliabilityReport = asRecord(reliability?.report);
  const calibration = asRecord(reliabilityReport.calibration);
  const rawCalibration = asRecord(calibration.final_held_out_raw);
  const plattCalibration = asRecord(calibration.final_held_out_platt);
  const failures = asRecord(reliabilityReport.held_out_failure_analysis);
  const falsePositives = asRecords(failures.false_positives);
  const falseNegatives = asRecords(failures.false_negatives);
  const failureOptions = [...falseNegatives.map((item, index) => ({ key: `false_negatives:${index}`, label: `Missed emerging exposure · ${item.scenario_id} · ${item.building_id}`, item })), ...falsePositives.map((item, index) => ({ key: `false_positives:${index}`, label: `False alarm · ${item.scenario_id} · ${item.building_id}`, item }))];
  const chosenFailure = failureOptions.find((item) => item.key === failureKey) ?? failureOptions[0];
  const subgroupMetrics = asRecord(failures.subgroups);
  const subgroups = Object.entries(subgroupMetrics);
  const sensitivityReport = asRecord(sensitivity?.report);
  const sensitivityRows = asRecords(sensitivityReport.comparisons).filter((item) => item.variant !== "baseline");
  const selectedSensitivity = sensitivityRows[sensitivityIndex] ?? sensitivityRows[0];
  const sensitivityBaseline = selectedSensitivity && asRecords(sensitivityReport.comparisons).find((item) => item.variant === "baseline" && item.scenario_id === selectedSensitivity.scenario_id && item.tick === selectedSensitivity.tick);
  const supportCounts = asRecord(asRecord(reliabilityReport.distribution_support).test_support_counts);
  return <main className="model-lab">
    <div className="page-heading"><div><div className="breadcrumb">INTELLIGENCE <ArrowRight size={12}/> MODEL EVIDENCE</div><h1>Model Intelligence Lab<span className="heading-dot"/></h1><p>A locally trained flood exposure model, evaluated on unseen simulated scenarios.</p></div><Badge tone={error ? "amber" : "green"}>{error ? "Data unavailable" : "Synthetic evaluation"}</Badge></div>
    {error && <div className="connection-banner" role="alert"><CircleAlert size={17}/><span>{error}</span></div>}
    <section className="ml-hero"><div className="ml-hero-icon"><BrainCircuit size={27}/></div><div><span className="eyebrow">LOCAL MODEL · {model?.model_version ?? dataset?.dataset_version ?? "LOADING"}</span><h2>{model?.model_name ?? "Flood exposure classifier"}</h2><p>{model?.algorithm?.replaceAll("_", " ") ?? evaluation?.selected_model.replaceAll("_", " ") ?? "Local model"} · predicts whether a building crosses the simulated 0.05 m flood exposure threshold six five-minute ticks ahead.</p><p>{model?.training_scenarios ?? dataset?.scenario_count ?? "—"} training scenarios · {model?.observation_count?.toLocaleString() ?? dataset?.observation_count.toLocaleString() ?? "—"} observations · trained {model?.trained_at_utc ? new Date(model.trained_at_utc).toLocaleDateString() : "date not recorded"}</p><small>Reliability evidence: {model?.reliability_status ?? "checking"} · calibration: {model?.calibration_status ?? "checking"} · artifact SHA-256 {model?.artifact_sha256?.slice(0, 12) ?? "unavailable"}</small></div><div className="ml-status"><Badge tone={model?.status === "ready" ? "green" : "amber"}>{model?.status === "ready" ? "Artifact ready" : model?.unavailable_reason ?? "Checking artifact"}</Badge><small>Inference stays on this machine</small></div></section>
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
      <Panel title="Prediction reliability inspector" eyebrow="LIVE DIGITAL TWIN STATE" action={<Badge tone={currentPredictions ? "green" : "amber"}>{currentPredictions ? `epoch ${currentPredictions.scenario_epoch} · v${currentPredictions.scenario_state_version} · tick ${currentPredictions.scenario_tick}` : "Current prediction unavailable"}</Badge>}>
        {currentPredictions?.predictions.length ? <><label className="ml-select-label">Building<select aria-label="Choose a building" value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>{currentPredictions.predictions.map((p) => <option key={p.building_id} value={p.building_id}>{p.building_id}</option>)}</select></label>{selected && <div className="inspector-result"><div className="inspector-compare"><div><small>Current simulated exposure</small><strong>{selected.current_exposed ? selected.current_exposure_category : "Not exposed"}</strong><span>{selected.current_max_depth_m.toFixed(2)} m depth</span></div><ArrowRight/><div><small>Predicted in {currentPredictions.horizon_minutes} minutes</small><strong className={selected.predicted_future_exposed ? "future-high" : ""}>{selected.predicted_future_exposed ? "Exposed" : "Not exposed"}</strong><span>Threshold ≥ 0.05 m</span></div></div><div className="reliability-status-row"><Badge tone={selected.distribution_support_status === "within_observed_support" ? "green" : "amber"}>{selected.distribution_support_status.replaceAll("_", " ")}</Badge><small>Training support is not an accuracy guarantee.</small></div><p>{selected.calibrated_synthetic_probability !== null && selected.calibrated_synthetic_probability !== undefined ? <>Calibrated against held-out synthetic scenarios: <b>{selected.calibrated_synthetic_probability.toFixed(3)}</b></> : <>Raw classifier score <b>{selected.uncalibrated_model_score.toFixed(3)}</b> · not a probability</>}</p>{selected.reliability_warnings.map((warning) => <p className="reliability-warning" key={warning}>{warning}</p>)}<h3>Relevant input features</h3>{selected.influential_features.map((f) => <div className="feature-value" key={f.name}><span>{f.name.replaceAll("_", " ")}</span><b>{f.value.toFixed(2)}</b><small>global held-out importance {f.global_permutation_importance.toFixed(3)}</small></div>)}</div>}</> : <p className="muted">{scenario ? "Waiting for a prediction for this exact scenario epoch and state version." : "Create or select a scenario to inspect local inference."}</p>}
        <p className="activity-note">Current exposure is calculated by the flood engine. The classifier estimates a separate future label and never changes water simulation.</p>
      </Panel>
    </div>
    <section className="reliability-section" aria-labelledby="reliability-heading">
      <div className="reliability-section-heading"><div><span className="eyebrow">SAVED, GROUPED EVIDENCE · SYNTHETIC LABELS</span><h2 id="reliability-heading">Reliability &amp; Uncertainty</h2><p>Evidence describes the local flood simulator only. It is not a real-world forecast guarantee.</p></div><Badge tone={reliability?.status === "available" ? "green" : "amber"}>{reliability?.status ?? "Loading evidence"}</Badge></div>
      {reliability?.warnings.map((warning) => <div className="connection-banner" role="status" key={warning}><CircleAlert size={16}/><span>{warning}</span></div>)}
      <div className="ml-columns reliability-columns">
        <Panel title="Calibration analysis" eyebrow={String(calibration.method ?? "CALIBRATION EVIDENCE") } action={<Badge>{String(calibration.status ?? "unavailable").replaceAll("_", " ")}</Badge>}>
          <p className="activity-note">Platt sigmoid fit from five-fold group-held-out development scores. Entire scenario groups are held out; the final test groups were not used to fit or select the calibrator. Adoption required a ≥0.001 nested development Brier improvement and log loss no more than 0.01 worse.</p>
          <CalibrationPlot raw={asRecords(rawCalibration.reliability_diagram)} calibrated={asRecords(plattCalibration.reliability_diagram)}/>
          <div className="ml-metric-grid reliability-metrics"><div><small>Test Brier · raw score</small><strong>{number(rawCalibration.brier_score)}</strong></div><div><small>Test Brier · Platt</small><strong>{number(plattCalibration.brier_score)}</strong></div><div><small>Test log loss · raw</small><strong>{number(rawCalibration.log_loss)}</strong></div><div><small>Test log loss · Platt</small><strong>{number(plattCalibration.log_loss)}</strong></div><div><small>10-bin ECE · raw</small><strong>{number(rawCalibration.expected_calibration_error)}</strong></div><div><small>10-bin ECE · Platt</small><strong>{number(plattCalibration.expected_calibration_error)}</strong></div></div>
          <p className="activity-note">Held-out F1 at 0.5: raw {number(asRecord(asRecord(calibration.held_out_classification_at_threshold_0_5).uncalibrated).f1)} · Platt {number(asRecord(asRecord(calibration.held_out_classification_at_threshold_0_5).platt_calibrated).f1)}. A monotonic sigmoid preserves the score ranking; calibration estimates the synthetic target frequency only.</p>
        </Panel>
        <Panel title="Distribution support" eyebrow="MARGINAL TRAINING SUPPORT">
          <p>Current building inputs are checked against per-feature training min/max and 0.5th–99.5th percentile tails. This is an interpretable support flag, not a detector for every unsafe or novel condition.</p>
          <div className="support-counts">{Object.entries(supportCounts).map(([name, count]) => <div key={name}><span>{name.replaceAll("_", " ")}</span><strong>{String(count)}</strong><small>held-out building-tick rows</small></div>)}</div>
          <p className="activity-note">A prediction inside observed support can still be wrong. Marginal checks do not detect all feature interactions or correlated shifts.</p>
          {selected && <div className="reliability-status-row"><Badge tone={selected.distribution_support_status === "within_observed_support" ? "green" : "amber"}>{selected.distribution_support_status.replaceAll("_", " ")}</Badge><span>Selected building: {selected.building_id}</span></div>}
        </Panel>
      </div>
      <div className="ml-columns reliability-columns">
        <Panel title="Failure inspector" eyebrow="UNSEEN SCENARIO EXAMPLES">
          {failureOptions.length ? <><label className="ml-select-label">Held-out case<select aria-label="Choose a failure example" value={chosenFailure?.key ?? ""} onChange={(event) => setFailureKey(event.target.value)}>{failureOptions.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>{chosenFailure && <FailureDetails item={chosenFailure.item}/>}</> : <p className="muted">Saved held-out error examples are unavailable.</p>}
          <p className="activity-note">Rows are correlated within scenarios and across ticks. These are concrete simulator examples, not estimates of real incident failure rates.</p>
        </Panel>
        <Panel title="Subgroup performance" eyebrow="HELD-OUT SYNTHETIC CONDITIONS">
          <div className="subgroup-table-wrap"><table className="subgroup-table"><thead><tr><th>Condition</th><th>Scenarios</th><th>Rows</th><th>F1</th><th>Recall</th><th>Status</th></tr></thead><tbody>{subgroups.map(([name, value]) => { const row = asRecord(value); return <tr key={name}><th>{name.replaceAll("_", " ")}</th><td>{String(row.scenario_count ?? "—")}</td><td>{String(row.observation_count ?? "—")}</td><td>{number(row.f1)}</td><td>{number(row.recall)}</td><td>{String(row.status ?? "—")}</td></tr>; })}</tbody></table></div>
          <p className="activity-note">Metrics are shown only for slices spanning at least three test scenarios and both classes. Smaller slices retain counts and an insufficient-support status in the saved JSON.</p>
        </Panel>
      </div>
      <Panel title="Sensitivity explorer" eyebrow="AUTHORITATIVE SIMULATOR VARIANTS" action={<Badge>{String(sensitivity?.status ?? "Loading")}</Badge>}>
        {selectedSensitivity ? <><label className="ml-select-label">Reproducible intervention<select aria-label="Choose sensitivity intervention" value={String(sensitivityIndex)} onChange={(event) => setSensitivityIndex(Number(event.target.value))}>{sensitivityRows.map((row, index) => <option key={`${row.scenario_id}:${row.tick}:${row.variant}`} value={index}>{String(row.scenario_id)} · tick {String(row.tick)} · {String(row.variant).replaceAll("_", " ")}</option>)}</select></label><div className="sensitivity-compare"><div><small>Baseline predicted exposed</small><strong>{String(sensitivityBaseline?.predicted_positive_count ?? "—")}</strong><small>Variant predicted exposed</small><strong>{String(selectedSensitivity.predicted_positive_count ?? "—")}</strong></div><div><small>Prediction flips</small><strong>{number(selectedSensitivity.prediction_flip_fraction_vs_baseline)}</strong><small>Change in predicted count</small><strong>{signedNumber(selectedSensitivity.delta_predicted_positive_count)}</strong></div><div><small>Rank correlation</small><strong>{number(selectedSensitivity.rank_spearman_vs_baseline)}</strong><small>Variant F1 on its rerun simulator label</small><strong>{number(selectedSensitivity.f1)}</strong></div></div><p className="activity-note">{String(asRecord(sensitivityReport).intervention_method ?? "Interventions rerun the authoritative simulator from initial state.")} Sensitivity measures response to a controlled change; it does not prove accuracy. Some rank correlations are undefined when all scores are tied.</p></> : <p className="muted">{sensitivity?.reason ?? "Reproducible sensitivity results are unavailable."}</p>}
      </Panel>
    </section>
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
function number(value: unknown) { return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "—"; }
function signedNumber(value: unknown) { return typeof value === "number" ? `${value > 0 ? "+" : ""}${value}` : "—"; }
function asRecord(value: unknown): Record<string, unknown> { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}; }
function asRecords(value: unknown): Record<string, unknown>[] { return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item)) : []; }

function CalibrationPlot({ raw, calibrated }: { raw: Record<string, unknown>[]; calibrated: Record<string, unknown>[] }) {
  const points = (rows: Record<string, unknown>[], color: string, prefix: string) => rows.filter((row) => metricNumber(row.count) > 0).map((row) => {
    const x = metricNumber(row.mean_score); const y = metricNumber(row.observed_frequency);
    return <circle key={`${prefix}-${String(row.bin)}`} cx={50 + x * 400} cy={210 - y * 180} r="4" fill={color}><title>{prefix} bin {String(row.bin)}: score {x.toFixed(3)}, observed {y.toFixed(3)}, n={String(row.count)}</title></circle>;
  });
  return <figure className="calibration-figure"><svg viewBox="0 0 500 250" role="img" aria-label="Held-out calibration reliability diagram, raw score and Platt calibrated synthetic probability">
    <line x1="50" y1="210" x2="450" y2="30" stroke="#657777" strokeDasharray="5 5"/><line x1="50" y1="210" x2="450" y2="210" stroke="#657777"/><line x1="50" y1="210" x2="50" y2="30" stroke="#657777"/>
    {[0, 0.5, 1].map((value) => <g key={value}><text x={45 + value * 400} y="230" textAnchor="middle">{value.toFixed(1)}</text><text x="36" y={214 - value * 180} textAnchor="end">{value.toFixed(1)}</text></g>)}
    {points(raw, "#f3ad66", "Raw score")}{points(calibrated, "#83d7b1", "Platt")}
    <text x="250" y="247" textAnchor="middle">Mean predicted score</text><text transform="translate(12 120) rotate(-90)" textAnchor="middle">Observed synthetic frequency</text>
  </svg><figcaption><span><i className="raw-dot"/> Raw RF score</span><span><i className="calibrated-dot"/> Platt synthetic probability</span><span>Dashed line: ideal agreement. Points use held-out test bins.</span></figcaption></figure>;
}

function FailureDetails({ item }: { item: Record<string, unknown> }) {
  const features = asRecord(item.relevant_features);
  return <div className="failure-details"><div><b>{String(item.scenario_id)} · seed {String(item.scenario_seed)} · tick {String(item.tick)}</b><span>{String(item.building_id)} · actual {item.actual === 1 ? "exposed" : "not exposed"} · predicted {item.predicted === 1 ? "exposed" : "not exposed"}</span><small>Raw score {number(item.raw_score_uncalibrated)} · calibrated synthetic estimate {number(item.calibrated_synthetic_probability)}</small></div><dl>{Object.entries(features).map(([name, value]) => <div key={name}><dt>{name.replaceAll("_", " ")}</dt><dd>{typeof value === "number" ? value.toFixed(3) : String(value)}</dd></div>)}</dl></div>;
}
