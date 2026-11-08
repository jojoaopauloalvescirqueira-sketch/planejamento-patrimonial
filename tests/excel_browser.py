"""Export the real XLSX from a synthetic browser profile and inspect the package."""
import functools
import json
import os
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "excel-export"
OUT.mkdir(parents=True, exist_ok=True)
SHEET = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
CHART = {"c": "http://schemas.openxmlformats.org/drawingml/2006/chart"}


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def grid(book, sheet):
    xml = ET.fromstring(book.read(f"xl/worksheets/sheet{sheet}.xml"))
    return {
        cell.attrib["r"]: cell.findtext("s:is/s:t", namespaces=SHEET)
        if cell.get("t") == "inlineStr"
        else float(cell.findtext("s:v", namespaces=SHEET))
        for cell in xml.findall(".//s:c", SHEET)
    }


def inspect(path, archived=False, empty=False):
    with ZipFile(path) as book:
        assert book.testzip() is None
        names = book.namelist()
        assert not any("externalLink" in n or "vbaProject" in n for n in names)
        for name in names:
            root = ET.fromstring(book.read(name))
            assert not root.findall(".//s:f", SHEET)
            assert all(node.get("TargetMode") != "External" for node in root.iter())
            assert b"PRIVATE_BROKER_LOGIN" not in book.read(name)
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        tabs = [n.get("name") for n in workbook.findall(".//s:sheet", SHEET)]
        assert tabs[:6] == ["Resumo", "Mensal", "Lançamentos", "Fechamentos", "Contas e metas", "Projeções"]
        assert len(tabs) == (11 if archived else 6)
        for index, _ in enumerate(tabs, 1):
            table = ET.fromstring(book.read(f"xl/tables/table{index}.xml"))
            assert table.get("ref") == table.find("s:autoFilter", SHEET).get("ref")
            assert table.find("s:tableStyleInfo", SHEET).get("showRowStripes") == "1"
            if index > 1:
                sheet = ET.fromstring(book.read(f"xl/worksheets/sheet{index}.xml"))
                assert sheet.find(".//s:pane", SHEET).get("topLeftCell") == "D5"
                assert all(sheet.find(f".//s:col[@min='{col}']", SHEET).get("hidden") == "1" for col in (2, 3))
        if empty:
            assert "xl/charts/chart1.xml" not in names
            assert grid(book, 1)["A6"] == "Nenhuma conta ativa"
            return
        summary, monthly, movement, closure, reference = [grid(book, n) for n in (1, 2, 3, 4, 6)]
        assert "Build " in summary["A2"]
        assert summary["A5"] == 2000  # Initial capital for two active accounts, once each.
        assert summary["A26"] == "=Conta fictícia"
        assert monthly["H5"] == 0 and isinstance(monthly["D5"], float)
        assert "M5" not in monthly and "Conversão indisponível" in monthly["R5"]
        assert monthly["G6"] == 1000 and monthly["L6"] == 1230
        assert monthly["L7"] == 1466.9
        assert monthly["E126"] == "Finalizado" and monthly["F126"] == "Aguardando fechamento"
        assert monthly["H126"] == -25 and "L126" not in monthly and "I126" not in monthly
        assert reference["E5"] == 1230 and reference["E6"] == 1466.9
        assert "Anulado" in movement.values() and "Revisão anterior" in movement.values()
        assert "Ausência confirmada" in movement.values()
        assert "Confirmado" in closure.values()
        assert ("Arquivo fictício" in grid(book, 7).values()) if archived else (
            all("Arquivo fictício" not in grid(book, n).values() for n in range(1, 7)))
        if archived:
            assert "Pessoa fictícia" in grid(book, 9).values()
        for index in (1, 2):
            chart = ET.fromstring(book.read(f"xl/charts/chart{index}.xml"))
            assert chart.find(".//c:dispBlanksAs", CHART).get("val") == "gap"
            assert len(chart.findall(".//c:ser", CHART)) == 2
        chart = ET.fromstring(book.read("xl/charts/chart1.xml"))
        actual = chart.findall(".//c:ser", CHART)[0]
        assert not actual.findall(".//c:numCache/c:pt", CHART)


