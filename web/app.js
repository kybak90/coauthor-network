import {CoauthorGraph, pairKey} from "./graph.js";

const $ = selector => document.querySelector(selector);
const rows = $("#rows"), scroll = $("#table-scroll"), centerPicker = $("#center");
const state = {
  mode: history.state?.coauthorMode === "accepted" ? "accepted" : "ongoing",
  center: null, person: null, paper: null, pair: null,
};
let data, version, papers, pairIndex, loading = false;

function clearSelection() {
  state.person = state.paper = state.pair = null;
}

function showSharedPapers(pair) {
  state.pair = pair;
  expand(true);
  scroll.scrollTop = 0;
}

function chooseAuthor(id, showPapers = false) {
  clearSelection();
  state.center = state.person = id;
  if (showPapers) showSharedPapers(id === data.focus ? null : pairKey(data.focus, id));
  graph.centerOn(id);
  renderPapers();
}

const graph = new CoauthorGraph($("#graph"), (type, id) => {
  if (type === "author") { chooseAuthor(id, true); return; }
  clearSelection();
  if (type === "edge") showSharedPapers(id);
  renderPapers();
});

function expand(open) {
  $("#paper-toggle").setAttribute("aria-expanded", String(open));
  scroll.hidden = !open;
}

function highlight() {
  // The table shows papers with Bak while the graph highlights all of the selected author's connections.
  graph.highlight({...state, pair: state.person ? null : state.pair, paper: papers.get(state.paper)});
  centerPicker.value = state.center;
  $("#clear-paper").hidden = !(state.paper || (state.person && !state.pair));
  for (const row of rows.children) {
    const selected = row.dataset.paper === state.paper;
    row.classList.toggle("selected", selected);
    row.querySelector("button").setAttribute("aria-pressed", String(selected));
  }
}

function renderPapers() {
  const edge = pairIndex.get(state.pair);
  const ids = edge ? edge.papers : data.modes[state.mode].papers;
  $("#row-count").textContent = ids.length;
  $("#all-papers").hidden = !edge;
  $("#pair-caption").hidden = !edge;
  $("#pair-caption").textContent = edge ? data.people[edge.a] + " × " + data.people[edge.b] : "";
  const fragment = document.createDocumentFragment();
  for (const id of ids) {
    const paper = papers.get(id);
    const row = document.createElement("tr");
    row.dataset.paper = id;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = paper.title;
    row.insertCell().append(button);
    const venue = row.insertCell();
    venue.textContent = paper.venue;
    if (paper.status === "ongoing") venue.className = "ongoing-venue";
    row.insertCell().textContent = paper.authors.map(a => a.name).join(", ");
    fragment.append(row);
  }
  const previousScroll = scroll.scrollTop;
  rows.replaceChildren(fragment);
  scroll.scrollTop = previousScroll;
  highlight();
}

function renderMode() {
  const view = data.modes[state.mode];
  pairIndex = new Map(view.edges.map(edge => [pairKey(edge.a, edge.b), edge]));
  if (state.paper && !view.papers.includes(state.paper)) clearSelection();
  const filteredEdge = pairIndex.get(state.pair);
  if (!filteredEdge || (state.paper && !filteredEdge.papers.includes(state.paper))) state.pair = null;
  if (!(state.person in view.nodes)) state.person = null;
  const lostCenter = state.center && !(state.center in view.nodes);
  if (!state.center || lostCenter) state.center = data.focus;
  const choices = Object.keys(view.nodes).sort((a, b) => data.people[a].localeCompare(data.people[b], "en"));
  centerPicker.replaceChildren(...choices.map(id => new Option(data.people[id], id)));
  $("input[value='" + state.mode + "']").checked = true;
  $("#author-count").textContent = choices.length;
  $("#edge-count").textContent = view.edges.length;
  $("#paper-count").textContent = view.papers.length;
  graph.setData(data, state.mode);
  if (lostCenter) graph.centerOn(data.focus);
  renderPapers();
}

rows.addEventListener("click", event => {
  const row = event.target.closest("tr");
  if (!row) return;
  if (state.paper === row.dataset.paper) {
    const wasFiltered = Boolean(state.pair);
    clearSelection();
    if (wasFiltered) { renderPapers(); return; }
  } else {
    state.person = null;
    state.paper = row.dataset.paper;
  }
  highlight();
});
for (const radio of document.querySelectorAll("input[name=mode]")) {
  radio.checked = radio.value === state.mode;
  radio.addEventListener("change", () => {
    state.mode = radio.value;
    history.replaceState({...history.state, coauthorMode: state.mode}, "");
    if (data) renderMode();
  });
}
centerPicker.onchange = () => chooseAuthor(centerPicker.value);
$("#paper-toggle").onclick = () => expand(scroll.hidden);
$("#all-papers").onclick = $("#clear-paper").onclick = () => { clearSelection(); renderPapers(); };
$("#reset").onclick = () => {
  if (!data) return;
  clearSelection();
  state.center = data.focus;
  graph.reset();
  renderPapers();
};

async function getJSON(path) {
  const response = await fetch(new URL(path, document.baseURI), {cache: "no-store"});
  if (!response.ok) throw new Error(path + " returned HTTP " + response.status);
  return response.json();
}

async function refresh() {
  if (loading || document.hidden || graph.drag) return;
  loading = true;
  try {
    const manifest = await getJSON("version.json");
    if (!/^[a-f0-9]{64}$/.test(manifest.version)) throw new Error("Invalid data version");
    if (version !== manifest.version) {
      const next = await getJSON("data-" + manifest.version + ".json");
      const previous = papers?.get(state.paper);
      if (previous && !next.papers.some(p => p.id === previous.id)) {
        // A DOI can first appear when an ongoing paper is accepted.
        state.paper = next.papers.find(p => p.signature === previous.signature)?.id ?? null;
      }
      data = next;
      papers = new Map(data.papers.map(p => [p.id, p]));
      renderMode();
      version = manifest.version;
    }
    $("#status").hidden = true;
  } catch (error) {
    console.error("Unable to refresh the public catalog", error);
    $("#status").textContent = data ? "Showing the last loaded catalog. The next check will retry."
      : "The catalog could not be loaded. Reload to try again.";
    $("#status").hidden = false;
  } finally {
    loading = false;
  }
}

document.addEventListener("visibilitychange", refresh);
window.addEventListener("focus", refresh);
window.setInterval(refresh, 5 * 60 * 1000);
refresh();
