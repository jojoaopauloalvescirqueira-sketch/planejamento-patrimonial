"""Exercise the initial forecast through the public form with synthetic data."""
import functools
import os
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "form-patrimony"
OUT.mkdir(parents=True, exist_ok=True)


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    handler = functools.partial(Quiet, directory=str(ROOT / "dist"))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server, sync_playwright() as playwright:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            browser = playwright.chromium.launch(headless=True, executable_path=os.environ.get("PP_CHROMIUM"))
            context = browser.new_context(viewport={"width": 1200, "height": 900}, timezone_id="America/Sao_Paulo")
            context.route("https://api.frankfurter.dev/**", lambda route: route.fulfill(status=503))
            page = context.new_page()
            page.clock.set_fixed_time(datetime(2026, 11, 8, 13, tzinfo=timezone.utc))
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            before = page.evaluate("localStorage.getItem(PlanningStore.KEY)")
            page.get_by_role("button", name="Preencher novo formulário", exact=True).click()

            def field(name):
                return page.locator(f"#pl-native-{name}")

            def choose(profile):
                field("openProfiles").click()
                page.locator(f"[data-pl-choose-profile={profile}]").click()

            def money(name, value):
                assert field(name).inner_text().replace("\xa0", " ") == "US$ " + value

            expect(field("saldo")).to_have_value("")
            card = field("patrimonyForecast")
            income = field("incomeForecast")
            expect(income.get_by_role("heading", name="Prazos e metas de renda")).to_be_visible()
            assert income.evaluate("""el =>
                ['lifeSummary','dreamSummary'].every(
                    id => el.contains(document.getElementById('pl-native-' + id))) &&
                el.nextElementSibling.id === 'pl-native-patrimonyForecast' &&
                el.nextElementSibling.nextElementSibling.id === 'pl-native-pastStart'
            """)
            expect(field("assetForecast")).to_have_count(0)
            expect(income.get_by_text("Patrimônio necessário", exact=True)).to_have_count(0)
            expect(field("patrimonyValue")).to_be_hidden()
            expect(field("patrimonyMonth")).to_contain_text("Preencha mês e ano iniciais")
            field("ano").fill("2026")
            field("mes").select_option("3")
            field("saldo").fill("1000")
            field("aporte").fill("200")
            choose("base")
            expect(field("sonhoBRL")).to_have_value("")
            expect(field("fxInfo")).to_contain_text("Atualize a cotação")
            expect(field("pastStart")).to_contain_text("8 meses passados")
            expect(field("patrimonyMonth")).to_contain_text("fevereiro/2036")
            money("patrimonyValue", "259.450,90")
            money("patrimonyInitial", "1.000,00")
            money("patrimonyContributions", "24.000,00")
            money("patrimonyResult", "234.450,90")
            card.screenshot(path=str(OUT / "desktop.png"))

            field("aporte").fill("0")
            money("patrimonyContributions", "0,00")
            money("patrimonyValue", "34.710,99")
            field("saldo").fill("0")
            money("patrimonyValue", "0,00")
            money("patrimonyResult", "0,00")
            field("saldo").fill("1000")
            field("aporte").fill("200")
            choose("conservative")
            assert "259.450,90" not in field("patrimonyValue").inner_text()
            choose("base")
            field("saldo").fill("")
            expect(field("patrimonyValue")).to_be_hidden()
            expect(field("patrimonyParts")).to_be_hidden()
            field("saldo").fill("1000")
            money("patrimonyValue", "259.450,90")
            field("ano").fill("2200")
            expect(field("patrimonyValue")).to_be_hidden()
            expect(field("patrimonyMonth")).to_contain_text("Patrimônio projetado indisponível")
            field("ano").fill("2026")
            money("patrimonyValue", "259.450,90")

            page.set_viewport_size({"width": 320, "height": 700})
            card.screenshot(path=str(OUT / "320px.png"))
            assert card.evaluate("el=>el.scrollWidth<=el.clientWidth && el.getBoundingClientRect().right<=innerWidth")
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            page.set_viewport_size({"width": 1200, "height": 900})
            field("mes").select_option("11")
            expect(field("patrimonyMonth")).to_contain_text("outubro/2036")
            field("sonhoMoeda").select_option("USD")
            field("sonhoBRL").fill("200")
            field("custoMoeda").select_option("USD")
            field("custoValor").fill("100")
            life = field("lifeSummary")
            dream = field("dreamSummary")

            def required_capital(goal_card, expected):
                metric = goal_card.locator("dl > div").filter(
                    has=page.get_by_text("Patrimônio necessário", exact=True)
                )
                assert metric.locator("dd").inner_text().replace("\xa0", " ") == "US$ " + expected

            required_capital(life, "3.333,34")
            required_capital(dream, "6.666,67")
            field("sonhoBRL").fill("1000000")
            expect(dream).to_contain_text("Fora dos 120 meses")
            required_capital(dream, "33.333.333,34")
            field("sonhoBRL").fill("200")
            page.set_viewport_size({"width": 320, "height": 700})
            for goal_card in (life, dream):
                assert goal_card.evaluate("el=>el.scrollWidth<=el.clientWidth && el.getBoundingClientRect().right<=innerWidth")
            page.set_viewport_size({"width": 1200, "height": 900})
            field("stopOpen").click()
            expect(field("stopUse")).to_be_enabled()
            field("stopUse").click()
            expect(field("stopBadge")).to_contain_text("Ao salvar")
            money("patrimonyValue", "259.450,90")
            required_capital(dream, "6.666,67")
            submit = page.get_by_role("button", name="Confirmar plano", exact=True)
            submit.click()
            review = page.locator("[data-pl-preview]")
            expect(review).to_be_visible()
            review_text = review.inner_text().replace("\xa0", " ")
            assert "Patrimônio projetado ao fim do plano: US$ 259.450,90 · outubro/2036" in review_text
            assert "PARADA DOS APORTES" in review_text
            assert page.evaluate("localStorage.getItem(PlanningStore.KEY)") == before
            page.get_by_role("button", name="Voltar e editar", exact=True).click()
            expect(submit).to_be_visible()
            assert not errors, errors
            browser.close()
        finally:
            server.shutdown()
    print("PASS initial patrimony, composition, past start, missing FX and goal, input changes, zero, stop, review and 320 px")


if __name__ == "__main__":
    main()
