import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

const steps = [
  { path: "/scenarios", title: "Set the flood", text: "Choose rainfall, then advance the simulation." },
  { path: "/response", title: "Review a rescue plan", text: "Check routes and resources. Approve when ready." },
  { path: "/response?view=missions", title: "Track missions", text: "Dispatch approved units and follow their progress." },
];

export default function WorkflowGuide({ current = 0 }: { current?: number }) {
  return <section className="workflow-guide" aria-label="Rescue workflow">
    <div className="workflow-intro"><span className="eyebrow">YOUR WORKFLOW</span><h2>From flood to response</h2><p>New here? <Link to="/demo">Try the guided demo <ArrowRight size={12}/></Link></p></div>
    <ol>{steps.map((step, index) => <li key={step.title}><Link to={step.path} aria-current={current === index + 1 ? "step" : undefined}><span className="workflow-number">{index + 1}</span><div><strong>{step.title}</strong><p>{step.text}</p></div><ArrowRight size={16}/></Link></li>)}</ol>
  </section>;
}
