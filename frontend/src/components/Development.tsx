import { Link } from "react-router-dom";
import { ArrowRight, Bot, FlaskConical, SlidersHorizontal } from "lucide-react";
import { Badge } from "./ui";

export default function Development({
  kind,
}: {
  kind: "scenarios" | "decisions" | "model";
}) {
  const content = {
    scenarios: {
      title: "Every response starts with a scenario.",
      name: "Scenario Lab",
      part: "Proposed Part 3",
      icon: SlidersHorizontal,
      description:
        "Set rainfall, river stage and infrastructure conditions, then explore how the city changes.",
      features: [
        "Rainfall & river controls",
        "Scenario presets",
        "Deterministic flood steps",
      ],
    },
    decisions: {
      title: "Understand the reasoning behind every move.",
      name: "AI Decision Explorer",
      part: "Proposed Parts 5–7",
      icon: Bot,
      description:
        "Follow agent triggers, compare route choices and review proposed rescue plans before approving actions.",
      features: [
        "Agent activity timeline",
        "Decision explanations",
        "Human approval workflow",
      ],
    },
    model: {
      title: "Evidence before intelligence.",
      name: "Model Intelligence Lab",
      part: "Proposed Part 4",
      icon: FlaskConical,
      description:
        "Inspect the local training pipeline, grouped evaluation and model limitations. No model has been trained yet.",
      features: [
        "Dataset provenance",
        "Baseline comparison",
        "Held-out evaluation",
      ],
    },
  }[kind];
  return (
    <main className="development-page">
      <div className="development-grid" />
      <div className="development-content">
        <span className="development-icon">
          <content.icon size={34} />
        </span>
        <Badge tone="amber">Under development · {content.part}</Badge>
        <h1>{content.title}</h1>
        <p>{content.description}</p>
        <div className="future-features">
          {content.features.map((f, i) => (
            <div key={f}>
              <span>0{i + 1}</span>
              {f}
            </div>
          ))}
        </div>
        <p className="muted">
          Part 2 establishes the city and local data connection. Future part
          numbers are provisional until their scope is approved.
        </p>
        <Link className="primary-button" to="/">
          Back to Command Center <ArrowRight size={16} />
        </Link>
      </div>
    </main>
  );
}
