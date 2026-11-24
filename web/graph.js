const ns = "http://www.w3.org/2000/svg";

function svgElement(name, attrs = {}) {
  const element = document.createElementNS(ns, name);
  for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
  return element;
}

export function readSetting(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem("coauthor-network:" + key)) ?? fallback;
  } catch {
    return fallback;
  }
}

export function saveSetting(key, value) {
  try { localStorage.setItem("coauthor-network:" + key, JSON.stringify(value)); }
  catch { /* Storage can be unavailable in a private browser. */ }
}

export function pairKey(a, b) {
  return [a, b].sort().join("|");
}

function overlaps(a, b) {
  return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
}

export class CoauthorGraph {
  constructor(svg, onChoose) {
    this.svg = svg;
    this.onChoose = onChoose;
    this.edges = [];
    this.nodes = new Map();
    this.points = new Map();
    this.saved = readSetting("positions", {}) || {};
    this.camera = [0, 0];
    this.zoom = 1;
    this.tooltip = document.querySelector("#tooltip");
    this.measure = document.createElement("canvas").getContext("2d");
    this.installControls();
    new ResizeObserver(() => this.draw()).observe(svg);
    document.fonts.ready.then(() => this.draw());
  }

  setData(data, mode) {
    const view = data.modes[mode];
    this.data = data;
    // Use a common layout for both views. Preserve existing people across live refreshes.
    for (const [id, base] of Object.entries(data.layout)) {
      const saved = this.saved[id];
      if (Array.isArray(saved) && saved.length === 2 && saved.every(Number.isFinite)) {
        this.points.set(id, saved);
      } else if (!this.points.has(id)) {
        this.points.set(id, base);
      }
    }
    this.edges = view.edges.map(edge => {
      const key = pairKey(edge.a, edge.b);
      const count = edge.papers.length;
      const label = data.people[edge.a] + " and " + data.people[edge.b] + " · "
        + count + (count === 1 ? " shared paper" : " shared papers");
      const element = svgElement("g", {
        class: "edge", "data-edge": key, role: "button", tabindex: "0", "aria-label": label,
      });
      const line = svgElement("line", {class: "line", "stroke-width": 1 + 1.25 * Math.log2(count)});
      const hit = svgElement("line", {class: "hit"});
      element.append(line, hit);
      return {...edge, key, element, line, hit};
    });
    this.nodes = new Map(Object.entries(view.nodes).map(([id, count]) => {
      const radius = Math.min(15, 3.3 + 1.7 * Math.sqrt(count));
      const label = data.people[id] + " · " + count + (count === 1 ? " paper" : " papers");
      const element = svgElement("g", {
        class: "node", "data-author": id, role: "button", tabindex: "0", "aria-label": label,
      });
      const name = svgElement("text", {"dominant-baseline": "middle"});
      name.textContent = data.people[id];
      element.append(svgElement("circle", {class: "hit", r: Math.max(11, radius + 3)}),
        svgElement("circle", {class: "halo", r: radius + 2.7}),
        svgElement("circle", {class: "dot", r: radius}), name);
      return [id, {id, count, element, name, radius}];
    }));
    this.svg.querySelector("#edges").replaceChildren(...this.edges.map(e => e.element));
    this.svg.querySelector("#nodes").replaceChildren(...Array.from(this.nodes.values(), n => n.element));
    this.tooltip.hidden = true;
  }

  highlight({center, person, paper, pair}) {
    this.center = center;
    const active = new Set();
    const hasSelection = Boolean(person || paper || pair);
    if (paper) for (const author of paper.authors) active.add(author.id);
    if (person) active.add(person);
    for (const edge of this.edges) {
      const incident = edge.a === center || edge.b === center;
      const selected = paper ? edge.papers.includes(paper.id)
        : pair ? edge.key === pair : person && (edge.a === person || edge.b === person);
      edge.element.classList.toggle("incident", incident);
      edge.element.classList.toggle("active", Boolean(selected));
      edge.element.classList.toggle("muted", hasSelection && !selected);
      if (selected) { active.add(edge.a); active.add(edge.b); }
    }
    for (const node of this.nodes.values()) {
      node.element.classList.toggle("center", node.id === center);
      node.element.classList.toggle("major", node.count > 2);
      node.element.classList.toggle("active", active.has(node.id));
      node.element.classList.toggle("muted", hasSelection && !active.has(node.id));
    }
    this.draw();
  }

