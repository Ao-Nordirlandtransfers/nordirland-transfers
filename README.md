# Nordirland Transferzentrale

Community-Übersicht der Transfers rund um nordirische Vereine in
[Anstoss Online](https://www.anstoss-online.de/), im Stil von
transfermarkt.de. Läuft komplett kostenlos auf GitHub (Pages + Actions),
kein eigener Server nötig.

## Wie es funktioniert

1. `scrape.py` ruft die öffentliche Länderseite von Nordirland ab
   (`?do=land&land_id=240`) und liest die Tabelle "Letzte inländische
   Transfers" aus.
2. Da die Seite immer nur die letzten ~10 Transfers zeigt, wird jeder neue
   Fund in `data.json` **angehängt** (keine Duplikate) – so entsteht über
   Zeit eine echte Historie.
3. `.github/workflows/scrape.yml` führt das Skript automatisch **einmal
   nachts** aus (kurz nach dem AO-Reset um 0:01 Uhr) und committet
   Änderungen an `data.json`.
4. `index.html` liest `data.json` und zeigt sie als sortierbare,
   durchsuchbare Tabelle an.

## Einrichtung (einmalig, ca. 5 Minuten)

1. **Neues GitHub-Repo erstellen** (öffentlich, z.B. `nordirland-transfers`)
   und diese Dateien hochladen (per Web-Upload oder `git push`).
2. **Actions-Berechtigung setzen:** Repo → Settings → Actions → General →
   unter "Workflow permissions" **"Read and write permissions"**
   aktivieren. (Ohne das kann der Bot `data.json` nicht committen.)
3. **GitHub Pages aktivieren:** Repo → Settings → Pages → unter "Source"
   `Deploy from a branch` wählen, Branch `main`, Ordner `/ (root)`.
4. Nach ein paar Minuten ist die Seite unter
   `https://<dein-username>.github.io/<repo-name>/` erreichbar.
5. Den ersten Scrape-Lauf manuell anstoßen: Repo → Actions → "Nordirland
   Transfers aktualisieren" → **Run workflow**. Danach läuft es automatisch
   im 6-Stunden-Takt weiter.

## Anpassungen

- **Anderes Land:** In `scrape.py` die `land_id` in der `URL`-Variable
  ändern (die IDs stehen in der Flaggenleiste auf anstoss-online.de, z.B.
  in der URL beim Klick auf ein Land).
- **Häufigkeit:** Cron-Ausdruck in `.github/workflows/scrape.yml` anpassen
  (z.B. `'0 * * * *'` für stündlich).
- **Design:** Farben/Schriften liegen als CSS-Variablen ganz oben in
  `index.html` (`:root { --pitch: ...; --gold: ...; }`).

## Bekannte Grenze: Reset-Bursts über 10 Transfers

Die Länderseite zeigt immer nur die **letzten 10 Transfers insgesamt**.
Wenn beim nächtlichen Reset mehr als 10 Transfers gleichzeitig passieren
(z.B. Saisonstart), sind die älteren davon sofort nicht mehr sichtbar -
das kann kein Scraping-Zeitpunkt verhindern. An normalen Tagen mit
wenigen Transfers ist das kein Problem.

Eine vollständige Lösung wäre, statt der Transferliste die Kader aller 20
Premiership-Vereine regelmäßig zu speichern und Tag für Tag zu
vergleichen (wer ist neu im Kader, wer fehlt). Das würde aber Login-Daten
erfordern (die Kader-Seiten sind nicht öffentlich einsehbar) und deutlich
mehr Komplexität - aktuell bewusst nicht umgesetzt.

## Falls sich die Seitenstruktur ändert

`scrape.py` sucht die Tabelle anhand ihrer Spaltenüberschriften (Pos.,
Spieler, Stärke, Alter, Nat., Von, Nach, Datum), nicht anhand fester
CSS-Klassen – das übersteht kleinere Layout-Änderungen. Falls der Workflow
trotzdem "Keine Transfers gefunden" meldet, hat sich vermutlich die
Tabellenstruktur grundlegend geändert und die Parsing-Logik muss
nachgezogen werden.
