import itertools
import unittest

from scripts.build import REFERENCE, read_sources
from scripts.catalog import (
    FOCUS, HSSC, Record, catalog, graph, ongoing_records, person, published_records, unique_papers,
)


def research_page(rows):
    return (
        '<h3>Selected Publications</h3><div class="publications">{% bibliography %}</div>'
        '<h3>Work in Progress</h3><div class="publications"><ol class="bibliography">'
        + rows + '</ol></div>'
    )


def row(title, authors):
    return f'<li class="row"><div class="title">{title}</div><div class="author">{authors}</div></li>'


class CatalogRules(unittest.TestCase):
    def test_same_bib_key_preserves_distinct_records(self):
        bib = """
        @article{dup, title={One}, author={Bak, Kwan-Young}, journal={Journal A}}
        @article{dup, title={Two}, author={Park, Kwanyoung}, journal={Journal B}}
        """
        papers = unique_papers(published_records(bib))
        self.assertEqual([p["title"] for p in papers], ["One", "Two"])
        self.assertEqual(graph(papers)["nodes"], {FOCUS: 2})
        self.assertEqual(graph(papers)["edges"], [])

    def test_preprint_ongoing_acceptance_online_and_final_count_once(self):
        bib = """
        @article{pre, title={A study}, author={Kwanyoung Park and Woojoo Lee}, journal={arXiv preprint}}
        @inproceedings{acc, title={A Study}, author={Lee, Woojoo and Bak, Kwan-Young},
            booktitle={Annual Conference}, pubstate={in press}, doi={10.1234/TEST}}
        @article{online, title={Final title}, author={Kwan-Young Bak and Woojoo Lee},
            journal={Journal A}, pubstate={online first}, url={https://doi.org/10.1234/test}}
        @article{final, title={Final title}, author={Park, Kwanyoung and Woojoo Lee},
            journal={Journal A}, volume={4}, pages={10--20}, doi={doi:10.1234/test}}
        """
        page = research_page(row("A study!", "Kwanyoung Park, Woojoo Lee"))
        data = catalog(bib, page)
        for view in data["modes"].values():
            self.assertEqual(view["papers"], ["doi:10.1234/test"])
            self.assertEqual(view["edges"][0]["papers"], view["papers"])
        self.assertEqual(data["papers"][0]["title"], "Final title")
        self.assertEqual(data["people"][FOCUS], "Kwan-Young Bak")
        self.assertEqual(data["papers"][0]["authors"][0]["name"], "Kwanyoung Park")

    def test_fallback_dedup_population_and_unique_unordered_pairs(self):
        people = [person(name) for name in ("Park, Kwanyoung", "A One", "B Two", "Bak, Kwan-Young")]
        a = Record("Same: title", "Journal", people, "accepted", rank=1)
        b = Record("Same title", "Ongoing", people[::-1], "ongoing")
        other = Record("Other paper", "Journal", people[1:3], "accepted", rank=1)
        papers = unique_papers([a, b, other, a])
        self.assertEqual(len(papers), 1)
        view = graph(papers)
        self.assertEqual(set(view["nodes"].values()), {1})
        self.assertEqual(len(view["edges"]), 3)

    def test_eligibility_uses_type_venue_status_and_work_type(self):
        entries = [
            ("book", "Monograph", "Publisher"), ("techreport", "Report", "Department"),
            ("article", "Data (Research Report)", "Ministry"),
            ("article", "Source", "PyPI"), ("article", "Source", "CRAN"),
            ("article", "Notes", "arXiv:1234.56789"),
            ("article", "Package paper", "The R Journal"),
            ("inproceedings", "Conference paper", "AAAI"),
        ]
        bib = "\n".join(
            f"@{kind}{{s{i}, title={{{title}}}, author={{Kwan-Young Bak}}, "
            f"{'booktitle' if kind == 'inproceedings' else 'journal'}={{{venue}}}}}"
            for i, (kind, title, venue) in enumerate(entries)
        )
        bib += "\n@article{sub, title={Pending}, journal={Journal A}, author={Bak, Kwan-Young}, status={under review}}"
        bib += "\n@article{e, title={Accepted work}, journal={SoftwareX}, author={Kwan-Young Bak}, archiveprefix={arXiv}, eprint={1234.56789}}"
        self.assertEqual([r.title for r in published_records(bib)], ["Package paper", "Conference paper", "Accepted work"])

    def test_only_visible_rows_in_work_in_progress_are_read(self):
        repeated = row("Outside", "A Person")
        hidden = '<span class="more-authors" onclick="var x = t == \'2 more authors\' ? \'B Two, C Three\' : \'2 more authors\';">2 more authors</span>'
        page = research_page(row("Only one", "Kwan-Young Bak, and " + hidden)
                             + "<!--" + repeated + "--><div hidden>" + repeated + "</div>")
        records = ongoing_records(page + "<h3>Other projects</h3><ol class='bibliography'>" + repeated + "</ol>")
        self.assertEqual([r.title for r in records], ["Only one"])
        self.assertEqual([a["name"] for a in records[0].authors], ["Kwan-Young Bak", "B Two", "C Three"])
        self.assertEqual(ongoing_records(research_page("")), [])

    def test_incomplete_inputs_stop_the_build(self):
        for byline in ("A One, et al.", "A One and 1 more author", '<span class="more-authors">1 more author</span>'):
            with self.subTest(byline=byline), self.assertRaises(ValueError):
                ongoing_records(research_page(row("Test", byline)))
        for invalid in ("", research_page("").replace("{% bibliography %}", "{% bibliography --query @*[selected=true] %}"),
                        research_page("<li>A new row format</li>")):
            with self.subTest(page=invalid), self.assertRaises(ValueError):
                ongoing_records(invalid)
        with self.assertRaises(ValueError):
            published_records("@article{one, author={Kwan-Young Bak}, title={Unclosed ")


class PublicSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.bib, cls.markdown = read_sources(REFERENCE)
        cls.data = catalog(cls.bib, cls.markdown)
        cls.papers = {p["id"]: p for p in cls.data["papers"]}

    def test_real_counts_and_pair_weights(self):
        for mode, (papers, people, edges, bak_lee, yu_lee) in {
            "accepted": (39, 60, 222, 3, 1), "ongoing": (56, 70, 280, 7, 2),
        }.items():
            view = self.data["modes"][mode]
            self.assertEqual((len(set(view["papers"])), len(view["nodes"]), len(view["edges"])), (papers, people, edges))
            weights = {(e["a"], e["b"]): len(e["papers"]) for e in view["edges"]}
            self.assertEqual(weights[(FOCUS, "woojoo-lee")], bak_lee)
            self.assertEqual(weights[("jiwoong-yu", "woojoo-lee")], yu_lee)
            self.assertEqual(view["nodes"][FOCUS], papers)
            for edge in view["edges"]:
                self.assertLess(edge["a"], edge["b"])
                self.assertEqual(len(edge["papers"]), len(set(edge["papers"])))
                self.assertTrue(set(edge["papers"]).issubset(view["papers"]))

    def test_hssc_byline_and_every_contributed_edge(self):
        paper = self.papers["doi:" + HSSC]
        self.assertEqual(paper["authors"][4], {"id": FOCUS, "name": "Kwanyoung Park"})
        ids = {a["id"] for a in paper["authors"]}
        self.assertEqual(len(ids), 6)
        for mode in self.data["modes"].values():
            pairs = [(e["a"], e["b"]) for e in mode["edges"] if paper["id"] in e["papers"]]
            self.assertEqual(pairs, list(itertools.combinations(sorted(ids), 2)))
            self.assertNotIn("kwanyoung-park", mode["nodes"])

    def test_real_inclusions_and_exclusions(self):
        self.assertEqual(len(published_records(self.bib)), 39)
        self.assertEqual(len(ongoing_records(self.markdown)), 17)
        titles = {p["title"]: p for p in self.papers.values()}
        for text in ("Minimax optimality", "Adaptive smoothing of spherical trajectories", "ALTBI"):
            match, = [p for title, p in titles.items() if title.startswith(text)]
            self.assertEqual(match["status"], "accepted")
        altbi = next(p for p in titles.values() if p["title"].startswith("ALTBI"))
        self.assertIn("AAAI", altbi["venue"])
        fastkrr, = [p for t, p in titles.items() if t.startswith("FastKRR")]
        self.assertEqual(fastkrr["venue"], "Ongoing")
        self.assertEqual(fastkrr["authors"][4]["id"], FOCUS)
        self.assertTrue(all("2605.22030" not in p["venue"] and "(Technical Report)" not in p["title"] for p in titles.values()))
        single = titles["A feature space need not be the RKHS of its kernel"]
        self.assertEqual(len(single["authors"]), 1)
        self.assertFalse(any(single["id"] in e["papers"] for e in self.data["modes"]["ongoing"]["edges"]))


if __name__ == "__main__":
    unittest.main()