  centerOn(id) {
    this.camera = [...this.points.get(id)];
    this.draw();
  }

  reset() {
    this.saved = {};
    saveSetting("positions", {});
    this.points = new Map(Object.entries(this.data.layout));
    this.camera = [0, 0];
    this.zoom = 1;
    this.draw();
  }

  draw() {
    if (!this.nodes.size) return;
    const w = this.svg.clientWidth, h = this.svg.clientHeight;
    if (!w || !h) return;
    const sx = Math.max(60, w / 2 - Math.min(90, w * .07)) * this.zoom;
    const sy = Math.max(45, h / 2 - 24) * this.zoom;
    this.frame = {w, h, sx, sy};
    for (const n of this.nodes.values()) {
      const pos = this.points.get(n.id);
      n.x = w / 2 + (pos[0] - this.camera[0]) * sx;
      n.y = h / 2 + (pos[1] - this.camera[1]) * sy;
      n.element.setAttribute("transform", "translate(" + n.x + " " + n.y + ")");
    }
    for (const edge of this.edges) {
      const a = this.nodes.get(edge.a), b = this.nodes.get(edge.b);
      for (const line of [edge.line, edge.hit]) {
        line.setAttribute("x1", a.x); line.setAttribute("y1", a.y);
        line.setAttribute("x2", b.x); line.setAttribute("y2", b.y);
      }
    }
    this.placeLabels();
  }

  placeLabels() {
    const {w, h} = this.frame;
    const nodes = [...this.nodes.values()];
    const priority = n => (n.id === this.center ? 1000 : 0)
      + (n.element.classList.contains("active") ? 200 : 0) + n.count;
    nodes.sort((a, b) => priority(b) - priority(a));
    const obstacles = nodes.map(n => ({left: n.x - n.radius - 1, right: n.x + n.radius + 1,
      top: n.y - n.radius - 1, bottom: n.y + n.radius + 1}));
    for (const n of nodes) {
      const important = n.id === this.center || n.element.classList.contains("active");
      this.measure.font = important ? '700 14px "DM Sans", sans-serif' : '500 12.5px "DM Sans", sans-serif';
      const width = this.measure.measureText(n.name.textContent).width + 4;
      const r = n.radius + 3, side = n.x > w / 2 ? 1 : -1;
      const positions = [
        [side > 0 ? r : -width - r, 0], [side > 0 ? -width - r : r, 0],
        [-width / 2, r + 8], [-width / 2, -r - 8],
        [r, r + 5], [-width - r, -r - 5], [r, -r - 5], [-width - r, r + 5],
      ];
      let placed = false;
      for (const [dx, dy] of positions) {
        const box = {left: n.x + dx, right: n.x + dx + width, top: n.y + dy - 8, bottom: n.y + dy + 8};
        if (box.left < 2 || box.right > w - 2 || box.top < 1 || box.bottom > h - 1) continue;
        if (obstacles.some(other => overlaps(box, other))) continue;
        n.name.setAttribute("x", dx + 2);
        n.name.setAttribute("y", dy);
        obstacles.push(box);
        placed = true;
        break;
      }
      n.name.style.display = placed ? "" : "none";
    }
  }

  zoomBy(factor, x = this.frame.w / 2, y = this.frame.h / 2) {
    const {w, h, sx, sy} = this.frame;
    const next = Math.max(.4, Math.min(6, this.zoom * factor));
    const offset = 1 - this.zoom / next;
    this.camera[0] += (x - w / 2) * offset / sx;
    this.camera[1] += (y - h / 2) * offset / sy;
    this.zoom = next;
    this.draw();
  }

