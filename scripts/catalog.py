"""Turn the two public Research lists into papers and weighted, undirected graphs."""

import hashlib
import itertools
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from math import log1p

import bibtexparser
import networkx as nx
from bibtexparser.bparser import BibTexParser
from bibtexparser.latexenc import latex_to_unicode
from bs4 import BeautifulSoup, Comment

FOCUS = "kwan-young-bak"
FOCUS_NAME = "Kwan-Young Bak"
HSSC = "10.1057/s41599-026-08463-7"
PLACEHOLDER = re.compile(r"\b(?:\d+\s+more\s+authors?|et\s+al\.?|others)\b", re.I)
REPORT_OR_RELEASE = re.compile(
    r"\((?:(?:research|technical)\s+report|report|book|software|package release|preprint)\)\s*$",
    re.I,
)
NON_VENUE = re.compile(
    r"\b(?:arxiv|biorxiv|medrxiv|preprints?|technical report|research report|"
    r"CRAN|PyPI|GPRN|ISBN|comprehensive r archive network|python package index)\b",
    re.I,
)
MORE_LITERAL = re.compile(
    r"""(?:==|===)\s*['"]\d+\s+more\s+authors?['"]\s*\?\s*"""
    r"""(?P<value>'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")\s*:""", re.I,
)
HEADING = re.compile(r"^h[1-6]$")


def tidy(value):
    return " ".join(unicodedata.normalize("NFC", value).split())


def bib_text(value):
    value = latex_to_unicode(value)
    if "<" in value or "&" in value:
        markup = BeautifulSoup(value, "html.parser")
        for tag in markup.find_all(["sub", "sup"]):
            digits = "₀₁₂₃₄₅₆₇₈₉" if tag.name == "sub" else "⁰¹²³⁴⁵⁶⁷⁸⁹"
            tag.replace_with(tag.get_text().translate(str.maketrans("0123456789", digits)))
        value = markup.get_text()
    return tidy(value)


def name_key(name):
    return "-".join(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", name).casefold()))


def person(raw):
    if not raw.strip() or PLACEHOLDER.search(raw):
        raise ValueError(f"Incomplete public author list: {raw!r}")
    parts = [tidy(part) for part in raw.split(",")]
    # BibTeX allows both 'family, given' and 'family, suffix, given'.
    name = tidy(" ".join([parts[-1], *parts[:-1]])) if len(parts) > 1 else parts[0]
    if not name_key(name):
        raise ValueError(f"Missing author name in {raw!r}")
    key = name_key(name)
    return {"id": FOCUS if key == "kwanyoung-park" else key, "name": name}


def doi_from(entry):
    for field in ("doi", "url"):
        value = entry.get(field, "").strip()
        if field == "url" and not re.match(r"https?://(?:dx\.)?doi\.org/", value, re.I):
            continue
        value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value, flags=re.I)
        if re.fullmatch(r"10\.\d{4,9}/\S+", value, re.I):
            return value.casefold()
    return ""


@dataclass
class Record:
    title: str
    venue: str
    authors: list
    status: str
    doi: str = ""
    rank: int = 0

    @property
    def signature(self):
        title = "".join(c for c in unicodedata.normalize("NFKC", self.title).casefold() if c.isalnum())
        authors = sorted({author["id"] for author in self.authors})
        return json.dumps([title, authors], ensure_ascii=False)


