import {
  ArrowRight,
  Blocks,
  BrainCircuit,
  Cpu,
  Radar,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Orbitron, Space_Grotesk } from "next/font/google";
import Link from "next/link";

import styles from "./page-home.module.css";

const orbitron = Orbitron({
  subsets: ["latin"],
  variable: "--font-orbitron",
  weight: ["600", "700", "800"],
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
  weight: ["400", "500", "600", "700"],
});

type OrbitSlot = "nodeA" | "nodeB" | "nodeC" | "nodeD" | "nodeE";
type SceneSkin = "sceneOne" | "sceneTwo" | "sceneThree";

type OrbitNode = {
  label: string;
  role: string;
  slot: OrbitSlot;
  Icon: LucideIcon;
};

type SceneCard = {
  title: string;
  metric: string;
  skin: SceneSkin;
  Icon: LucideIcon;
  bars: number[];
};

const badges = [
  "Deep Search",
  "Code Ops",
  "Doc Audit",
  "Tool Mesh",
  "Memory Loop",
  "Subagents",
  "Sandbox",
  "Autofix",
];

const orbitNodes: OrbitNode[] = [
  { label: "Scout", role: "Search", slot: "nodeA", Icon: Radar },
  { label: "Builder", role: "Code", slot: "nodeB", Icon: Blocks },
  { label: "Reviewer", role: "QA", slot: "nodeC", Icon: ShieldCheck },
  { label: "Planner", role: "Plan", slot: "nodeD", Icon: BrainCircuit },
  { label: "Router", role: "Route", slot: "nodeE", Icon: Workflow },
];

const sceneCards: SceneCard[] = [
  {
    title: "Research Mesh",
    metric: "4.2M signals/day",
    skin: "sceneOne",
    Icon: Radar,
    bars: [26, 64, 40, 78, 56],
  },
  {
    title: "Build Pipeline",
    metric: "29 active workflows",
    skin: "sceneTwo",
    Icon: Blocks,
    bars: [34, 52, 70, 66, 88],
  },
  {
    title: "Quality Shield",
    metric: "96% review coverage",
    skin: "sceneThree",
    Icon: ShieldCheck,
    bars: [24, 42, 58, 74, 92],
  },
];

const telemetry = [
  { label: "Task Completion", value: 97 },
  { label: "Tool Success", value: 94 },
  { label: "Memory Hit", value: 89 },
  { label: "Latency Budget", value: 91 },
];

const sparkline = [
  14, 28, 22, 36, 30, 44, 24, 33, 26, 48, 32, 56, 38, 50, 34, 61, 40, 58,
  37, 54, 41, 63, 47, 69,
];

const flow = ["Observe", "Compose", "Execute", "Validate", "Deliver"];

