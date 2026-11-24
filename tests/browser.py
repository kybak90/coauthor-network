"""Exercise the built Pages artifact in Chromium, or a deployed URL with --url."""

import argparse
import json
import mimetypes
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

DIST = Path(__file__).resolve().parents[1] / "dist"
LOCAL = "https://coauthor.test/coauthor-network/"


def artifact(route):
    # Serve the exact artifact at a project-site subpath without a listening server.
    relative = urlsplit(route.request.url).path.removeprefix("/coauthor-network/")
    path = DIST / (relative or "index.html")
    if not path.is_file() or DIST not in path.resolve().parents:
        route.fulfill(status=404)
        return
    route.fulfill(path=path, content_type=mimetypes.guess_type(path)[0] or "application/octet-stream")


def switch(page, mode):
    name = "Accepted & Published" if mode == "accepted" else "Include Ongoing"
    page.get_by_text(name, exact=True).click()
    expect(page.get_by_role("radio", name=name)).to_be_checked()


def check_view(page, view):
    expect(page.locator("#rows tr")).to_have_count(len(view["papers"]))
    expect(page.locator("#nodes .node")).to_have_count(len(view["nodes"]))
    expect(page.locator("#edges .edge")).to_have_count(len(view["edges"]))
    expect(page.locator("#paper-count")).to_have_text(str(len(view["papers"])))


def click_edge(page, key):
    # Click an exposed point on the actual visible edge, avoiding intersecting edges.
    point = page.locator("[data-edge=" + json.dumps(key) + "] .line").evaluate("""line => {
        const rect = line.ownerSVGElement.getBoundingClientRect();
        const coord = k => Number(line.getAttribute(k));
        for (let i = 2; i < 99; i++) {
            const t = i / 100;
            const x = rect.x + coord('x1') * (1-t) + coord('x2') * t;
            const y = rect.y + coord('y1') * (1-t) + coord('y2') * t;
            if (document.elementFromPoint(x,y)?.closest('[data-edge]') === line.parentElement) return {x,y};
        }
    }""")
    if point:
        page.mouse.click(point["x"], point["y"])
    else:
        page.locator("[data-edge=" + json.dumps(key) + "]").press("Enter")


