# QR Platba

Lokální webová aplikace pro české QR platby podle SPAYD 1.0. V prohlížeči spravuje profily účtů, převádí české účty na IBAN, validuje MOD 97 a generuje PNG s QR kódem. Rozhraní je česky, reaguje na světlý/tmavý režim a podporuje `⌘N` pro novou platbu.

## Spuštění přes Docker

```bash
docker build -t qr-platba .
docker run --rm -p 8080:8080 qr-platba
```

Alternativně spusťte `docker compose up --build -d`.

Na počítači s Dockerem otevřete [http://localhost:8080](http://localhost:8080), z jiného zařízení v místní síti `http://IP_POČÍTAČE:8080/`. Port 8080 je publikován na všech síťových rozhraních hostitele; přístup se řídí také firewallem počítače. Místní nasazení nepotřebuje cloudové služby. Během sestavení se stáhne připnutá závislost `qrcode[pil]`; běžící kontejner už síť nepotřebuje.

Profily se ukládají do `localStorage` konkrétního prohlížeče a jeho originu. Přežijí restart aplikace i kontejneru; při vymazání dat webu se smažou. Údaje platby se při generování QR odesílají na server a server je neukládá. Při veřejném nasazení procházejí zvolenou reverzní proxy nebo tunelem.

**Neotvírejte `static/index.html` přímo z disku.** Adresa `file://` nemá přístup k místnímu API. Aplikaci vždy otevřete přes `http://127.0.0.1:8080/` po spuštění serveru.

Na Macu lze bez Dockeru použít také soubor `Spustit QR Platba.command` (dvojklikem nebo v Terminálu příkazem `zsh "Spustit QR Platba.command"`). Při prvním spuštění nainstaluje dvě Python závislosti do místního `.venv`, otevře prohlížeč a spustí server. Další běh už tyto závislosti nestahuje.

## Lokální spuštění a testy

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
.venv/bin/python -m unittest discover -s tests -v
```

## GitHub a deployment na vlastní server

Každý push do větve `main` spustí `.github/workflows/container.yml`, otestuje aplikaci a vydá obraz `ghcr.io/martinrybicka/qr-platba:latest`. GitHub slouží pro zdrojový kód a kontejnerový obraz; aplikace poběží na vašem Docker serveru.

Na serveru stáhněte `compose.deploy.yaml` a spusťte:

```bash
docker compose -f compose.deploy.yaml up -d
```

Poté otevřete `http://IP_SERVERU:8080/`. Novou verzi nasadíte pomocí `docker compose -f compose.deploy.yaml pull && docker compose -f compose.deploy.yaml up -d`. Balíček `ghcr.io/martinrybicka/qr-platba` je veřejný a lze jej stáhnout bez přihlášení. Pro veřejný internet použijte vlastní reverzní proxy s HTTPS.

### Portainer (Docker Standalone)

1. V Portaineru otevřete **Stacks → Add stack → Git repository**. Zadejte URL `https://github.com/martinrybicka/qr-platba`, větev `main` a cestu `compose.deploy.yaml`.
2. Volitelně nastavte proměnnou stacku `QR_PLATBA_PORT` (výchozí `8080`). Pak klikněte na **Deploy the stack**.
3. Pro další vydání v Portaineru zapněte GitOps aktualizace a volbu opětovného stažení obrazu. Po dokončení GitHub Actions lze stack také ručně aktualizovat s volbou znovu stáhnout image.

Portainer používá hotový image z GHCR. GitHub Actions jej sestaví při pushi do `main`; samotný Portainer nepotřebuje zdrojový kód pro sestavení.

## Specifikace

Implementace vychází z [aktuální specifikace QR Platba](https://qr-platba.cz/pro-vyvojare/specifikace-formatu/) a [standardu ČBA 1.2](https://qr-platba.cz/wp-content/uploads/1645-standard-qr-v1-2-cerven-2021.pdf). Používá `SPD*1.0*ACC:<IBAN>*AM:<částka>*CC:CZK` a volitelná pole `X-VS`, `MSG`. Kvůli malému logu uprostřed QR používá korekci chyb H; čtyřmodulová tichá zóna zůstává zachovaná. PNG přidává dekorativní kartu mimo samotný QR kód. Zpráva se převádí na velká písmena bez diakritiky kvůli kompatibilitě bankovních aplikací. Max. částka je 9 999 999,99 Kč, VS má nejvýše 10 číslic, zpráva nejvýše 60 znaků.