def published_records(bib):
    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    entries = bibtexparser.loads(bib, parser=parser).entries
    # Some BibTeX parsers skip unreadable records. Include repeated keys in this check.
    headers = re.findall(r"^\s*@([\w-]+)\s*[{(]", bib, re.M)
    expected = sum(tag.lower() not in {"comment", "string", "preamble"} for tag in headers)
    if not expected or len(entries) != expected:
        raise ValueError(f"Parsed {len(entries)} of {expected} bibliography entries")
    records = []
    for entry in entries:
        state = " ".join(entry.get(k, "") for k in ("pubstate", "status", "note"))
        formal = re.search(r"\b(?:in press|accepted|forthcoming|online[ -]first|published)\b", state, re.I)
        kind = entry["ENTRYTYPE"].lower()
        if kind not in {"article", "inproceedings", "conference"} and not (
            kind in {"misc", "unpublished"} and formal and (entry.get("journal") or entry.get("booktitle"))
        ):
            continue
        if re.search(r"\b(?:not (?:yet )?accepted|withdrawn|rejected)\b", state, re.I):
            continue
        if not formal and re.search(r"\b(?:under review|in preparation|submitted|preprint)\b", state, re.I):
            continue
        title = bib_text(entry.get("title", ""))
        venue = bib_text(entry.get("journal") or entry.get("booktitle", ""))
        subtype = (entry.get("entrysubtype") or entry.get("type", "")).casefold()
        if subtype in {"book", "report", "research report", "technical report", "software", "preprint"}:
            continue
        if REPORT_OR_RELEASE.search(title) or NON_VENUE.search(venue):
            continue
        doi = doi_from(entry)
        if not venue and ("arxiv" in entry.get("archiveprefix", "").lower() or "eprint" in entry
                          or doi.startswith("10.48550/arxiv.") or "arxiv.org/" in entry.get("url", "").lower()):
            continue
        if not (title and venue and entry.get("author")):
            raise ValueError(f"Missing title, venue or author in {entry['ID']}")
        authors = [person(bib_text(name)) for name in re.split(r"\s+and\s+", entry["author"], flags=re.I)]
        # The brief gives this byline spelling for this exact person, work and position.
        if doi == HSSC and len(authors) >= 5 and authors[4]["id"] == FOCUS:
            authors[4]["name"] = "Kwanyoung Park"
        rank = 1 + sum(bool(entry.get(field)) for field in ("volume", "number", "pages"))
        if re.search(r"\b(?:online[ -]first|published)\b", state, re.I):
            rank += 1
        records.append(Record(title, venue, authors, "accepted", doi, rank))
    return records


def split_byline(text):
    return [v for v in re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+", tidy(text)) if v]


def ongoing_records(markdown):
    soup = BeautifulSoup(markdown, "html.parser")
    for tag in soup.select("script, style, template, [hidden], [aria-hidden=true]"):
        tag.decompose()
    for tag in soup.find_all(style=re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.I)):
        tag.decompose()
    headings = soup.find_all(HEADING)
    heading = next((h for h in headings if tidy(h.get_text()).casefold() == "work in progress"), None)
    if heading is None:
        raise ValueError("Public Work in Progress heading missing")
    # The current Selected Publications page renders the complete bibliography.
    # Fail closed if the lab changes to a filtered query that we do not understand.
    selected = next((h for h in headings if tidy(h.get_text()).casefold() == "selected publications"), None)
    directives = soup.find_all(string=re.compile(r"^\s*{%\s*bibliography\s*%}\s*$"))
    if selected is None or not any(
        not isinstance(s, Comment) and s.find_parent(class_="publications")
        and s.find_previous(HEADING) is selected for s in directives
    ):
        raise ValueError("Public Selected Publications bibliography directive changed")

    records = []
    saw_list = False
    for tag in heading.find_all_next(True):
        if HEADING.fullmatch(tag.name) and int(tag.name[1]) <= int(heading.name[1]):
            break
        if tag.name in {"ol", "ul"} and "bibliography" in tag.get("class", []):
            saw_list = True
            if tag.get_text(strip=True) and not tag.select_one(".row"):
                raise ValueError("Unrecognized Work in Progress entries")
            if any(t.find_parent(class_="row") is None for t in tag.select(".title, .author")):
                raise ValueError("Work in Progress entry is outside its row")
        if "row" not in tag.get("class", []) or not tag.find_parent(class_="bibliography"):
            continue
        title_tag, byline = tag.select_one(".title"), tag.select_one(".author")
        if title_tag is None or byline is None:
            raise ValueError("Work in Progress row missing its public title or byline")
        title = tidy(title_tag.get_text(" ", strip=True))
        if not title:
            raise ValueError("Empty Work in Progress title")
        if REPORT_OR_RELEASE.search(title):
            continue
        for span in byline.select(".more-authors"):
            count = re.fullmatch(r"(\d+)\s+more\s+authors?", tidy(span.get_text()), re.I)
            match = MORE_LITERAL.search(span.get("onclick", ""))
            if not count or not match:
                raise ValueError(f"Cannot read collapsed byline for {title}")
            names = re.sub(r"""\\(['"\\])""", r"\1", match["value"][1:-1])
            if len(split_byline(names)) != int(count[1]):
                raise ValueError(f"Collapsed author count differs for {title}")
            span.replace_with(names)
        names = split_byline(byline.get_text(" ", strip=True))
        if not names:
            raise ValueError(f"Missing authors for {title}")
        records.append(Record(title, "Ongoing", [person(name) for name in names], "ongoing"))
    if not saw_list:
        raise ValueError("Public Work in Progress list missing")
    return records