def exercise(page, url, screenshot=None, mobile_screenshot=None):
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(url)
    expect(page.locator("#nodes .node").first).to_be_visible(timeout=30_000)
    page.evaluate("document.fonts.ready")
    data = page.evaluate("""async () => {
        const manifest = await (await fetch('./version.json', {cache:'no-store'})).json();
        return (await fetch('./data-' + manifest.version + '.json')).json();
    }""")
    accepted, ongoing = data["modes"]["accepted"], data["modes"]["ongoing"]
    expect(page.locator(".modes label")).to_have_text(["Include Ongoing", "Accepted & Published"])
    expect(page.get_by_role("radio", name="Include Ongoing")).to_be_checked()
    check_view(page, ongoing)
    if screenshot:
        page.screenshot(path=screenshot)

    switch(page, "accepted")
    page.reload()
    expect(page.get_by_role("radio", name="Accepted & Published")).to_be_checked()
    check_view(page, accepted)
    page.goto("about:blank")
    page.goto(url)
    expect(page.get_by_role("radio", name="Include Ongoing")).to_be_checked()
    check_view(page, ongoing)
    switch(page, "accepted")
    check_view(page, accepted)

    papers = {p["id"]: p for p in data["papers"]}
    hssc = "doi:10.1057/s41599-026-08463-7"
    selected = papers.get(hssc) or papers[accepted["papers"][0]]
    authors = {a["id"] for a in selected["authors"]}
    button = page.get_by_role("button", name=selected["title"], exact=True)
    button.click()
    expect(button).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".node.active")).to_have_count(len(authors))
    expect(page.locator(".edge.active")).to_have_count(len(authors) * (len(authors) - 1) // 2)
    assert page.locator("tr.selected td").nth(2).inner_text() == ", ".join(a["name"] for a in selected["authors"])
    switch(page, "ongoing")
    check_view(page, ongoing)
    expect(button).to_have_attribute("aria-pressed", "true")
    page.get_by_role("button", name="Clear selection").click()

    single = next((p for p in papers.values() if p["status"] == "ongoing" and len(p["authors"]) == 1), None)
    if single:
        page.get_by_role("button", name=single["title"], exact=True).click()
        expect(page.locator(".node.active")).to_have_count(1)
        expect(page.locator(".edge.active")).to_have_count(0)
    temporary = next((p for p in papers.values() if p["status"] == "ongoing"), None)
    if temporary and not single:
        page.get_by_role("button", name=temporary["title"], exact=True).click()
    switch(page, "accepted")
    expect(page.locator("tr.selected")).to_have_count(0)
    expect(page.locator(".node.active")).to_have_count(0)

    if accepted["edges"]:
        coauthors = [a for a in accepted["nodes"] if a != data["focus"]]
        coauthor = "woojoo-lee" if "woojoo-lee" in coauthors else coauthors[0]
        pair = {data["focus"], coauthor}
        edge = next(e for e in accepted["edges"] if {e["a"], e["b"]} == pair)
        key = edge["a"] + "|" + edge["b"]
        click_edge(page, key)
        expect(page.locator("#rows tr")).to_have_count(len(edge["papers"]))
        assert [r.get_attribute("data-paper") for r in page.locator("#rows tr").all()] == edge["papers"]
        switch(page, "ongoing")
        expanded = next(e for e in ongoing["edges"] if (e["a"], e["b"]) == (edge["a"], edge["b"]))
        expect(page.locator("#rows tr")).to_have_count(len(expanded["papers"]))
        page.get_by_role("button", name="All papers").click()

        page.locator("#paper-toggle").click()
        node = page.locator("[data-author=" + json.dumps(coauthor) + "]")
        label = node.locator("text")
        (label if label.is_visible() else node.locator(".dot")).click()
        expect(page.locator("#table-scroll")).to_be_visible()
        expect(node).to_have_class(re.compile(r"\bcenter\b"))
        neighbors = sum(coauthor in (e["a"], e["b"]) for e in ongoing["edges"])
        expect(page.locator(".edge.active")).to_have_count(neighbors)
        filtered_rows = page.locator("#rows tr")
        assert filtered_rows.evaluate_all("rows => rows.map(r => r.dataset.paper)") == expanded["papers"]
        switch(page, "accepted")
        assert filtered_rows.evaluate_all("rows => rows.map(r => r.dataset.paper)") == edge["papers"]
        filtered_rows.first.get_by_role("button").click()
        expect(filtered_rows.first.get_by_role("button")).to_have_attribute("aria-pressed", "true")
        expect(filtered_rows).to_have_count(len(edge["papers"]))
        page.get_by_role("button", name="All papers").click()
        check_view(page, accepted)
        page.locator("[data-author=" + json.dumps(data["focus"]) + "]").press("Enter")
        check_view(page, accepted)
    switch(page, "ongoing")
    check_view(page, ongoing)
    picker = page.get_by_role("combobox", name="Center on author")
    author = next((a for a in accepted["nodes"] if a != data["focus"]), data["focus"])
    node = page.locator("[data-author=" + json.dumps(author) + "]")
    picker.select_option(author)
    check_view(page, ongoing)
    expect(node).to_have_class(re.compile(r"\bcenter\b"))
    dot = node.locator(".dot")
    rect = dot.bounding_box()
    plot = page.locator("#graph").bounding_box()
    x, y = rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2
    assert abs(x - plot["x"] - plot["width"] / 2) < 2
    assert abs(y - plot["y"] - plot["height"] / 2) < 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 35, y + 22, steps=5)
    page.mouse.up()
    stored = page.evaluate("JSON.parse(localStorage.getItem('coauthor-network:positions'))")
    assert author in stored, "The drag did not persist a node position"
    page.reload()
    expect(page.get_by_role("radio", name="Include Ongoing")).to_be_checked()
    check_view(page, ongoing)
    position = node.get_attribute("transform")
    switch(page, "accepted")
    assert position == node.get_attribute("transform")
    page.get_by_role("button", name="Reset layout").click()
    assert position != node.get_attribute("transform")
    initial = node.get_attribute("transform")
    page.get_by_role("button", name="Zoom in").click()
    if author != data["focus"]:
        assert initial != node.get_attribute("transform")
    page.get_by_role("button", name="Zoom out").click()
    page.get_by_role("button", name="Reset layout").click()

    page.set_viewport_size({"width": 390, "height": 844})
    page.locator("#rows tr").last.get_by_role("button").click()
    expect(page.locator("#graph")).to_be_in_viewport(ratio=.95)
    assert page.locator("#table-scroll").evaluate("e => e.scrollHeight <= e.clientHeight || e.scrollTop > 0")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.get_by_role("button", name="Clear selection").click()
    page.locator("#paper-toggle").click()
    expect(page.locator("#table-scroll")).to_be_hidden()
    page.locator("#paper-toggle").click()
    expect(page.locator("#table-scroll")).to_be_visible()
    if mobile_screenshot:
        page.locator("#table-scroll").evaluate("e => e.scrollTop = 0")
        page.screenshot(path=mobile_screenshot)
    assert not errors, errors
    print(f"Browser passed: {len(accepted['papers'])} accepted / {len(ongoing['papers'])} including ongoing; "
          "default view, author and edge filters, selection, drag, zoom, persistence and mobile table.")
    return data


def check_refresh(page, data):
    # Simulate a later public version in the test browser only.
    switch(page, "ongoing")
    updated = json.loads(json.dumps(data))
    paper = updated["papers"][0]
    page.get_by_role("button", name=paper["title"], exact=True).click()
    paper["title"] += " (updated)"
    manifest = {"version": "b" * 64, "app": "a" * 64}
    page.route("**/version.json", lambda route: route.fulfill(json=manifest))
    page.route("**/data-" + manifest["version"] + ".json", lambda route: route.fulfill(json=updated))
    before = page.locator(".node").first.get_attribute("transform")
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    expect(page.get_by_role("button", name=paper["title"], exact=True)).to_have_attribute("aria-pressed", "true")
    expect(page.get_by_role("radio", name="Include Ongoing")).to_be_checked()
    assert before == page.locator(".node").first.get_attribute("transform")
    print("Live refresh passed: new public data retained the mode, selection and positions.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="Test a real Pages deployment")
    parser.add_argument("--screenshot")
    parser.add_argument("--mobile-screenshot")
    args = parser.parse_args()
    with sync_playwright() as playwright:
        chrome = os.getenv("CHROME_BIN") or shutil.which("google-chrome") or shutil.which("chromium")
        browser = playwright.chromium.launch(executable_path=chrome)
        page = browser.new_page(viewport={"width": 1440, "height": 920})
        if not args.url:
            page.route(LOCAL + "**", artifact)
        result = exercise(page, args.url or LOCAL, args.screenshot, args.mobile_screenshot)
        if not args.url:
            check_refresh(page, result)
        browser.close()
