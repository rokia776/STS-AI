"""
view_graph.py - interactive view of papers, entities and relations from graphrag.db.
Run:  uv run python view_graph.py
"""
import json
import sqlite3
import webbrowser
from pathlib import Path

DB = "graphrag.db"
OUT = "graph_view.html"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row


def cols(table):
    return [r["name"] for r in con.execute(f"PRAGMA table_info({table})")]


def pick(cs, exact=(), contains=()):
    low = {c.lower(): c for c in cs}
    for k in exact:
        if k in low:
            return low[k]
    for k in contains:
        for l, c in low.items():
            if k in l:
                return c
    return None


nodes = {}

# ---- entities (id, canonical_name, name, type) ----
for r in con.execute("SELECT * FROM entities"):
    d = dict(r)
    label = str(d.get("canonical_name") or d.get("name") or d["id"])
    nodes[f"e{d['id']}"] = {
        "id": f"e{d['id']}",
        "label": label if len(label) <= 28 else label[:26] + "…",
        "type": str(d.get("type") or "entity"),
        "details": {k: str(v)[:300] for k, v in d.items() if v is not None},
    }

# ---- papers ----
pc = cols("papers")
print("papers columns:", pc)
P_ID = pick(pc, exact=("paper_id", "id"))
P_TITLE = pick(pc, exact=("title", "name", "filename", "file_name"), contains=("title", "name", "file"))
for r in con.execute("SELECT * FROM papers"):
    d = dict(r)
    pid = str(d.get(P_ID))
    title = str(d.get(P_TITLE) or pid)
    nodes[f"p{pid}"] = {
        "id": f"p{pid}",
        "label": title if len(title) <= 32 else title[:30] + "…",
        "type": "paper",
        "details": {k: str(v)[:300] for k, v in d.items() if v is not None},
    }

# ---- edges (paper_id, entity_id, relation) : paper --relation--> entity ----
edges = []
for r in con.execute("SELECT * FROM edges"):
    d = dict(r)
    p, e = f"p{d['paper_id']}", f"e{d['entity_id']}"
    for nid, raw in ((p, d["paper_id"]), (e, d["entity_id"])):
        if nid not in nodes:  # مرجع مش موجود في الجدول الأصلي
            nodes[nid] = {"id": nid, "label": str(raw)[:28], "type": "unresolved",
                          "details": {"value": str(raw)}}
    edges.append({"from": p, "to": e, "label": str(d.get("relation") or ""), "paper": str(d["paper_id"])})

papers = [{"id": n["id"][1:], "title": n["label"]} for n in nodes.values() if n["type"] == "paper"]
data = {
    "nodes": list(nodes.values()),
    "edges": edges,
    "papers": papers,
    "relations": sorted({e["label"] for e in edges}),
}

HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>GraphRAG viewer</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
 body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:#12151c;color:#e6e6e6;display:flex;height:100vh}
 #side{width:320px;padding:12px;overflow:auto;background:#1b1f2a;border-right:1px solid #2c3242}
 #net{flex:1}
 input,select{width:100%;padding:7px;margin:4px 0 10px;background:#12151c;color:#e6e6e6;border:1px solid #3a4157;border-radius:6px}
 h3{margin:6px 0} .muted{color:#8b93a7;font-size:12px}
 .leg{display:inline-block;margin:2px 6px 2px 0;font-size:12px}
 .dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}
 pre{white-space:pre-wrap;word-break:break-word;font-size:12px;background:#12151c;padding:8px;border-radius:6px}
</style></head><body>
<div id="side">
 <h3>GraphRAG viewer</h3>
 <div class="muted" id="stats"></div>
 <label>Paper</label><select id="paper"><option value="">— All papers —</option></select>
 <label>Relation</label><select id="rel"><option value="">— All —</option></select>
 <label>Entity type</label><select id="type"><option value="">— All —</option></select>
 <label>Search</label><input id="q" placeholder="Entity or paper name, then Enter">
 <div id="legend"></div>
 <h3>Details</h3><pre id="info">Click a node or a relation</pre>
</div>
<div id="net"></div>
<script>
const DATA = __DATA__;
const palette=["#4e79a7","#f28e2b","#e15759","#76b7b2","#59a14f","#edc948","#b07aa1","#ff9da7","#9c755f","#bab0ac"];
const types=[...new Set(DATA.nodes.map(n=>n.type))].filter(t=>t!=="paper").sort();
const color={paper:"#ffffff"}; types.forEach((t,i)=>color[t]=palette[i%palette.length]);
const byId={}; DATA.nodes.forEach(n=>byId[n.id]=n);
const paperSel=document.getElementById("paper"), typeSel=document.getElementById("type"), relSel=document.getElementById("rel");
DATA.papers.forEach(p=>paperSel.add(new Option(p.title,p.id)));
DATA.relations.forEach(r=>relSel.add(new Option(r,r)));
types.forEach(t=>typeSel.add(new Option(t,t)));
document.getElementById("legend").innerHTML=["paper",...types].map(t=>`<span class="leg"><span class="dot" style="background:${color[t]}"></span>${t}</span>`).join("");

const nodes=new vis.DataSet(), edges=new vis.DataSet();
const net=new vis.Network(document.getElementById("net"),{nodes,edges},{
  nodes:{shape:"dot",size:11,font:{color:"#e6e6e6",size:13}},
  edges:{arrows:"to",color:{color:"#5b647c",highlight:"#fff"},font:{color:"#aab2c5",size:9,strokeWidth:0,align:"middle"},smooth:{type:"continuous"}},
  physics:{solver:"forceAtlas2Based",stabilization:{iterations:250}},
  interaction:{hover:true,tooltipDelay:150}
});

function render(){
  const p=paperSel.value, r=relSel.value, t=typeSel.value;
  let es=DATA.edges.filter(e=>(!p||e.paper===p)&&(!r||e.label===r)&&(!t||byId[e.to].type===t));
  const ids=new Set(); es.forEach(e=>{ids.add(e.from);ids.add(e.to)});
  nodes.clear(); edges.clear();
  nodes.add([...ids].map(id=>{const n=byId[id], isP=n.type==="paper";
    return {id:id,label:n.label,color:color[n.type]||"#888",shape:isP?"box":"dot",size:isP?18:11,
            font:isP?{color:"#111",size:14}:undefined,title:n.type+": "+n.label};}));
  edges.add(es.map((e,i)=>({id:"r"+i,from:e.from,to:e.to,label:p?e.label:"",_name:e.label,_paper:e.paper})));
  document.getElementById("stats").textContent=ids.size+" nodes · "+es.length+" relations";
}
paperSel.onchange=relSel.onchange=typeSel.onchange=render; render();

document.getElementById("q").addEventListener("keydown",ev=>{
  if(ev.key!=="Enter")return;
  const s=ev.target.value.toLowerCase();
  const hit=nodes.get().filter(n=>n.label.toLowerCase().includes(s)).map(n=>n.id);
  net.selectNodes(hit); if(hit.length) net.fit({nodes:hit,animation:true});
  document.getElementById("info").textContent=hit.length+" match(es)";
});
net.on("click",p=>{
  const info=document.getElementById("info");
  if(p.nodes.length){ info.textContent=JSON.stringify(byId[p.nodes[0]].details,null,2); }
  else if(p.edges.length){ const e=edges.get(p.edges[0]);
    info.textContent=byId[e.from].label+"\\n  —["+e._name+"]→\\n"+byId[e.to].label; }
});
</script></body></html>"""

Path(OUT).write_text(HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False)), encoding="utf-8")
print(f"Done: {len(data['nodes'])} nodes, {len(edges)} edges -> {OUT}")
webbrowser.open(Path(OUT).resolve().as_uri())