export default function LandingPage() {
  return (
    <div className={`${styles.page} ${orbitron.variable} ${spaceGrotesk.variable}`}>
      <div className={styles.auroraOne} />
      <div className={styles.auroraTwo} />
      <div className={styles.gridMask} />

      <div className={styles.shell}>
        <header className={styles.nav}>
          <div className={styles.brand}>
            <span className={styles.brandDot} />
            <span className={styles.brandText}>AGENTFLOW</span>
            <span className={styles.brandTag}>Visual Command Surface</span>
          </div>
          <div className={styles.navAction}>
            <a href="#flow-map" className={styles.ghostButton}>
              Flow Map
            </a>
            <Link href="/workspace" className={styles.primaryButton}>
              进入工作台
              <ArrowRight className={styles.btnIcon} />
            </Link>
          </div>
        </header>

        <main className={styles.main}>
          <section className={styles.hero}>
            <div className={`${styles.heroCopy} ${styles.reveal}`}>
              <p className={styles.kicker}>AGENT ERA INTERFACE</p>
              <h1 className={styles.title}>少解释，多执行</h1>
              <p className={styles.subtitle}>一个页面，看见任务如何被智能体网络接力完成。</p>

              <div className={styles.heroActions}>
                <Link href="/workspace" className={styles.primaryButton}>
                  Start Mission
                  <ArrowRight className={styles.btnIcon} />
                </Link>
                <a href="#visual-scenes" className={styles.secondaryButton}>
                  View Scenes
                </a>
              </div>

              <div className={styles.badgeRail}>
                <div className={styles.badgeTrack}>
                  {badges.concat(badges).map((item, index) => (
                    <span key={`${item}-${index}`} className={styles.badgeItem}>
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <aside className={`${styles.visualStage} ${styles.reveal} ${styles.delay1}`}>
              <div className={styles.stageGlow} />
              <div className={`${styles.ring} ${styles.ringOne}`} />
              <div className={`${styles.ring} ${styles.ringTwo}`} />
              <div className={`${styles.ring} ${styles.ringThree}`} />
              <div className={`${styles.vector} ${styles.vectorOne}`} />
              <div className={`${styles.vector} ${styles.vectorTwo}`} />
              <div className={`${styles.vector} ${styles.vectorThree}`} />

              <div className={styles.stageCore}>
                <Cpu className={styles.coreIcon} />
                <span>Agent Core</span>
              </div>

              {orbitNodes.map((node) => {
                const Icon = node.Icon;
                return (
                  <article
                    key={node.label}
                    className={`${styles.agentNode} ${styles[node.slot]}`}
                  >
                    <Icon className={styles.agentIcon} />
                    <div>
                      <strong>{node.label}</strong>
                      <span>{node.role}</span>
                    </div>
                  </article>
                );
              })}
            </aside>
          </section>

          <section id="visual-scenes" className={styles.visualSection}>
            <div className={`${styles.sceneGrid} ${styles.reveal} ${styles.delay1}`}>
              {sceneCards.map((card) => {
                const Icon = card.Icon;
                return (
                  <article
                    key={card.title}
                    className={`${styles.sceneCard} ${styles[card.skin]}`}
                  >
                    <div className={styles.sceneHead}>
                      <div className={styles.sceneIconWrap}>
                        <Icon className={styles.sceneIcon} />
                      </div>
                      <div>
                        <h3>{card.title}</h3>
                        <p>{card.metric}</p>
                      </div>
                    </div>
                    <div className={styles.sceneVisual}>
                      {card.bars.map((bar, index) => (
                        <span
                          key={`${card.title}-${bar}-${index}`}
                          style={{
                            height: `${bar}%`,
                            animationDelay: `${index * 80}ms`,
                          }}
                        />
                      ))}
                    </div>
                  </article>
                );
              })}
            </div>

            <aside className={`${styles.cockpit} ${styles.reveal} ${styles.delay2}`}>
              <div className={styles.cockpitHead}>
                <span className={styles.livePill}>Live Telemetry</span>
                <span className={styles.liveStatus}>ONLINE</span>
              </div>

              <div className={styles.telemetryList}>
                {telemetry.map((item) => (
                  <div key={item.label} className={styles.telemetryRow}>
                    <div className={styles.telemetryTitle}>
                      <span>{item.label}</span>
                      <strong>{item.value}%</strong>
                    </div>
                    <div className={styles.telemetryBar}>
                      <span style={{ width: `${item.value}%` }} />
                    </div>
                  </div>
                ))}
              </div>

              <div className={styles.sparkline}>
                {sparkline.map((value, index) => (
                  <span
                    key={`${value}-${index}`}
                    style={{
                      height: `${value}px`,
                      animationDelay: `${index * 50}ms`,
                    }}
                  />
                ))}
              </div>

              <div className={styles.cockpitFooter}>
                <Sparkles className={styles.sparkIcon} />
                <span>Adaptive orchestration in progress</span>
              </div>
            </aside>
          </section>

          <section
            id="flow-map"
            className={`${styles.flowSection} ${styles.reveal} ${styles.delay3}`}
          >
            <p className={styles.flowTag}>FLOW MAP</p>
            <div className={styles.flowTrack}>
              {flow.map((step, index) => (
                <div key={step} className={styles.flowItem}>
                  <span className={styles.flowDot}>{index + 1}</span>
                  <span className={styles.flowText}>{step}</span>
                </div>
              ))}
            </div>
          </section>
        </main>

        <footer className={`${styles.footer} ${styles.reveal} ${styles.delay3}`}>
          <p>Agent-native interface for execution-first teams.</p>
          <Link href="/workspace" className={styles.primaryButton}>
            Launch AgentFlow
            <ArrowRight className={styles.btnIcon} />
          </Link>
        </footer>
      </div>
    </div>
  );
}
