import { useState, useEffect } from "react";

// Bloomberg Terminal Color System
const B = {
  bg:       "#000000",
  panel:    "#070707",
  border:   "#444444",
  border2:  "#2a2a2a",
  orange:   "#FF6600",  // Bloomberg signature orange
  yellow:   "#FFFF00",  // Field labels
  green:    "#00CC44",  // Positive / completed
  red:      "#FF3333",  // Negative / failed
  cyan:     "#00CCFF",  // Highlights
  white:    "#FFFFFF",  // Primary data values
  gray:     "#888888",  // Secondary text
  dgray:    "#555555",  // Muted
  magenta:  "#FF66FF",  // Alerts
  mono:     "'Courier New', 'Lucida Console', monospace",
};

const stages = [
  { n:0,  label:"BOOTSTRAP",           status:"completed", dur:"0.3s",  agent:"orchestrator" },
  { n:1,  label:"UNIVERSE VALIDATION", status:"completed", dur:"1.2s",  agent:"validator" },
  { n:2,  label:"DATA INGESTION",      status:"completed", dur:"4.1s",  agent:"ingestion" },
  { n:3,  label:"RECONCILIATION",      status:"completed", dur:"2.3s",  agent:"reconcile" },
  { n:4,  label:"DATA QA",             status:"completed", dur:"1.8s",  agent:"qa-agent" },
  { n:5,  label:"EVIDENCE LIBRARY",    status:"completed", dur:"6.4s",  agent:"evidence-lib" },
  { n:6,  label:"SECTOR ANALYSIS",     status:"completed", dur:"11.2s", agent:"sector-compute" },
  { n:7,  label:"VALUATION",           status:"running",   dur:null,    agent:"valuation-analyst" },
  { n:8,  label:"MACRO & GEOPOLIT.",   status:"pending",   dur:null,    agent:"macro-strategist" },
  { n:9,  label:"RISK ASSESSMENT",     status:"pending",   dur:null,    agent:"risk-agent" },
  { n:10, label:"RED TEAM",            status:"pending",   dur:null,    agent:"red-team" },
  { n:11, label:"ASSOCIATE REVIEW",    status:"pending",   dur:null,    agent:"associate-rev" },
  { n:12, label:"PORTFOLIO CONST.",    status:"pending",   dur:null,    agent:"portfolio-mgr" },
  { n:13, label:"REPORT ASSEMBLY",     status:"pending",   dur:null,    agent:"synthesiser" },
  { n:14, label:"MONITORING",          status:"pending",   dur:null,    agent:"monitor" },
];

const positions = [
  { ticker:"NVDA", name:"NVIDIA CORP",       wt:22, px:892.40, chg:+2.4,  var95:-4.2, conv:88 },
  { ticker:"TSM",  name:"TAIWAN SEMI ADR",   wt:18, px:164.20, chg:+0.8,  var95:-3.8, conv:82 },
  { ticker:"MSFT", name:"MICROSOFT CORP",    wt:21, px:418.30, chg:+1.1,  var95:-2.1, conv:79 },
  { ticker:"AMZN", name:"AMAZON.COM INC",    wt:20, px:182.50, chg:-0.3,  var95:-2.9, conv:75 },
  { ticker:"GOOGL",name:"ALPHABET INC-A",    wt:19, px:168.90, chg:+0.6,  var95:-2.4, conv:71 },
];

const events = [
  { t:"14:22:41", type:"CMPLT", col:"#00CC44", msg:"S06 SECTOR ANALYSIS COMPLETE               11.2s" },
  { t:"14:22:41", type:"ARTIF", col:"#00CCFF", msg:"ARTIFACT WRITTEN: sector_analysis_output.json" },
  { t:"14:22:42", type:"START", col:"#FF6600", msg:"S07 VALUATION STARTED  [valuation-analyst]" },
  { t:"14:22:42", type:"LLM  ", col:"#FFFF00", msg:"LLM CALL: claude-sonnet-4-6  tokens=4200" },
  { t:"14:22:43", type:"WAIT ", col:"#888888", msg:"AWAITING LLM RESPONSE..." },
];

const mktData = [
  { sym:"SPX",   val:"5421.8", chg:"+12.4",  pct:"+0.23%" },
  { sym:"NDX",   val:"19284",  chg:"+89.2",  pct:"+0.47%" },
  { sym:"ASX200",val:"7892.1", chg:"-18.3",  pct:"-0.23%" },
  { sym:"NVDA",  val:"892.4",  chg:"+21.0",  pct:"+2.41%" },
  { sym:"TSM",   val:"164.2",  chg:"+1.3",   pct:"+0.80%" },
  { sym:"VIX",   val:"18.42",  chg:"+0.84",  pct:"+4.78%" },
  { sym:"AUD/USD",val:"0.6412",chg:"-0.0021",pct:"-0.33%" },
  { sym:"10Y",   val:"4.342",  chg:"+0.021", pct:"+0.49%" },
];

const fkeys = [
  "F1 HELP","F2 NEWS","F3 SETTINGS","F4 HISTORY","F5 REPORT","F6 AUDIT","F7 QUANT","F8 STAGES","F9 NEW RUN","F10 SAVE","F11 EXPORT","F12 QUIT"
];

