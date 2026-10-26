/* Week 7 interactive story: plain JavaScript (+ plotly from a CDN for figure 4).
   All data comes from JSON files exported by the analysis notebook. */
(function () {
  "use strict";

  var root = document.querySelector("[data-story-base]");
  if (!root) return;
  var BASE = root.getAttribute("data-story-base");
  var SVGNS = "http://www.w3.org/2000/svg";
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

  /* ---------- shared helpers ---------- */

  var cache = {};
  function load(name) {
    if (!cache[name]) {
      cache[name] = fetch(BASE + name).then(function (r) {
        if (!r.ok) throw new Error(name + " " + r.status);
        return r.json();
      });
    }
    return cache[name];
  }

  function theme() {
    var cs = getComputedStyle(document.documentElement);
    var v = function (n) { return cs.getPropertyValue(n).trim(); };
    return { ink: v("--ink"), ink2: v("--ink-2"), ink3: v("--ink-3"), accent: v("--accent"),
             paper: v("--paper"), paper2: v("--paper-2"), pos: v("--pos") || v("--ink") };
  }
  var themeListeners = [];
  function onTheme(fn) { themeListeners.push(fn); }
  darkQuery.addEventListener("change", function () { themeListeners.forEach(function (fn) { fn(); }); });

  function el(tag, attrs, children) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") n.textContent = attrs[k];
      else if (k === "html") n.innerHTML = attrs[k];
      else n.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }
  function svg(tag, attrs) {
    var n = document.createElementNS(SVGNS, tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    return n;
  }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  function fmt(x, d) {
    if (x === null || x === undefined) return "–";
    var s = Math.abs(x).toFixed(d === undefined ? 2 : d);
    return (x > 0 ? "+" : x < 0 ? "−" : "±") + s;
  }
  function shortName(n) { return n.replace(/ \((Marvel Comics|character|comics|characters)\)$/, ""); }
  function sign(x) { return x > 0 ? "pos" : x < 0 ? "neg" : "zero"; }

  // Initialise a widget when it comes close to the viewport (keeps the page light).
  function whenNear(node, fn) {
    if (!("IntersectionObserver" in window)) { fn(); return; }
    var io = new IntersectionObserver(function (entries) {
      if (entries.some(function (e) { return e.isIntersecting; })) { io.disconnect(); fn(); }
    }, { rootMargin: "400px 0px" });
    io.observe(node);
  }
  function fail(stage, err) {
    stage.innerHTML = "";
    stage.appendChild(el("p", { "class": "widget__error", text: "Could not load the data for this figure (" + err.message + ")." }));
  }

  /* ---------- Figure 1: Ally or enemy? ---------- */

  function initGame(box) {
    var stage = box.querySelector(".widget__stage");
    load("game.json").then(function (items) {
      var byId = {};
      items.forEach(function (it) { byId[it.id] = it; });
      // A few telling cases first, then the rest of the 40 in a fixed shuffled order.
      var first = [19, 6, 29, 33, 14];
      var rest = items.map(function (it) { return it.id; }).filter(function (id) { return first.indexOf(id) < 0; });
      var seed = 7;
      for (var i = rest.length - 1; i > 0; i--) {
        seed = (seed * 16807) % 2147483647;
        var j = seed % (i + 1), t = rest[i]; rest[i] = rest[j]; rest[j] = t;
      }
      var order = first.concat(rest).map(function (id) { return byId[id]; });
      var pos = 0;
      var tally = { you: [0, 0], bert: [0, 0], vader: [0, 0], kw: [0, 0] };
      var seen = {};

      stage.innerHTML = "";
      var head = el("div", { "class": "game__head" });
      var sents = el("div", { "class": "game__sentences" });
      var guesses = el("div", { "class": "game__guesses", role: "group", "aria-label": "Your guess" });
      var reveal = el("div", { "class": "game__reveal", "aria-live": "polite" });
      var foot = el("div", { "class": "game__foot" });
      var score = el("p", { "class": "game__score" });
      var next = el("button", { "class": "btn", type: "button", text: "Next sentence →" });
      foot.appendChild(score); foot.appendChild(next);
      [head, sents, guesses, reveal, foot].forEach(function (n) { stage.appendChild(n); });

      var LABELS = ["ally", "enemy", "family", "neutral"];
      var buttons = LABELS.map(function (lab) {
        var b = el("button", { "class": "btn btn--choice", type: "button", "data-label": lab, text: lab });
        b.addEventListener("click", function () { guess(lab); });
        guesses.appendChild(b);
        return b;
      });
      next.addEventListener("click", function () { pos = (pos + 1) % order.length; show(); next.blur(); });

      function sentenceHTML(s, highlight) {
        var t = esc(s.text);
        if (highlight && s.kw_words.length) {
          var words = s.kw_words.map(function (w) { return w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); });
          t = t.replace(new RegExp("\\b(" + words.join("|") + ")\\b", "gi"), "<mark>$1</mark>");
        }
        return t;
      }

      function renderSentences(it, revealed) {
        sents.innerHTML = "";
        var max = 3, all = it.sentences.length;
        var showAll = sents.getAttribute("data-all") === "1";
        it.sentences.forEach(function (s, k) {
          if (k >= max && !showAll) return;
          var q = el("blockquote", { "class": "game__quote" });
          q.innerHTML = "<p>“" + sentenceHTML(s, revealed) + "”</p>" +
            (revealed ? "<p class=\"game__sentscore\">DistilBERT " + fmt(s.bert) + " · VADER " + fmt(s.vader) +
              " · keywords " + fmt(s.kw, 0) + "</p>" : "");
          sents.appendChild(q);
        });
        if (all > max) {
          var more = el("button", { "class": "linkbtn", type: "button",
            text: showAll ? "Show fewer sentences" : "Show all " + all + " sentences" });
          more.addEventListener("click", function () {
            sents.setAttribute("data-all", showAll ? "0" : "1");
            renderSentences(it, revealed);
          });
          sents.appendChild(more);
        }
      }

      function show() {
        var it = order[pos];
        head.innerHTML = "<span class=\"game__count\">Link " + (pos + 1) + " of " + order.length + "</span>" +
          "<span class=\"game__link\">" + esc(shortName(it.source)) + " → " + esc(shortName(it.target)) + "</span>" +
          "<span class=\"game__hint\">" + (it.sentences.length > 1 ? it.sentences.length + " sentences" : "1 sentence") +
          " on " + esc(shortName(it.source)) + "’s page " + (it.sentences.length > 1 ? "mention " : "mentions ") +
          esc(shortName(it.target)) + ". What is the relation?</span>";
        sents.setAttribute("data-all", "0");
        renderSentences(it, false);
        buttons.forEach(function (b) { b.disabled = false; b.className = "btn btn--choice"; });
        reveal.innerHTML = "";
        reveal.hidden = true;
        next.hidden = true;
        updateScore();
      }

      // What each instrument's sign says, and whether that fits our label.
      function verdict(x, label) {
        var s = sign(x);
        var reads = s === "neg" ? "negative → reads as enemy" : s === "pos" ? "positive → reads as ally/family" : "zero → no call";
        var ok = null;
        if (label === "enemy") ok = s === "neg";
        else if (label === "ally" || label === "family") ok = s === "pos";
        return { reads: reads, ok: ok, s: s };
      }

      function bar(x) {
        var v = Math.max(-1, Math.min(1, x || 0));
        var w = Math.abs(v) * 50;
        var left = v < 0 ? 50 - w : 50;
        return "<span class=\"meter\" aria-hidden=\"true\"><span class=\"meter__mid\"></span>" +
          "<span class=\"meter__fill meter__fill--" + sign(v) + "\" style=\"left:" + left + "%;width:" + w + "%\"></span></span>";
      }

      function guess(lab) {
        var it = order[pos];
        var first = !seen[it.id];
        seen[it.id] = true;
        buttons.forEach(function (b) {
          b.disabled = true;
          var l = b.getAttribute("data-label");
          if (l === it.label) b.className += " is-answer";
          if (l === lab && l !== it.label) b.className += " is-wrong";
        });
        var right = lab === it.label;
        var rows = [["DistilBERT", it.bert, "bert"], ["VADER", it.vader, "vader"], ["Keyword list", it.kw, "kw"]];
        var html = "<p class=\"game__verdict\">" + (right ? "You matched our label: " : "Our label: ") +
          "<strong class=\"tag\">" + it.label + "</strong>" + (right ? "" : " (you said " + lab + ")") + "</p>";
        html += "<table class=\"instr\"><thead><tr><th scope=\"col\">Instrument</th><th scope=\"col\">Link score</th>" +
          "<th scope=\"col\"><span class=\"visually-hidden\">Scale</span></th><th scope=\"col\">What the sign says</th></tr></thead><tbody>";
        rows.forEach(function (r) {
          var v = verdict(r[1], it.label);
          var mark = v.ok === null ? "<span class=\"instr__na\" title=\"Neutral: no sign is right\">—</span>"
            : v.ok ? "<span class=\"instr__ok\">✓</span>" : "<span class=\"instr__no\">✗</span>";
          html += "<tr><th scope=\"row\">" + r[0] + "</th><td class=\"num\">" + fmt(r[1]) + "</td><td>" + bar(r[1]) +
            "</td><td>" + mark + " " + v.reads + "</td></tr>";
          if (first && v.ok !== null) { tally[r[2]][1] += 1; if (v.ok) tally[r[2]][0] += 1; }
        });
        html += "</tbody></table>";
        if (it.label === "neutral") {
          html += "<p class=\"game__note\">We labeled this link neutral, so no sign is right here. Any confident score is noise.</p>";
        }
        if (it.sentences.length > 1) {
          html += "<p class=\"game__note\">Link score = mean over its " + it.sentences.length + " sentences. Sentence scores are shown above.</p>";
        }
        if (first) { tally.you[1] += 1; if (right) tally.you[0] += 1; }
        reveal.innerHTML = html;
        reveal.hidden = false;
        renderSentences(it, true);
        next.hidden = false;
        updateScore();
        next.focus({ preventScroll: true });
      }

      function updateScore() {
        if (!tally.you[1]) { score.textContent = "Guess to see how you compare with the three instruments."; return; }
        var f = function (t) { return t[0] + "/" + t[1]; };
        score.innerHTML = "<strong>You</strong> matched our label on " + f(tally.you) + " links. On the ally, family and enemy links you saw, the sign was right for " +
          "<strong>DistilBERT</strong> " + f(tally.bert) + " · <strong>VADER</strong> " + f(tally.vader) +
          " · <strong>keywords</strong> " + f(tally.kw) + ".";
      }

      show();
    }).catch(function (e) { fail(stage, e); });
  }

  /* ---------- Figure 2: Network explorer ---------- */

  function initExplorer(box) {
    var stage = box.querySelector(".widget__stage");
    Promise.all([load("network.json")]).then(function (res) {
      var net = res[0];
      var nodes = net.nodes, edges = net.edges;
      var sentPromise = null;
      var sentsByEdge = null;
      function sentences() {
        if (!sentPromise) {
          sentPromise = load("sentences.json").then(function (rows) {
            sentsByEdge = {};
            rows.forEach(function (r) { (sentsByEdge[r[0]] = sentsByEdge[r[0]] || []).push(r); });
            return sentsByEdge;
          });
        }
        return sentPromise;
      }
      sentences(); // start fetching in the background

      // adjacency
      var adj = nodes.map(function () { return []; });
      edges.forEach(function (e, i) { adj[e[0]].push(i); adj[e[1]].push(i); });
      var choices = nodes.map(function (n, i) { return i; }).filter(function (i) {
        return adj[i].some(function (k) { return edges[k][2] !== null; });
      }).sort(function (a, b) { return nodes[a][0].localeCompare(nodes[b][0]); });

      stage.innerHTML = "";
      var controls = el("div", { "class": "explorer__controls" });
      var label = el("label", { "for": "explorer-pick", text: "Character" });
      var select = el("select", { id: "explorer-pick" });
      choices.forEach(function (i) { select.appendChild(el("option", { value: i, text: nodes[i][0] })); });
      var legend = el("div", { "class": "keys", html:
        "<span class=\"key key--neg\">negative link</span><span class=\"key key--pos\">positive link</span>" +
        "<span class=\"key key--none\">no matched sentence</span>" });
      controls.appendChild(label); controls.appendChild(select); controls.appendChild(legend);
      var info = el("p", { "class": "explorer__info" });
      var layout = el("div", { "class": "explorer__layout" });
      var svgBox = el("div", { "class": "explorer__svg" });
      var side = el("div", { "class": "explorer__side" });
      var detail = el("div", { "class": "explorer__detail", "aria-live": "polite" });
      var list = el("ul", { "class": "explorer__list", "aria-label": "Links of this character" });
      side.appendChild(detail); side.appendChild(list);
      layout.appendChild(svgBox); layout.appendChild(side);
      [controls, info, layout].forEach(function (n) { stage.appendChild(n); });

      var current = null, selectedEdge = null, edgeEls = {}, rowEls = {};

      function colorFor(e, T) { return e[2] === null ? T.ink3 : e[2] < 0 ? T.accent : T.pos; }

      function draw(center) {
        current = center;
        var T = theme();
        svgBox.innerHTML = "";
        list.innerHTML = "";
        edgeEls = {}; rowEls = {};
        var SW = 860, SH = 640, CX = SW / 2, CY = SH / 2, R = 240;
        var s = svg("svg", { viewBox: "0 0 " + SW + " " + SH, role: "img",
          "aria-label": "Links of " + nodes[center][0] + "; red lines are negative links, blue lines positive" });
        var defs = svg("defs");
        [["neg", T.accent], ["pos", T.pos], ["none", T.ink3]].forEach(function (m) {
          var mk = svg("marker", { id: "arrow-" + m[0], viewBox: "0 0 10 10", refX: "9", refY: "5",
            markerWidth: "6", markerHeight: "6", orient: "auto-start-reverse" });
          mk.appendChild(svg("path", { d: "M0,1 L10,5 L0,9 z", fill: m[1] }));
          defs.appendChild(mk);
        });
        s.appendChild(defs);

        var nb = {};
        adj[center].forEach(function (k) {
          var e = edges[k], other = e[0] === center ? e[1] : e[0];
          (nb[other] = nb[other] || []).push(k);
        });
        var others = Object.keys(nb).map(Number).sort(function (a, b) {
          var ca = nodes[a][1] === null ? 99 : nodes[a][1], cb = nodes[b][1] === null ? 99 : nodes[b][1];
          return ca - cb || nodes[a][0].localeCompare(nodes[b][0]);
        });
        var pos = {};
        pos[center] = [CX, CY];
        others.forEach(function (o, i) {
          var a = -Math.PI / 2 + (2 * Math.PI * i) / others.length;
          pos[o] = [CX + R * Math.cos(a), CY + R * Math.sin(a), a];
        });
        var showLabels = others.length <= 26;

        var gEdges = svg("g"), gNodes = svg("g"), gLabels = svg("g", { "class": "explorer__labels" });
        others.forEach(function (o) {
          nb[o].forEach(function (k) {
            var e = edges[k];
            var a = pos[e[0]], b = pos[e[1]];
            // bend outgoing and incoming links to opposite sides so both directions stay visible
            var dx = b[0] - a[0], dy = b[1] - a[1], len = Math.sqrt(dx * dx + dy * dy) || 1;
            var bend = 16, nx = -dy / len * bend, ny = dx / len * bend;
            var r0 = e[0] === center ? 15 : 7, r1 = e[1] === center ? 17 : 9;
            var x0 = a[0] + dx / len * r0, y0 = a[1] + dy / len * r0;
            var x1 = b[0] - dx / len * r1, y1 = b[1] - dy / len * r1;
            var d = "M" + x0 + "," + y0 + " Q" + ((x0 + x1) / 2 + nx) + "," + ((y0 + y1) / 2 + ny) + " " + x1 + "," + y1;
            var kind = e[2] === null ? "none" : e[2] < 0 ? "neg" : "pos";
            var g = svg("g", { "class": "edge edge--" + kind, tabindex: "0", role: "button",
              "aria-label": nodes[e[0]][0] + " to " + nodes[e[1]][0] + (e[2] === null ? ", no matched sentence" : ", DistilBERT " + fmt(e[2])) });
            g.appendChild(svg("path", { d: d, "class": "edge__hit" }));
            var p = svg("path", { d: d, "class": "edge__line", stroke: colorFor(e, T), "marker-end": "url(#arrow-" + kind + ")" });
            if (kind === "none") p.setAttribute("stroke-dasharray", "4 4");
            g.appendChild(p);
            g.addEventListener("click", function () { select_(k); });
            g.addEventListener("keydown", function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); select_(k); } });
            g.addEventListener("mouseenter", function () { hoverLabel(o, true); });
            g.addEventListener("mouseleave", function () { hoverLabel(o, false); });
            gEdges.appendChild(g);
            edgeEls[k] = g;
          });
          var p = pos[o];
          gNodes.appendChild(svg("circle", { cx: p[0], cy: p[1], r: 6, fill: T.paper, stroke: T.ink, "stroke-width": 2 }));
          var lx = CX + (R + 12) * Math.cos(p[2]), ly = CY + (R + 12) * Math.sin(p[2]);
          var anchor = Math.cos(p[2]) > 0.2 ? "start" : Math.cos(p[2]) < -0.2 ? "end" : "middle";
          var t = svg("text", { x: lx, y: ly + 4, "text-anchor": anchor, "data-node": o,
            "class": "explorer__label" + (showLabels ? "" : " is-hidden") });
          t.textContent = shortName(nodes[o][0]);
          gLabels.appendChild(t);
        });
        gNodes.appendChild(svg("circle", { cx: CX, cy: CY, r: 13, fill: T.ink }));
        var ct = svg("text", { x: CX, y: CY - 22, "text-anchor": "middle", "class": "explorer__center" });
        ct.textContent = shortName(nodes[center][0]);
        s.appendChild(gEdges); s.appendChild(gNodes); s.appendChild(gLabels); s.appendChild(ct);
        svgBox.appendChild(s);

        // info line
        var c = nodes[center][1];
        var out = adj[center].filter(function (k) { return edges[k][0] === center; });
        var inn = adj[center].filter(function (k) { return edges[k][1] === center; });
        var neg = adj[center].filter(function (k) { return edges[k][2] !== null && edges[k][2] < 0; }).length;
        var scored = adj[center].filter(function (k) { return edges[k][2] !== null; }).length;
        var mates = c === null ? [] : net.communities[c].filter(function (n) { return n !== nodes[center][0]; }).map(shortName);
        info.innerHTML = "<strong>" + esc(shortName(nodes[center][0])) + "</strong>: " + out.length + " links out, " + inn.length +
          " links in; " + neg + " of " + scored + " scored links negative. " +
          (c === null ? "Outside the giant component." : "Louvain community C" + c + ", with " + esc(mates.join(", ")) + ".");

        // list: most negative first; unscored last
        var ks = adj[center].slice().sort(function (a, b) {
          var x = edges[a][2], y = edges[b][2];
          if (x === null) return 1; if (y === null) return -1; return x - y;
        });
        ks.forEach(function (k) {
          var e = edges[k];
          var li = el("li");
          var b = el("button", { type: "button", "class": "explorer__row" });
          var kind = e[2] === null ? "none" : e[2] < 0 ? "neg" : "pos";
          b.innerHTML = "<span class=\"dot dot--" + kind + "\"></span><span class=\"explorer__rowname\">" +
            esc(shortName(nodes[e[0]][0])) + " → " + esc(shortName(nodes[e[1]][0])) + "</span><span class=\"num\">" +
            (e[2] === null ? "–" : fmt(e[2])) + "</span>";
          b.addEventListener("click", function () { select_(k); });
          li.appendChild(b); list.appendChild(li);
          rowEls[k] = b;
        });
        detail.innerHTML = "<p class=\"explorer__prompt\">Click a line, or a row below, to read the sentence behind it.</p>";
        var firstNeg = ks.filter(function (k) { return edges[k][2] !== null; })[0];
        if (firstNeg !== undefined) select_(firstNeg, true);
      }


      function hoverLabel(o, on) {
        var t = svgBox.querySelector("text[data-node=\"" + o + "\"]");
        if (t) t.classList.toggle("is-hover", on);
      }

      function select_(k, quiet) {
        if (selectedEdge !== null && edgeEls[selectedEdge]) {
          edgeEls[selectedEdge].classList.remove("is-selected");
          rowEls[selectedEdge] && rowEls[selectedEdge].classList.remove("is-selected");
        }
        selectedEdge = k;
        edgeEls[k] && edgeEls[k].classList.add("is-selected");
        if (edgeEls[k]) edgeEls[k].parentNode.appendChild(edgeEls[k]); // draw on top
        rowEls[k] && rowEls[k].classList.add("is-selected");
        var e = edges[k];
        var other = e[0] === current ? e[1] : e[0];
        svgBox.querySelectorAll(".explorer__label.is-active").forEach(function (t) { t.classList.remove("is-active"); });
        var lab = svgBox.querySelector("text[data-node=\"" + other + "\"]");
        if (lab) lab.classList.add("is-active");
        var head = "<p class=\"explorer__title\">" + esc(shortName(nodes[e[0]][0])) + " → " + esc(shortName(nodes[e[1]][0])) + "</p>";
        if (e[2] === null) {
          detail.innerHTML = head + "<p class=\"explorer__prompt\">No sentence on " + esc(shortName(nodes[e[0]][0])) +
            "'s page matched this link, so it has no score.</p>";
          return;
        }
        detail.innerHTML = head + "<p class=\"explorer__scores\">Link score (mean of " + e[5] + " sentence" + (e[5] > 1 ? "s" : "") +
          "): DistilBERT <strong>" + fmt(e[2]) + "</strong> · VADER " + fmt(e[3]) + " · keywords " + fmt(e[4]) + "</p>" +
          "<p class=\"explorer__prompt\">Loading sentences…</p>";
        sentences().then(function (by) {
          if (selectedEdge !== k) return;
          var rows = by[k] || [];
          var html = head + detail.querySelector(".explorer__scores").outerHTML;
          rows.forEach(function (r) {
            html += "<blockquote class=\"explorer__quote\"><p>“" + esc(r[1]) + "”</p><p class=\"game__sentscore\">DistilBERT " +
              fmt(r[2]) + " · VADER " + fmt(r[3]) + " · keywords " + fmt(r[4], 0) + "</p></blockquote>";
          });
          detail.innerHTML = html;
          if (!quiet && window.innerWidth < 760) detail.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
        }).catch(function (err) { detail.innerHTML = head + "<p class=\"widget__error\">" + esc(err.message) + "</p>"; });
      }

      select.addEventListener("change", function () { draw(Number(select.value)); });
      var start = choices.filter(function (i) { return nodes[i][0] === "Hercules (Marvel Comics)"; })[0];
      if (start === undefined) start = choices[0];
      select.value = start;
      draw(start);
      onTheme(function () { var k = selectedEdge; draw(current); if (k !== null) select_(k, true); });
    }).catch(function (e) { fail(stage, e); });
  }

  /* ---------- Figure 3: the null model, animated ---------- */

  function initNull(box) {
    var stage = box.querySelector(".widget__stage");
    load("null.json").then(function (D) {
      stage.innerHTML = "";
      var controls = el("div", { "class": "nullsim__controls" });
      var run = el("button", { "class": "btn btn--primary", type: "button", text: "Run " + D.n_perm.toLocaleString("en") + " shuffles" });
      var skip = el("button", { "class": "btn", type: "button", text: "Skip to the end" });
      var counter = el("span", { "class": "nullsim__counter", "aria-live": "polite" });
      controls.appendChild(run); controls.appendChild(skip); controls.appendChild(counter);
      var chart = el("div", { "class": "nullsim__chart" });
      stage.appendChild(controls); stage.appendChild(chart);

      var W = 760, H = 400, m = { l: 52, r: 18, t: 54, b: 70 };
      var X0 = -9, X1 = 9;
      var step = D.step * 100;
      var vals = D.null.map(function (v) { return v * 100; });
      var lo = Math.min.apply(null, vals) - step / 2;
      var edges = [];
      for (var x = lo; x <= Math.max.apply(null, vals) + step; x += 2 * step) edges.push(x);
      var counts = new Array(edges.length).fill(0);
      var finalCounts = new Array(edges.length).fill(0);
      function binOf(v) { return Math.min(edges.length - 1, Math.floor((v - lo) / (2 * step))); }
      vals.forEach(function (v) { finalCounts[binOf(v)] += 1; });
      var yMax = Math.ceil(Math.max.apply(null, finalCounts) / 20) * 20;
      var obs = D.observed * 100;
      var sx = function (v) { return m.l + (v - X0) / (X1 - X0) * (W - m.l - m.r); };
      var sy = function (c) { return H - m.b - c / yMax * (H - m.t - m.b); };

      var T, s, bars = [], done = 0, raf = null, finished = false;

      function frame() {
        T = theme();
        chart.innerHTML = "";
        s = svg("svg", { viewBox: "0 0 " + W + " " + H, role: "img",
          "aria-label": "Histogram of the difference between and within communities under shuffled signs" });
        // grid + y axis
        for (var g = 0; g <= yMax; g += 20) {
          s.appendChild(svg("line", { x1: m.l, x2: W - m.r, y1: sy(g), y2: sy(g), stroke: T.paper2, "stroke-width": 1 }));
          var ty = svg("text", { x: m.l - 8, y: sy(g) + 4, "text-anchor": "end", "class": "axis" }); ty.textContent = g; s.appendChild(ty);
        }
        var yl = svg("text", { x: 14, y: (m.t + H - m.b) / 2, transform: "rotate(-90 14 " + (m.t + H - m.b) / 2 + ")",
          "text-anchor": "middle", "class": "axis" });
        yl.textContent = "shuffles"; s.appendChild(yl);
        // x axis
        s.appendChild(svg("line", { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, stroke: T.ink, "stroke-width": 1.5 }));
        for (var t = -8; t <= 8; t += 2) {
          var tx = svg("text", { x: sx(t), y: H - m.b + 20, "text-anchor": "middle", "class": "axis" });
          tx.textContent = (t > 0 ? "+" : t < 0 ? "−" : "") + Math.abs(t); s.appendChild(tx);
        }
        var xl = svg("text", { x: (m.l + W - m.r) / 2, y: H - 14, "text-anchor": "middle", "class": "axis axis--title" });
        xl.textContent = "Δ = share negative between − share negative within (percentage points)"; s.appendChild(xl);
        bars = edges.map(function (e0) {
          var r = svg("rect", { x: sx(e0) + 1, width: Math.max(1, sx(e0 + 2 * step) - sx(e0) - 2), y: sy(0), height: 0,
            fill: e0 + step >= obs ? T.ink2 : T.ink3, opacity: 0.9 });
          s.appendChild(r); return r;
        });
        var note = svg("text", { x: m.l + 6, y: m.t - 24, "class": "nullsim__note" });
        note.textContent = "Signs shuffled across " + D.n_links.toLocaleString("en") + " links; network and communities fixed";
        s.appendChild(note);
        chart.appendChild(s);
        paint();
        if (finished) drawObserved();
      }

      function paint() {
        bars.forEach(function (r, i) {
          r.setAttribute("y", sy(counts[i]));
          r.setAttribute("height", sy(0) - sy(counts[i]));
        });
        counter.textContent = done ? "shuffle " + done.toLocaleString("en") + " of " + D.n_perm.toLocaleString("en") : "";
      }

      function drawObserved() {
        var g = svg("g", { "class": "nullsim__obs" });
        g.appendChild(svg("line", { x1: sx(obs), x2: sx(obs), y1: m.t - 6, y2: H - m.b, stroke: T.accent, "stroke-width": 3 }));
        var lab = svg("text", { x: sx(obs) + 8, y: m.t + 10, "class": "nullsim__obslabel" });
        lab.textContent = "observed Δ = " + fmt(obs, 1) + " pts";
        var lab2 = svg("text", { x: sx(obs) + 8, y: m.t + 30, "class": "nullsim__obsstat" });
        lab2.textContent = "z = " + D.z.toFixed(2) + " · one-sided p = " + D.p_one.toFixed(2);
        g.appendChild(lab); g.appendChild(lab2);
        // Louvain-seed rug
        var ry = H - m.b + 34;
        D.seeds.forEach(function (v) {
          g.appendChild(svg("line", { x1: sx(v * 100), x2: sx(v * 100), y1: ry - 7, y2: ry + 7, stroke: T.ink, "stroke-width": 1.6 }));
        });
        var rl = svg("text", { x: sx(Math.min.apply(null, D.seeds) * 100) - 8, y: ry + 4, "text-anchor": "end", "class": "axis" });
        rl.textContent = "observed Δ, 20 Louvain seeds";
        g.appendChild(rl);
        s.appendChild(g);
        // keep the x-axis title clear of the rug
        s.querySelector(".axis--title").setAttribute("y", H - 4);
      }

      function finish() {
        if (raf) cancelAnimationFrame(raf);
        raf = null;
        counts = finalCounts.slice(); done = vals.length; finished = true;
        frame();
        counter.textContent = "All " + D.n_perm.toLocaleString("en") + " shuffles done. Our real Δ is the red line.";
        run.textContent = "Replay";
      }

      function start() {
        if (reduceMotion) { finish(); return; }
        if (raf) cancelAnimationFrame(raf);
        counts = new Array(edges.length).fill(0); done = 0; finished = false;
        frame();
        var t0 = null, dur = 4200;
        function tick(ts) {
          if (t0 === null) t0 = ts;
          var p = Math.min(1, (ts - t0) / dur);
          var target = Math.round(vals.length * (p * p * (3 - 2 * p)));
          while (done < target) { counts[binOf(vals[done])] += 1; done += 1; }
          paint();
          if (p < 1) raf = requestAnimationFrame(tick); else finish();
        }
        raf = requestAnimationFrame(tick);
      }

      run.addEventListener("click", start);
      skip.addEventListener("click", finish);
      onTheme(frame);
      frame();
      counter.textContent = "Press run: each shuffle randomly reassigns the signs and adds one Δ to the histogram.";
    }).catch(function (e) { fail(stage, e); });
  }

  /* ---------- Figure 4: DistilBERT vs VADER, sentence by sentence ---------- */

  function initDisagree(box) {
    var stage = box.querySelector(".widget__stage");
    if (!window.Plotly) { fail(stage, new Error("plotly did not load")); return; }
    Promise.all([load("sentences.json"), load("network.json")]).then(function (res) {
      var rows = res[0], net = res[1];
      stage.innerHTML = "";
      var div = el("div", { "class": "disagree__plot" });
      stage.appendChild(div);
      var wrap = function (s) {
        var t = s.length > 240 ? s.slice(0, 237) + "…" : s, out = [], line = "";
        esc(t).split(" ").forEach(function (w) {
          if ((line + " " + w).length > 58) { out.push(line); line = w; } else line = line ? line + " " + w : w;
        });
        out.push(line);
        return out.join("<br>");
      };
      var groups = { same: { x: [], y: [], t: [] }, opp: { x: [], y: [], t: [] }, zero: { x: [], y: [], t: [] } };
      rows.forEach(function (r) {
        var e = net.edges[r[0]];
        var key = r[3] === 0 ? "zero" : (r[2] > 0) === (r[3] > 0) ? "same" : "opp";
        var g = groups[key];
        g.x.push(r[2]); g.y.push(r[3]);
        g.t.push("<b>" + esc(net.nodes[e[0]][0]) + " → " + esc(net.nodes[e[1]][0]) + "</b><br>" + wrap(r[1]) +
          "<br><i>DistilBERT " + fmt(r[2]) + " · VADER " + fmt(r[3]) + "</i>");
      });

      function render() {
        var T = theme();
        var font = "'Source Serif 4', Georgia, serif";
        var tr = function (g, name, color, op) {
          return { type: "scattergl", mode: "markers", name: name, x: g.x, y: g.y, text: g.t,
            hovertemplate: "%{text}<extra></extra>",
            marker: { size: 6, color: color, opacity: op } };
        };
        var data = [
          tr(groups.same, "same sign", T.pos, 0.35),
          tr(groups.opp, "opposite signs", T.accent, 0.55),
          tr(groups.zero, "VADER exactly 0", T.ink3, 0.35)
        ];
        var shade = function (x0, x1, y0, y1) {
          return { type: "rect", xref: "x", yref: "y", x0: x0, x1: x1, y0: y0, y1: y1, fillcolor: T.paper2, line: { width: 0 }, layer: "below" };
        };
        var small = window.innerWidth < 600;
        var layout = {
          paper_bgcolor: T.paper, plot_bgcolor: T.paper,
          font: { family: font, color: T.ink, size: small ? 12 : 13 },
          margin: { l: 56, r: 12, t: 16, b: small ? 96 : 76 },
          xaxis: { title: { text: "DistilBERT score (−1 … +1)" }, range: [-1.08, 1.08], zeroline: true, zerolinecolor: T.ink2,
            gridcolor: T.paper2, tickfont: { color: T.ink2 }, fixedrange: small },
          yaxis: { title: { text: "VADER compound (−1 … +1)" }, range: [-1.08, 1.08], zeroline: true, zerolinecolor: T.ink2,
            gridcolor: T.paper2, tickfont: { color: T.ink2 }, fixedrange: small },
          shapes: [shade(0, 1.08, -1.08, 0), shade(-1.08, 0, 0, 1.08)],
          annotations: [
            { x: 0.98, y: -1.0, xref: "x", yref: "y", xanchor: "right", showarrow: false, text: "DistilBERT +, VADER −",
              font: { family: "Oswald, sans-serif", size: 12, color: T.ink2 } },
            { x: -0.98, y: 1.0, xref: "x", yref: "y", xanchor: "left", showarrow: false, text: "DistilBERT −, VADER +",
              font: { family: "Oswald, sans-serif", size: 12, color: T.ink2 } }
          ],
          legend: { orientation: "h", x: 0, y: small ? -0.28 : -0.2, font: { color: T.ink } },
          hoverlabel: { bgcolor: T.paper, bordercolor: T.ink, font: { family: font, size: 12, color: T.ink }, align: "left" },
          dragmode: small ? false : "zoom"
        };
        Plotly.react(div, data, layout, { displaylogo: false, responsive: true,
          modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d"] });
      }
      render();
      onTheme(render);
    }).catch(function (e) { fail(stage, e); });
  }

  /* ---------- boot ---------- */

  var inits = { game: initGame, explorer: initExplorer, nullsim: initNull, disagree: initDisagree };
  Object.keys(inits).forEach(function (id) {
    var box = document.getElementById(id);
    if (box) whenNear(box, function () { inits[id](box); });
  });
})();