  choose(element) {
    if (element?.dataset.author) this.onChoose("author", element.dataset.author);
    else if (element?.dataset.edge) this.onChoose("edge", element.dataset.edge);
    else this.onChoose("clear");
    this.tooltip.hidden = true;
  }

  showTooltip(element, x, y) {
    if (!element || this.drag) { this.tooltip.hidden = true; return; }
    this.tooltip.textContent = element.getAttribute("aria-label");
    this.tooltip.hidden = false;
    const {w, h} = this.frame;
    this.tooltip.style.left = Math.max(4, Math.min(x + 12, w - this.tooltip.offsetWidth - 4)) + "px";
    this.tooltip.style.top = Math.max(4, Math.min(y + 12, h - this.tooltip.offsetHeight - 4)) + "px";
  }

  installControls() {
    const svg = this.svg;
    const target = event => event.target.closest("[data-author], [data-edge]");
    svg.addEventListener("pointerdown", event => {
      if (event.button !== 0 || this.drag || !this.frame) return;
      const id = target(event)?.dataset.author;
      this.drag = {id, pointer: event.pointerId, x: event.clientX, y: event.clientY,
        start: [...(id ? this.points.get(id) : this.camera)], moved: false};
      this.skipClick = false;
      this.tooltip.hidden = true;
    });
    svg.addEventListener("pointermove", event => {
      const rect = svg.getBoundingClientRect();
      if (!this.drag) {
        this.showTooltip(target(event), event.clientX - rect.left, event.clientY - rect.top);
        return;
      }
      const drag = this.drag;
      if (event.pointerId !== drag.pointer) return;
      const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) < 4) return;
      if (!drag.moved) svg.setPointerCapture(event.pointerId);
      drag.moved = true;
      svg.classList.add("dragging");
      const {sx, sy} = this.frame;
      if (drag.id) this.points.set(drag.id, [drag.start[0] + dx / sx, drag.start[1] + dy / sy]);
      else this.camera = [drag.start[0] - dx / sx, drag.start[1] - dy / sy];
      this.draw();
    });
    const finishDrag = event => {
      if (!this.drag || event.pointerId !== this.drag.pointer) return;
      const {id, moved} = this.drag;
      this.skipClick = moved;
      if (id && moved) {
        this.saved[id] = this.points.get(id);
        saveSetting("positions", this.saved);
      }
      this.drag = null;
      svg.classList.remove("dragging");
    };
    window.addEventListener("pointerup", finishDrag);
    window.addEventListener("pointercancel", finishDrag);
    svg.addEventListener("click", event => { if (!this.skipClick) this.choose(target(event)); });
    svg.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        this.choose(target(event));
      }
    });
    svg.addEventListener("pointerleave", () => { this.tooltip.hidden = true; });
    svg.addEventListener("focusin", event => {
      const element = target(event);
      if (!element) return;
      const bbox = element.getBoundingClientRect(), rect = svg.getBoundingClientRect();
      this.showTooltip(element, bbox.left + bbox.width / 2 - rect.left, bbox.top + bbox.height / 2 - rect.top);
    });
    svg.addEventListener("focusout", () => { this.tooltip.hidden = true; });
    svg.addEventListener("wheel", event => {
      if (!this.frame) return;
      event.preventDefault();
      const rect = svg.getBoundingClientRect();
      this.zoomBy(Math.exp(-Math.sign(event.deltaY) * .13), event.clientX - rect.left, event.clientY - rect.top);
    }, {passive: false});
    document.querySelector("#zoom-in").onclick = () => { if (this.frame) this.zoomBy(1.3); };
    document.querySelector("#zoom-out").onclick = () => { if (this.frame) this.zoomBy(1 / 1.3); };
  }
}