const screens = ["MONITOR","PORTFOLIO","REPORT","AUDIT","QUANT","STAGES","NEW RUN","SAVED"];

export default function Bloomberg() {
  const [screen, setScreen]   = useState("MONITOR");
  const [pulse, setPulse]     = useState(true);
  const [time, setTime]       = useState("");
  const [cmd, setCmd]         = useState("");
  const [mktIdx, setMktIdx]   = useState(0);
  const [activeTab, setTab]   = useState("PIPELINE");
  const [tickers, setTickers] = useState(["NVDA","TSM","MSFT","AMZN","GOOGL"]);
  const [tkInput, setTkInput] = useState("");

  useEffect(() => {
    const tick = setInterval(() => {
      setPulse(p => !p);
      setTime(new Date().toLocaleTimeString("en-AU", { hour12: false, hour:"2-digit", minute:"2-digit", second:"2-digit" }));
      setMktIdx(i => (i + 1) % mktData.length);
    }, 900);
    setTime(new Date().toLocaleTimeString("en-AU", { hour12: false, hour:"2-digit", minute:"2-digit", second:"2-digit" }));
    return () => clearInterval(tick);
  }, []);

  const handleCmd = e => {
    if (e.key === "Enter" && cmd.trim()) {
      const up = cmd.trim().toUpperCase();
      if (screens.includes(up)) setScreen(up);
      setCmd("");
    }
  };

  const S = (p) => ({ fontFamily: B.mono, ...p });

  const TH = ({ children, w, color }) => (
    <td style={S({ color: color || B.yellow, fontSize: 10, padding: "1px 8px", width: w, whiteSpace:"nowrap", letterSpacing:"0.05em" })}>{children}</td>
  );
  const TD = ({ children, color, align }) => (
    <td style={S({ color: color || B.white, fontSize: 11, padding: "2px 8px", textAlign: align || "left", whiteSpace:"nowrap" })}>{children}</td>
  );

  const Panel = ({ title, children, style = {}, titleRight }) => (
    <div style={{ border:`1px solid ${B.border}`, display:"flex", flexDirection:"column", ...style }}>
      <div style={{ background:"#111", borderBottom:`1px solid ${B.border}`, padding:"3px 8px", display:"flex", justifyContent:"space-between", alignItems:"center", flexShrink:0 }}>
        <span style={S({ color: B.orange, fontSize: 11, letterSpacing:"0.1em" })}>{title}</span>
        {titleRight && <span style={S({ color: B.gray, fontSize: 10 })}>{titleRight}</span>}
      </div>
      <div style={{ flex:1, overflow:"auto" }}>{children}</div>
    </div>
  );

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100vh", background: B.bg, color: B.white, fontFamily: B.mono, fontSize:12, overflow:"hidden", userSelect:"none" }}>

      {/* ── TOP STATUS BAR ── */}
      <div style={{ background:"#111", borderBottom:`1px solid ${B.border}`, padding:"3px 10px", display:"flex", alignItems:"center", gap:0, flexShrink:0 }}>
        {/* Brand */}
        <span style={S({ color: B.orange, fontSize:13, letterSpacing:"0.15em", marginRight:16, fontWeight:"bold" })}>MERIDIAN</span>
        <span style={S({ color: B.yellow, fontSize:10, marginRight:16, letterSpacing:"0.08em" })}>RESEARCH TERMINAL</span>
        <span style={S({ color: B.border, marginRight:16 })}>|</span>

        {/* Screen tabs */}
        {screens.map(s => (
          <button key={s} onClick={() => setScreen(s)}
            style={S({ fontSize:10, padding:"1px 10px", marginRight:1, border:"none", cursor:"pointer", letterSpacing:"0.06em",
              background: screen === s ? B.orange : "transparent",
              color: screen === s ? B.bg : B.gray })}>
            {s}
          </button>
        ))}

        <div style={{ flex:1 }} />

        {/* Market ticker */}
        <span style={S({ color: B.gray, fontSize:10, marginRight:8 })}>
          {mktData[mktIdx].sym}
          <span style={{ color: B.cyan, marginLeft:6 }}>{mktData[mktIdx].val}</span>
          <span style={{ color: mktData[mktIdx].chg.startsWith("+") ? B.green : B.red, marginLeft:4 }}>
            {mktData[mktIdx].chg} ({mktData[mktIdx].pct})
          </span>
        </span>
        <span style={S({ color: B.border, marginRight:8 })}>|</span>
        <span style={S({ color: B.green, fontSize:10 })}>{time} AEST</span>
      </div>

      {/* ── COMMAND LINE ── */}
      <div style={{ background:"#0a0a0a", borderBottom:`2px solid ${B.orange}`, padding:"4px 10px", display:"flex", alignItems:"center", gap:8, flexShrink:0 }}>
        <span style={S({ color: B.orange, fontSize:12 })}>{">"}</span>
        <input value={cmd} onChange={e => setCmd(e.target.value.toUpperCase())} onKeyDown={handleCmd}
          placeholder="TYPE SCREEN NAME + ENTER  (e.g. MONITOR  PORTFOLIO  REPORT  AUDIT  QUANT  STAGES)"
          style={S({ flex:1, background:"transparent", border:"none", outline:"none", color: B.yellow, fontSize:11, letterSpacing:"0.05em" })} />
        <span style={S({ color: B.gray, fontSize:10 })}>
          RUN: <span style={{ color: B.orange }}>20260406_142241</span>
        </span>
        <span style={S({ color: B.border })}>|</span>
        <span style={S({ color: B.green, fontSize:10, display:"flex", alignItems:"center", gap:4 })}>
          <span style={{ color: pulse ? B.green : B.dgray, transition:"color 0.2s" }}>●</span> RUNNING S07/15
        </span>
      </div>

      {/* ── MAIN CONTENT ── */}
      <div style={{ flex:1, overflow:"hidden", display:"flex", flexDirection:"column" }}>

        {/* MONITOR SCREEN */}
        {screen === "MONITOR" && (
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gridTemplateRows:"1fr 1fr", gap:1, flex:1, padding:1, background: B.border2 }}>

            {/* Top-left: Pipeline tracker */}
            <Panel title="PIPELINE STATUS — RUN 20260406_142241" titleRight="7/15 COMPLETE">
              <div style={{ padding:"4px 0" }}>
                <div style={{ display:"grid", gridTemplateColumns:"28px 1fr 100px 80px 80px", padding:"3px 8px", borderBottom:`1px solid ${B.border2}` }}>
                  {["S#","STAGE NAME","AGENT","STATUS","DURATION"].map(h => (
                    <span key={h} style={S({ color: B.yellow, fontSize:9, letterSpacing:"0.08em" })}>{h}</span>
                  ))}
                </div>
                {stages.map(s => (
                  <div key={s.n} style={{ display:"grid", gridTemplateColumns:"28px 1fr 100px 80px 80px", padding:"2px 8px",
                    background: s.status === "running" ? "#1a0d00" : "transparent",
                    borderBottom:`1px solid ${B.border2}` }}>
                    <span style={S({ color: B.gray, fontSize:10 })}>S{String(s.n).padStart(2,"0")}</span>
                    <span style={S({ color: s.status==="running" ? B.orange : s.status==="completed" ? B.white : B.dgray, fontSize:11,
                      fontWeight: s.status==="running" ? "bold" : "normal" })}>
                      {s.status === "running" && <span style={{ color: pulse ? B.orange : B.dgray, marginRight:4 }}>►</span>}
                      {s.label}
                    </span>
                    <span style={S({ color: B.gray, fontSize:9, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" })}>{s.agent}</span>
                    <span style={S({ color: s.status==="completed" ? B.green : s.status==="running" ? B.orange : B.dgray, fontSize:10, letterSpacing:"0.06em" })}>
                      {s.status==="completed" ? "COMPLETE" : s.status==="running" ? "RUNNING" : "PENDING"}
                    </span>
                    <span style={S({ color: B.cyan, fontSize:10 })}>{s.dur || (s.status==="running" ? "..." : "")}</span>
                  </div>
                ))}
              </div>
            </Panel>

            {/* Top-right: Live event feed */}
            <Panel title="LIVE EVENT FEED" titleRight="REAL-TIME SSE STREAM">
              <div style={{ padding:"6px 0" }}>
                {/* Market data strip */}
                <div style={{ display:"flex", gap:0, borderBottom:`1px solid ${B.border}`, padding:"4px 8px", overflowX:"hidden", flexWrap:"wrap" }}>
                  {mktData.map(m => (
                    <span key={m.sym} style={S({ fontSize:10, marginRight:16 })}>
                      <span style={{ color: B.cyan }}>{m.sym}</span>
                      <span style={{ color: B.white, marginLeft:4 }}>{m.val}</span>
                      <span style={{ color: m.chg.startsWith("+") ? B.green : B.red, marginLeft:4 }}>{m.pct}</span>
                    </span>
                  ))}
                </div>
                {events.map((e, i) => (
                  <div key={i} style={{ display:"flex", gap:8, padding:"3px 8px", borderBottom:`1px solid ${B.border2}`,
                    background: i === events.length-1 ? "#0a0500" : "transparent" }}>
                    <span style={S({ color: B.gray, fontSize:10, flexShrink:0 })}>{e.t}</span>
                    <span style={S({ color: e.col, fontSize:10, width:40, flexShrink:0, letterSpacing:"0.06em" })}>[{e.type}]</span>
                    <span style={S({ color: e.col, fontSize:11 })}>{e.msg}</span>
                  </div>
                ))}
                <div style={{ padding:"6px 8px", borderTop:`1px solid ${B.border}`, marginTop:8 }}>
                  <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:8 }}>
                    {[["TOTAL EVENTS","24"],["LLM CALLS","7"],["ARTIFACTS","5"]].map(([l,v]) => (
                      <div key={l}>
                        <div style={S({ color: B.yellow, fontSize:9, letterSpacing:"0.08em" })}>{l}</div>
                        <div style={S({ color: B.white, fontSize:16 })}>{v}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </Panel>

            {/* Bottom-left: Positions */}
            <Panel title="PORTFOLIO POSITIONS — UNIVERSE" titleRight="5 SECURITIES">
              <table style={{ width:"100%", borderCollapse:"collapse" }}>
                <thead>
                  <tr style={{ borderBottom:`1px solid ${B.border}` }}>
                    {["TICKER","NAME","WT%","PX LAST","CHG%","VaR95","CONV"].map(h => <TH key={h}>{h}</TH>)}
                  </tr>
                </thead>
                <tbody>
                  {positions.map((p, i) => (
                    <tr key={p.ticker} style={{ borderBottom:`1px solid ${B.border2}`, background: i%2===0 ? "#050505" : "transparent" }}>
                      <TD color={B.orange}>{p.ticker}</TD>
                      <TD color={B.gray}>{p.name}</TD>
                      <TD color={B.white}>{p.wt}%</TD>
                      <TD color={B.white}>{p.px.toFixed(2)}</TD>
                      <TD color={p.chg >= 0 ? B.green : B.red}>{p.chg >= 0 ? "+" : ""}{p.chg.toFixed(1)}%</TD>
                      <TD color={B.red}>{p.var95.toFixed(1)}%</TD>
                      <td style={S({ padding:"2px 8px" })}>
                        <div style={{ width:50, height:6, background:"#1a1a1a", display:"inline-block", verticalAlign:"middle" }}>
                          <div style={{ height:"100%", width:`${p.conv}%`, background: p.conv>80?B.green:p.conv>60?B.orange:B.red }} />
                        </div>
                        <span style={S({ color: B.gray, fontSize:9, marginLeft:4 })}>{p.conv}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr style={{ borderTop:`1px solid ${B.border}` }}>
                    <td colSpan={2} style={S({ color: B.yellow, fontSize:10, padding:"3px 8px", letterSpacing:"0.08em" })}>PORTFOLIO TOTAL</td>
                    <TD color={B.orange}>100%</TD>
                    <TD color={B.gray}>—</TD>
                    <TD color={B.green}>+1.32%</TD>
                    <TD color={B.red}>-3.2%</TD>
                    <TD color={B.gray}>—</TD>
                  </tr>
                </tfoot>
              </table>
            </Panel>

            {/* Bottom-right: Risk metrics */}
            <Panel title="RISK &amp; QUALITY METRICS" titleRight="STAGE 9 + AUDIT">
              <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:0 }}>
                {/* Left: risk */}
                <div style={{ borderRight:`1px solid ${B.border}`, padding:"8px" }}>
                  <div style={S({ color: B.yellow, fontSize:9, letterSpacing:"0.08em", marginBottom:6 })}>MARKET RISK</div>
                  {[["PORTFOLIO VaR 95%","-3.2%",B.red],["MAX DRAWDOWN","-18.4%",B.red],["VOLATILITY ANN.","22.1%",B.orange],["SHARPE RATIO","1.34",B.green],["BETA (ASX200)","1.18",B.cyan],["TRACKING ERROR","8.4%",B.orange]].map(([l,v,c]) => (
                    <div key={l} style={{ display:"flex", justifyContent:"space-between", padding:"2px 0", borderBottom:`1px solid ${B.border2}` }}>
                      <span style={S({ color: B.gray, fontSize:10 })}>{l}</span>
                      <span style={S({ color: c, fontSize:11 })}>{v}</span>
                    </div>
                  ))}
                </div>
                {/* Right: audit */}
                <div style={{ padding:"8px" }}>
                  <div style={S({ color: B.yellow, fontSize:9, letterSpacing:"0.08em", marginBottom:6 })}>QUALITY AUDIT</div>
                  {[["QUALITY SCORE","8.4/10",B.green],["GATES PASSED","12/15",B.orange],["TOTAL CLAIMS","284",B.white],["TIER 1 VERIFIED","112",B.green],["IC APPROVED","YES",B.green],["MANDATE COMPLY","YES",B.green]].map(([l,v,c]) => (
                    <div key={l} style={{ display:"flex", justifyContent:"space-between", padding:"2px 0", borderBottom:`1px solid ${B.border2}` }}>
                      <span style={S({ color: B.gray, fontSize:10 })}>{l}</span>
                      <span style={S({ color: c, fontSize:11 })}>{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </Panel>
          </div>
        )}

        {/* PORTFOLIO SCREEN */}
        {screen === "PORTFOLIO" && (
          <div style={{ padding:8, flex:1, overflow:"auto" }}>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 280px", gap:8 }}>
              <Panel title="POSITION DETAIL — FULL ANALYSIS" titleRight="5 SECURITIES · EQUAL-WEIGHT BASE">
                <table style={{ width:"100%", borderCollapse:"collapse" }}>
                  <thead>
                    <tr style={{ borderBottom:`1px solid ${B.orange}` }}>
                      {["TICKER","SECURITY NAME","WEIGHT","LAST PX","1D CHG","1D CHG%","VaR 95%","MAX DD","SHARPE","CONVICTION","ESG","SECTOR"].map(h => <TH key={h}>{h}</TH>)}
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((p, i) => (
                      <tr key={p.ticker} style={{ borderBottom:`1px solid ${B.border2}`, background: i%2===0 ? "#050505" : "transparent" }}>
                        <TD color={B.orange}>{p.ticker}</TD>
                        <TD color={B.white}>{p.name}</TD>
                        <TD color={B.yellow}>{p.wt}%</TD>
                        <TD color={B.white}>{p.px.toFixed(2)}</TD>
                        <TD color={p.chg>=0?B.green:B.red}>{p.chg>=0?"+":""}{(p.chg*p.px/100).toFixed(2)}</TD>
                        <TD color={p.chg>=0?B.green:B.red}>{p.chg>=0?"+":""}{p.chg.toFixed(2)}%</TD>
                        <TD color={B.red}>{p.var95.toFixed(1)}%</TD>
                        <TD color={B.red}>{(p.var95*4.2).toFixed(1)}%</TD>
                        <TD color={B.green}>{(1.1+i*0.06).toFixed(2)}</TD>
                        <TD color={p.conv>80?B.green:p.conv>65?B.orange:B.red}>{p.conv}/100</TD>
                        <TD color={B.cyan}>{[72,68,81,75,79][i]}</TD>
                        <TD color={B.gray}>{["COMPUTE","COMPUTE","INFRAST","INFRAST","COMPUTE"][i]}</TD>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
              <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
                <Panel title="FACTOR EXPOSURE">
                  {[["MOMENTUM",0.72],["QUALITY",0.58],["GROWTH",0.81],["VALUE",-0.12],["SIZE",-0.34],["VOLATILITY",-0.21]].map(([f,v]) => (
                    <div key={f} style={{ display:"flex", alignItems:"center", gap:6, padding:"3px 8px", borderBottom:`1px solid ${B.border2}` }}>
                      <span style={S({ color: B.yellow, fontSize:10, width:80 })}>{f}</span>
                      <div style={{ flex:1, height:8, background:"#1a1a1a", position:"relative" }}>
                        <div style={{ position:"absolute", left:"50%", top:0, height:"100%", width:`${Math.abs(v)*45}%`, background: v>0?B.green:B.red, transform: v>0?"none":"translateX(-100%)" }} />
                        <div style={{ position:"absolute", left:"50%", top:-1, width:1, height:10, background: B.border }} />
                      </div>
                      <span style={S({ color: v>0?B.green:B.red, fontSize:10, width:36, textAlign:"right" })}>{v>0?"+":""}{v.toFixed(2)}</span>
                    </div>
                  ))}
                </Panel>
                <Panel title="ALLOCATION">
                  {positions.map(p => (
                    <div key={p.ticker} style={{ display:"flex", alignItems:"center", gap:6, padding:"3px 8px", borderBottom:`1px solid ${B.border2}` }}>
                      <span style={S({ color: B.orange, fontSize:11, width:44 })}>{p.ticker}</span>
                      <div style={{ flex:1, height:10, background:"#1a1a1a" }}>
                        <div style={{ height:"100%", width:`${p.wt*4}%`, background: B.orange, opacity:0.7 }} />
                      </div>
                      <span style={S({ color: B.white, fontSize:11, width:28, textAlign:"right" })}>{p.wt}%</span>
                    </div>
                  ))}
                </Panel>
              </div>
            </div>
          </div>
        )}

        {/* REPORT SCREEN */}
        {screen === "REPORT" && (
          <div style={{ padding:8, flex:1, overflow:"auto" }}>
            <Panel title="AI RESEARCH REPORT — 20260406_142241" titleRight="14,200 WORDS · 8.4/10 QUALITY · IC APPROVED">
              <div style={{ padding:"12px 20px", maxWidth:900 }}>
                <div style={S({ color: B.orange, fontSize:10, letterSpacing:"0.12em", marginBottom:4 })}>
                  AI INFRASTRUCTURE — INVESTMENT RESEARCH REPORT — JPAM MERIDIAN PLATFORM
                </div>
                <div style={S({ color: B.yellow, fontSize:18, marginBottom:4, lineHeight:1.3 })}>
                  AI Infrastructure: 15-Stock Portfolio Analysis for the Australian Market
                </div>
                <div style={S({ color: B.gray, fontSize:10, marginBottom:16, borderBottom:`1px solid ${B.border}`, paddingBottom:10 })}>
                  GENERATED: 06 APR 2026 14:22 AEST &nbsp;|&nbsp; MODEL: CLAUDE-SONNET-4-6 &nbsp;|&nbsp; QUALITY: 8.4/10 &nbsp;|&nbsp; IC: APPROVED &nbsp;|&nbsp; MANDATE: COMPLIANT
                </div>
                {[
                  { h:"1. EXECUTIVE SUMMARY", body:"The AI infrastructure investment thesis remains compelling through 2026-2028, driven by persistent compute demand from large language model training and inference workloads. Our 15-stock universe spans semiconductor manufacturing, data centre REITs, power infrastructure, and networking — reflecting the full capital stack required to sustain the AI buildout. The portfolio targets a risk-adjusted return of 18-24% p.a. over the investment horizon with quality score 8.4/10 and full IC approval." },
                  { h:"2. SECTOR ALLOCATION RATIONALE", body:"Compute (42%) leads the portfolio, anchored by NVDA and TSM as dominant picks by weight. Infrastructure (31%) provides exposure to the physical layer via data centre operators and networking equipment providers. Power & Energy (27%) captures the emerging constraint — electricity availability — that is increasingly binding for hyperscale expansion in both US and Australian markets." },
                  { h:"3. KEY RISKS — RED TEAM ASSESSMENT", body:"Primary risks include: (1) NVDA concentration risk — 22% single-name exposure exceeds typical risk limits; recommend staged reduction if quality score degrades. (2) Geopolitical risk — TSM Taiwan exposure carries tail risk requiring hedging consideration. (3) Interest rate sensitivity — the portfolio carries duration through data centre REIT holdings. (4) Regulatory risk — Australian AI sector faces emerging framework from ASIC and Treasury." },
                ].map(({h,body}) => (
                  <div key={h} style={{ marginBottom:16 }}>
                    <div style={S({ color: B.orange, fontSize:12, letterSpacing:"0.08em", marginBottom:6, borderBottom:`1px solid ${B.border2}`, paddingBottom:4 })}>{h}</div>
                    <div style={S({ color: B.gray, fontSize:12, lineHeight:1.8 })}>{body}</div>
                  </div>
                ))}
                <div style={{ display:"flex", gap:8, marginTop:12 }}>
                  {["DOWNLOAD .MD","DOWNLOAD PDF","EXPORT JSON","SHARE LINK"].map(btn => (
                    <button key={btn} style={S({ padding:"4px 14px", background:"transparent", border:`1px solid ${B.orange}`, color: B.orange, cursor:"pointer", fontSize:10, letterSpacing:"0.08em" })}>{btn}</button>
                  ))}
                </div>
              </div>
            </Panel>
          </div>
        )}

        {/* AUDIT SCREEN */}
        {screen === "AUDIT" && (
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:8, padding:8, flex:1, overflow:"auto" }}>
            <Panel title="QUALITY AUDIT PACKET" titleRight="SESSION 19">
              <div style={{ padding:"8px" }}>
                <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:8, marginBottom:8 }}>
                  {[["QUALITY SCORE","8.4/10",B.green],["GATES PASSED","12/15",B.orange],["IC APPROVED","YES",B.green],["MANDATE","COMPLIANT",B.green]].map(([l,v,c]) => (
                    <div key={l} style={{ border:`1px solid ${B.border}`, padding:"8px 10px" }}>
                      <div style={S({ color: B.yellow, fontSize:9, letterSpacing:"0.08em", marginBottom:4 })}>{l}</div>
                      <div style={S({ color: c, fontSize:18 })}>{v}</div>
                    </div>
                  ))}
                </div>
                {[["TOTAL CLAIMS","284"],["TIER 1 — VERIFIED","112"],["TIER 2 — HIGH CONF.","98"],["TIER 3 — SUPPORTED","54"],["TIER 4 — INFERRED","20"],["PASS","241"],["CAVEAT","32"],["FAIL","11"]].map(([l,v]) => (
                  <div key={l} style={{ display:"flex", justifyContent:"space-between", padding:"3px 4px", borderBottom:`1px solid ${B.border2}` }}>
                    <span style={S({ color: B.yellow, fontSize:10 })}>{l}</span>
                    <span style={S({ color: B.white, fontSize:11 })}>{v}</span>
                  </div>
                ))}
              </div>
            </Panel>
            <Panel title="AGENT OUTCOMES">
              <div style={{ padding:"6px" }}>
                <div style={S({ color: B.yellow, fontSize:9, letterSpacing:"0.08em", padding:"4px 2px", marginBottom:4 })}>SUCCEEDED</div>
                {["orchestrator","macro-strategist","sector-analyst-compute","evidence-librarian","valuation-analyst","red-team-analyst","associate-reviewer"].map(a => (
                  <div key={a} style={S({ color: B.green, fontSize:11, padding:"2px 4px", borderBottom:`1px solid ${B.border2}` })}>{"[OK]"} {a}</div>
                ))}
                <div style={S({ color: B.yellow, fontSize:9, letterSpacing:"0.08em", padding:"6px 2px 4px", borderTop:`1px solid ${B.border}`, marginTop:4 })}>BLOCKERS</div>
                <div style={S({ color: B.dgray, fontSize:11, padding:"2px 4px" })}>NO BLOCKERS DETECTED</div>
              </div>
            </Panel>
          </div>
        )}

        {/* QUANT SCREEN */}
        {screen === "QUANT" && (
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:8, padding:8, flex:1, overflow:"auto" }}>
            <Panel title="MARKET RISK METRICS">
              {[["PORTFOLIO VaR 95%","-3.2%",B.red],["PORTFOLIO VaR 99%","-5.1%",B.red],["MAX DRAWDOWN","-18.4%",B.red],["DRAWDOWN DURATION","42 DAYS",B.orange],["PORTFOLIO VOLATILITY","22.1%",B.orange],["BENCHMARK VOL","15.3%",B.gray],["TRACKING ERROR","8.4%",B.orange],["INFORMATION RATIO","0.88",B.cyan],["SHARPE RATIO (ANN)","1.34",B.green],["SORTINO RATIO","1.82",B.green],["CALMAR RATIO","0.97",B.cyan],["BETA (ASX200)","1.18",B.orange]].map(([l,v,c]) => (
                <div key={l} style={{ display:"flex", justifyContent:"space-between", padding:"3px 8px", borderBottom:`1px solid ${B.border2}` }}>
                  <span style={S({ color: B.yellow, fontSize:10 })}>{l}</span>
                  <span style={S({ color: c, fontSize:11 })}>{v}</span>
                </div>
              ))}
            </Panel>
            <Panel title="PORTFOLIO WEIGHTS">
              {positions.map(p => (
                <div key={p.ticker} style={{ padding:"5px 8px", borderBottom:`1px solid ${B.border2}` }}>
                  <div style={{ display:"flex", justifyContent:"space-between", marginBottom:3 }}>
                    <span style={S({ color: B.orange, fontSize:11 })}>{p.ticker}</span>
                    <span style={S({ color: B.white, fontSize:11 })}>{p.wt}%</span>
                  </div>
                  <div style={{ height:8, background:"#111" }}>
                    <div style={{ height:"100%", width:`${p.wt*4}%`, background: B.orange, opacity:0.7 }} />
                  </div>
                </div>
              ))}
            </Panel>
            <Panel title="ATTRIBUTION (BHB)">
              <div style={{ padding:"4px 0" }}>
                {[["ALLOCATION EFFECT","+2.4%",B.green],["SELECTION EFFECT","+4.1%",B.green],["INTERACTION EFFECT","-0.3%",B.red],["TOTAL ACTIVE RETURN","+6.2%",B.green]].map(([l,v,c]) => (
                  <div key={l} style={{ display:"flex", justifyContent:"space-between", padding:"5px 8px", borderBottom:`1px solid ${B.border2}` }}>
                    <span style={S({ color: B.yellow, fontSize:10 })}>{l}</span>
                    <span style={S({ color: c, fontSize:13 })}>{v}</span>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        )}

        {/* STAGES SCREEN */}
        {screen === "STAGES" && (
          <div style={{ padding:8, flex:1, overflow:"auto" }}>
            <Panel title="STAGE EXECUTION DETAIL — ALL 15 STAGES" titleRight="7 COMPLETE  1 RUNNING  7 PENDING">
              <table style={{ width:"100%", borderCollapse:"collapse" }}>
                <thead>
                  <tr style={{ borderBottom:`1px solid ${B.orange}` }}>
                    {["#","STAGE NAME","ASSIGNED AGENT","STATUS","DURATION","GATE","OUTPUT"].map(h => <TH key={h}>{h}</TH>)}
                  </tr>
                </thead>
                <tbody>
                  {stages.map((s,i) => (
                    <tr key={s.n} style={{ borderBottom:`1px solid ${B.border2}`, background: s.status==="running" ? "#1a0d00" : i%2===0 ? "#050505" : "transparent" }}>
                      <TD color={B.gray}>S{String(s.n).padStart(2,"0")}</TD>
                      <TD color={s.status==="running" ? B.orange : s.status==="completed" ? B.white : B.dgray}>{s.status==="running" && "► "}{s.label}</TD>
                      <TD color={B.gray}>{s.agent}</TD>
                      <td style={S({ padding:"3px 8px" })}>
                        <span style={S({ color: s.status==="completed"?B.green:s.status==="running"?B.orange:B.dgray, fontSize:10, letterSpacing:"0.06em" })}>
                          {s.status==="completed"?"COMPLETE":s.status==="running"?"RUNNING":"PENDING"}
                        </span>
                      </td>
                      <TD color={B.cyan}>{s.dur || (s.status==="running"?"...":"—")}</TD>
                      <TD color={s.status==="completed"?B.green:B.dgray}>{s.status==="completed"?"✓ PASS":"—"}</TD>
                      <TD color={B.gray}>{s.status==="completed"?`${s.label.toLowerCase().replace(/ /g,"_")}_output.json`:"—"}</TD>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          </div>
        )}

        {/* NEW RUN SCREEN */}
        {screen === "NEW RUN" && (
          <div style={{ padding:8, flex:1, overflow:"auto" }}>
            <div style={{ maxWidth:700 }}>
              <Panel title="NEW PIPELINE RUN — CONFIGURATION">
                <div style={{ padding:"12px 16px", display:"flex", flexDirection:"column", gap:14 }}>
                  <div>
                    <div style={S({ color: B.yellow, fontSize:10, letterSpacing:"0.1em", marginBottom:6 })}>TICKER UNIVERSE</div>
                    <div style={{ display:"flex", gap:8 }}>
                      <input value={tkInput} onChange={e => setTkInput(e.target.value.toUpperCase())}
                        onKeyDown={e => { if(e.key==="Enter" && tkInput.trim()) { setTickers(t=>[...t, tkInput.trim()]); setTkInput(""); }}}
                        placeholder="ENTER TICKER + ENTER" maxLength={6}
                        style={S({ padding:"5px 10px", background:"#0a0a0a", border:`1px solid ${B.orange}`, color: B.yellow, fontSize:12, outline:"none", width:180 })} />
                    </div>
                    <div style={{ display:"flex", flexWrap:"wrap", gap:4, marginTop:8 }}>
                      {tickers.map(t => (
                        <span key={t} onClick={() => setTickers(ts => ts.filter(x=>x!==t))}
                          style={S({ padding:"3px 10px", background:"#1a0d00", border:`1px solid ${B.orange}`, color: B.orange, fontSize:11, cursor:"pointer" })}>
                          {t} [×]
                        </span>
                      ))}
                    </div>
                  </div>
                  {[["DEFAULT MODEL","claude-sonnet-4-6"],["MARKET","AU / ASX + GLOBAL"],["BENCHMARK","ASX 200"],["MAX POSITIONS","15"],["LLM TEMPERATURE","0.1"],["PORTFOLIO VARIANTS","EQUAL-WEIGHT, OPTIMISED, RISK-PARITY"]].map(([l,v]) => (
                    <div key={l} style={{ display:"flex", alignItems:"center", gap:20, borderBottom:`1px solid ${B.border2}`, paddingBottom:8 }}>
                      <span style={S({ color: B.yellow, fontSize:10, letterSpacing:"0.08em", width:180 })}>{l}</span>
                      <span style={S({ color: B.white, fontSize:12 })}>{v}</span>
                    </div>
                  ))}
                  <button onClick={() => setScreen("MONITOR")}
                    style={S({ padding:"8px 24px", background: B.orange, color: B.bg, border:"none", cursor:"pointer", fontSize:12, letterSpacing:"0.12em", alignSelf:"flex-start", fontWeight:"bold" })}>
                    INITIATE PIPELINE  [GO]
                  </button>
                </div>
              </Panel>
            </div>
          </div>
        )}

        {/* SAVED SCREEN */}
        {screen === "SAVED" && (
          <div style={{ padding:8, flex:1, overflow:"auto" }}>
            <Panel title="SAVED RESEARCH REPORTS" titleRight="3 RECORDS">
              <table style={{ width:"100%", borderCollapse:"collapse" }}>
                <thead>
                  <tr style={{ borderBottom:`1px solid ${B.orange}` }}>
                    {["RUN ID","UNIVERSE","SCORE","WORDS","STATUS","DATE","ACTIONS"].map(h => <TH key={h}>{h}</TH>)}
                  </tr>
                </thead>
                <tbody>
                  {[
                    { id:"20260406_143012", tickers:["NVDA","TSM","MSFT","AMZN","GOOGL"], score:8.4, words:14200, status:"COMPLETE", date:"06 APR 14:30" },
                    { id:"20260405_091533", tickers:["AAPL","META","AMD","INTC","QCOM"],  score:7.9, words:11800, status:"COMPLETE", date:"05 APR 09:15" },
                    { id:"20260404_161002", tickers:["ASML","AMAT","LRCX","KLAC","MU"],   score:null, words:null, status:"FAILED",   date:"04 APR 16:10" },
                  ].map((r,i) => (
                    <tr key={r.id} style={{ borderBottom:`1px solid ${B.border2}`, background: i%2===0?"#050505":"transparent" }}>
                      <TD color={B.orange}>{r.id}</TD>
                      <TD color={B.gray}>{r.tickers.join(" ")}</TD>
                      <TD color={r.score?B.green:B.dgray}>{r.score?r.score.toFixed(1):"—"}</TD>
                      <TD color={B.white}>{r.words?r.words.toLocaleString():"—"}</TD>
                      <TD color={r.status==="COMPLETE"?B.green:B.red}>{r.status}</TD>
                      <TD color={B.gray}>{r.date}</TD>
                      <td style={S({ padding:"3px 8px" })}>
                        <button onClick={() => setScreen("REPORT")} style={S({ padding:"2px 10px", background:"transparent", border:`1px solid ${B.orange}`, color: B.orange, cursor:"pointer", fontSize:9, letterSpacing:"0.06em" })}>VIEW</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          </div>
        )}
      </div>

      {/* ── FUNCTION KEY BAR ── */}
      <div style={{ background:"#111", borderTop:`2px solid ${B.border}`, padding:"3px 4px", display:"flex", flexShrink:0, gap:1 }}>
        {fkeys.map((f,i) => (
          <button key={f} onClick={() => {
            const actions = ["","","","",() => setScreen("REPORT"),() => setScreen("AUDIT"),() => setScreen("QUANT"),() => setScreen("STAGES"),() => setScreen("NEW RUN"),null,null,null];
            if(typeof actions[i] === "function") actions[i]();
          }}
            style={S({ flex:1, padding:"3px 2px", background:"#1a1a1a", border:`1px solid ${B.border2}`, color: B.gray, fontSize:9, cursor:"pointer", letterSpacing:"0.04em", textAlign:"center" })}>
            {f}
          </button>
        ))}
      </div>
    </div>
  );
}