def unique_papers(records):
    records = [r for r in records if any(a["id"] == FOCUS for a in r.authors)]
    known_dois = defaultdict(set)
    for record in records:
        if record.doi:
            known_dois[record.signature].add(record.doi)
    papers = {}
    for record in records:
        signature = record.signature
        fingerprint = hashlib.sha256(signature.encode()).hexdigest()[:24]
        matches = known_dois[signature]
        if not record.doi and len(matches) > 1:
            raise ValueError(f"Ambiguous DOI for {record.title}")
        doi = record.doi or next(iter(matches), "")
        key = "doi:" + doi if doi else "work:" + fingerprint
        if key not in papers or record.rank > papers[key][0]:
            papers[key] = (record.rank, {
                "id": key, "signature": fingerprint, "title": record.title, "venue": record.venue,
                "authors": record.authors, "status": record.status,
            })
    return [paper for _, paper in papers.values()]


def graph(papers):
    counts, edges = Counter(), defaultdict(list)
    for paper in papers:
        people = sorted({author["id"] for author in paper["authors"]})
        counts.update(people)
        for pair in itertools.combinations(people, 2):
            edges[pair].append(paper["id"])
    return {
        "papers": [p["id"] for p in papers], "nodes": dict(sorted(counts.items())),
        "edges": [{"a": a, "b": b, "papers": ids} for (a, b), ids in sorted(edges.items())],
    }


def initial_layout(mode):
    if len(mode["nodes"]) == 1:
        return {FOCUS: [0, 0]}
    graph = nx.Graph()
    graph.add_nodes_from(mode["nodes"])
    for edge in mode["edges"]:
        graph.add_edge(edge["a"], edge["b"], weight=1 + log1p(len(edge["papers"])))
    points = nx.spring_layout(graph, seed=17, iterations=280, k=1.3 / len(graph) ** .5)
    points = {key: xy - points[FOCUS] for key, xy in points.items()}
    bounds = [max(abs(xy[i]) for xy in points.values()) or 1 for i in (0, 1)]
    return {key: [round(float(xy[i]) / bounds[i], 5) for i in (0, 1)] for key, xy in points.items()}


def catalog(bib, markdown):
    published = published_records(bib)
    ongoing = ongoing_records(markdown)
    papers = unique_papers(published + ongoing)
    accepted = graph([p for p in papers if p["status"] == "accepted"])
    if not accepted["papers"]:
        raise ValueError("No accepted papers for Kwan-Young Bak in the public bibliography")
    total = graph(papers)
    people = {a["id"]: a["name"] for p in reversed(papers) for a in p["authors"]}
    people[FOCUS] = FOCUS_NAME
    return {"focus": FOCUS, "people": people, "papers": papers,
            "modes": {"accepted": accepted, "ongoing": total}, "layout": initial_layout(total)}
