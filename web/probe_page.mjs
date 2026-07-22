import { chromium } from "playwright-core";

const URL = process.argv[2] || "http://localhost:3311/v2/b/26-10321-RNVN";
const browser = await chromium.launch({
  executablePath: process.env.PW_CHROME ||
    (await import("node:fs")).readdirSync(process.env.HOME + "/.cache/ms-playwright")
      .filter((d) => d.startsWith("chromium-"))
      .map((d) => `${process.env.HOME}/.cache/ms-playwright/${d}/chrome-linux64/chrome`)[0],
  args: ["--no-sandbox"],
});
const page = await browser.newPage();
const msgs = [];
page.on("console", (m) => msgs.push(`[console.${m.type()}] ${m.text()}`));
page.on("pageerror", (e) => msgs.push(`[PAGEERROR] ${e.message}\n${e.stack?.split("\n").slice(0,4).join("\n")}`));
page.on("requestfailed", (r) => msgs.push(`[REQFAIL] ${r.url()} :: ${r.failure()?.errorText}`));

await page.goto(URL, { waitUntil: "networkidle", timeout: 45000 }).catch((e) => msgs.push(`[GOTO-ERR] ${e.message}`));
await page.waitForTimeout(2500);

// Try to click the first page card, then the Confirm button, and report reactions.
const report = {};
try {
  const cards = await page.$$("button.v2card");
  report.cardCount = cards.length;
  if (cards[1]) { await cards[1].click({ timeout: 3000 }); await page.waitForTimeout(400); }
  report.afterCardClickPanelNav = await page.$eval(".v2panel-nav span", (el) => el.textContent).catch(() => "NO PANEL NAV");
  const catBtns = await page.$$(".v2panel-catgrid button");
  report.catBtnCount = catBtns.length;
  if (catBtns[0]) { await catBtns[0].click({ timeout: 3000 }); await page.waitForTimeout(300); }
  // is the confirm button enabled?
  const confirm = await page.$("button.btn.primary");
  report.confirmDisabled = confirm ? await confirm.isDisabled() : "NO CONFIRM BTN";
} catch (e) {
  report.clickError = e.message;
}

console.log("=== CONSOLE / ERRORS ===");
console.log(msgs.length ? msgs.join("\n") : "(no console messages or errors captured)");
console.log("\n=== INTERACTION REPORT ===");
console.log(JSON.stringify(report, null, 2));
await browser.close();