SEED = """() => {
  const api = JPWPlanning, issue = (type, payload) => {
    const r = api.commands.execute(type,payload,api.queries.token(payload.accountId));
    if (!r.ok) throw Error(JSON.stringify(r));
    return r.accountId;
  };
  const create = (name,startMonth) => issue('createAccount',{name,startMonth,login:'PRIVATE_BROKER_LOGIN',
    initialUsd:1000,monthlyContributionUsd:200,profileId:'base',goals:{adequate:null,ideal:{value:100,currency:'USD'}}});
  const run = (accountId,month,type,extra) => issue(type,{accountId,month,...extra});
  const fill = (id,m,usd) => {
    run(id,m,'recordResult',{usd});
    for (const kind of ['contribution','withdrawal']) run(id,m,'confirmNoMovement',{kind,confirmation:true});
    run(id,m,'finalizeMonth',{confirmFlows:true});
  };
  const a = create('=Conta fictícia','2026-11'), b = create('Conta com lacuna','2026-10');
  const old = create('Arquivo fictício','2025-12');
  run(a,'2026-11','recordContribution',{usd:50,brl:250});
  const id = api.queries.account(a).plan.contributions[0].id;
  run(a,'2026-11','recordContribution',{id,usd:0,brl:0,reason:'Anulação de teste'});
  fill(a,'2026-11',0);
  fill(b,'2026-11',-25);
  fill(old,'2025-12',0);
  const review = api.queries.previewFinalizeYear({accountId:old,year:'2025'});
  issue('finalizeYear',{accountId:old,year:'2025',signerName:'Pessoa fictícia',declarationAccepted:true,reviewKey:review.reviewKey});
  issue('archiveAccount',{accountId:old,confirmation:true});
  api.ui.selectView('consolidated');
}"""


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT / "dist")))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True, executable_path=os.environ.get("PP_CHROMIUM"))
            context = browser.new_context(viewport={"width": 1100, "height": 850}, timezone_id="America/Sao_Paulo")
            context.route("https://api.frankfurter.dev/**", lambda route: route.fulfill(status=503))
            page = context.new_page()
            page.clock.set_fixed_time(datetime(2026, 11, 8, 13, tzinfo=timezone.utc))
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            heading = page.locator('[data-pl-action="excel"]')
            dialog = page.locator("#excel-dialog")
            archived = dialog.locator("#excel-archived")

            def export(filename):
                with page.expect_download() as received:
                    dialog.get_by_role("button", name="Baixar arquivo Excel").click()
                download = received.value
                assert download.suggested_filename == "planejamento-patrimonial-2026-11-08.xlsx"
                destination = OUT / filename
                download.save_as(destination)
                expect(dialog.get_by_role("status")).to_have_text("Arquivo Excel preparado para download.")
                dialog.get_by_role("button", name="Cancelar").click()
                return destination

            heading.click()
            inspect(export("vazio.xlsx"), empty=True)
            page.evaluate(SEED)
            raw = page.evaluate("localStorage.getItem(PlanningStore.KEY)")
            page.locator("[data-pl-account]").select_option(label="=Conta fictícia")
            heading.click()
            expect(archived).not_to_be_checked()
            page.locator("#excel-dialog").screenshot(path=str(OUT / "dialogo.png"))
            inspect(export("planejamento-patrimonial-exemplo.xlsx"))
            expect(heading).to_be_focused()
            page.get_by_role("button", name="Backup e dados", exact=True).click()
            backup = page.locator("#data-dialog")
            backup.get_by_role("button", name="Exportar Excel", exact=True).click()
            archived.check()
            inspect(export("com-arquivados.xlsx"), archived=True)
            expect(backup).to_be_visible()
            expect(backup.locator("#excel-open-data")).to_be_focused()
            backup.get_by_role("button", name="Fechar backup e recuperação").click()
            assert raw == page.evaluate("localStorage.getItem(PlanningStore.KEY)")

            page.set_viewport_size({"width": 320, "height": 560})
            heading.focus()
            page.keyboard.press("Enter")
            expect(archived).to_be_focused()
            box = dialog.bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= 320
            assert box["y"] >= 0 and box["y"] + box["height"] <= 560
            # Mutate the confirmed raw snapshot from a second tab after opening the dialog.
            other = context.new_page()
            other.goto(page.url)
            other.evaluate("localStorage.setItem(PlanningStore.KEY, localStorage.getItem(PlanningStore.KEY)+' ')")
            dialog.get_by_role("button", name="Baixar arquivo Excel").click()
            expect(dialog.get_by_role("status")).to_contain_text("Exportação não concluída.")
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
    print("PASS Excel download, native tables and charts, typed data, both entry points, archives, cancellation, 320px and stale base")


if __name__ == "__main__":
    main()
