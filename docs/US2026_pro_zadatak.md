# Ugradbeni sistemi — Samostalni projekat

## Agentski IoT sistem zasnovan na Hermes Agentu

---

## Uvod

U okviru ovog projekta realizirat ćemo **agentski IoT sistem** (*pametni dom / intelligent home*) zasnovan na velikom jezičkom modelu (*Large Language Model*, LLM). Za razliku od klasičnog pristupa, gdje korisnik svaku radnju u sistemu izvodi direktnim slanjem komandi ili izmjenom konfiguracije, ovdje sa sistemom komuniciramo **kroz prirodni jezik** — agentu opisujemo šta želimo, a on samostalno odlučuje koje alate i komande treba iskoristiti da bi taj zahtjev ispunio.

Kao agenta koristimo **Hermes Agent** — autonomni AI agent otvorenog koda razvijen od strane organizacije Nous Research. Hermes Agent se izvršava na računaru Raspberry Pi 5 (8GB RAM), unutar Docker kontejnera. Agent se oslanja na LLM koji se izvršava na ML serveru fakulteta, a sa krajnjim IoT uređajima komunicira putem MQTT protokola.

Krajnji uređaji u sistemu su dvije vrste:

- **Tasmota uređaji** — zasnovani na ESP32, sa Tasmota firmware-om, na koje se dodaju senzori i aktuatori (npr. DHT11 senzor temperature i vlažnosti, modul sa relejima)
- **Custom uređaji** — zasnovani na picoETF (Raspberry Pi Pico W), sa aplikacijom napisanom u MicroPython-u, koja sa sistemom komunicira putem JSON poruka preko MQTT-a

Cilj vježbe je da se studenti upoznaju sa agentskim pristupom korištenju LLM-a, sa MQTT komunikacijom u IoT sistemima, te da samostalno realiziraju krajnje uređaje i poduče agenta da ih koristi.

Dokumentacija Hermes Agenta dostupna je na adresi https://hermes-agent.nousresearch.com/docs i preporučuje se konsultovati je tokom rada.

Arhitektura cjelokupnog sistema prikazana je na slici 1. Studenti sa svog računara (PC) pristupaju Raspberry Pi 5 računaru putem SSH protokola. Na Raspberry Pi 5 se, unutar Docker kontejnera, izvršava Hermes Agent. Agent koristi LLM koji se izvršava u okviru Ollama na ML serveru (`195.130.59.211`), a sa krajnjim uređajima komunicira posredstvom MQTT brokera (`195.130.59.221`). Pored toga, agent po potrebi može pristupati i Internetu (npr. za web pretragu). Krajnji uređaji (Tasmota i picoETF) nalaze se u lokalnoj WiFi mreži i sa sistemom komuniciraju preko istog MQTT brokera.

---

## Priprema radnog okruženja

Radno okruženje je pripremljeno kao Docker image koji sadrži sve preduslove za rad sa Hermes Agentom (Python, MQTT biblioteke, mrežne alate), ali *ne* sadrži sam Hermes Agent — njega studenti instaliraju u toku vježbe. Image takođe sadrži certifikat (CA) potreban za sigurnu (HTTPS) komunikaciju sa ML serverom, pomoćne skripte za testiranje MQTT-a, te kostur MCP servera koji povezuje agenta sa IoT uređajima.

### Preuzimanje i raspakivanje paketa

Paket sa radnim okruženjem dostupan je na adresi:

https://drive.google.com/file/d/16sGLdrPcAPdrv7G62CIe6PH1IjePxuC1/view

Pošto se na Raspberry Pi 5 radi putem SSH-a (bez grafičkog okruženja), paket se preuzima direktno iz komandne linije. Obzirom da se radi o većem fajlu sa Google Drive-a, najpouzdaniji način je alat `gdown`:

```bash
pip install --user gdown
gdown 16sGLdrPcAPdrv7G62CIe6PH1IjePxuC1 -O us2026-hermes-paket.zip
```

> **Hint:** Identifikator `16sGLdrPcAPdrv7G62CIe6PH1IjePxuC1` u gornjoj komandi je ID fajla na Google Drive-u (dio adrese između `/d/` i `/view`). Alternativno, fajl se može preuzeti i pomoću `curl`-a, navođenjem istog ID-a u adresi `https://drive.google.com/uc?export=download&id=<ID>&confirm=t`.

Nakon preuzimanja, paket je potrebno raspakirati:

```bash
unzip us2026-hermes-paket.zip
cd us2026-paket
```

Sadržaj paketa čine: Docker image (`.tar` fajl), skripta za pokretanje kontejnera (`pokreni_hermes.sh`) i skripta za poništavanje rada (`reset_hermes.sh`).

### Pokretanje kontejnera

Kontejner se pokreće priloženom skriptom:

```bash
bash pokreni_hermes.sh
```

Skripta automatski obavlja sve potrebne korake. Pri prvom pokretanju, ona iz `.tar` fajla učitava Docker image u Docker (komandom `docker load`), jer se image ne može direktno pokrenuti dok nije učitan. Zatim skripta traži oznaku tima, kreira (pri prvom pokretanju) folder za trajnu pohranu rada tima, te pokreće kontejner. Pri svakom narednom pokretanju, skripta prepoznaje da je image već učitan i da kontejner tima već postoji, pa ga samo ponovo pokreće.

Nakon unosa oznake tima (npr. `tim01`), skripta ostavlja korisnika u komandnom promptu unutar kontejnera (oznaka `#`).

> **Hint:** Sav rad tima (instalacija Hermesa, konfiguracija, sesije) pohranjuje se u folder na Raspberry Pi računaru i trajno se čuva. Kontejner se može zaustaviti (komandom `exit`) i kasnije ponovo pokrenuti istom skriptom — rad se nastavlja tamo gdje je stao.

> **Napomena:** Skripta `reset_hermes.sh` trajno briše sav rad tima i vraća okruženje u početno, čisto stanje. Koristite je samo ako želite krenuti potpuno ispočetka.

---

## Instalacija i konfiguracija Hermes Agenta

### Instalacija

Hermes Agent se instalira komandom (unutar kontejnera):

```bash
pip install --user --break-system-packages hermes-agent
```

> **Napomena:** Zastavica `--user` je obavezna. Ona instalira Hermes u folder koji se trajno čuva, pa instalacija preživljava ponovno pokretanje kontejnera. Bez nje bi se Hermes morao instalirati iznova pri svakom pokretanju.

Nakon instalacije se pokreće postinstall, koji povezuje preostale komponente:

```bash
hermes postinstall
```

Pošto su pomoćni alati (Node.js, ripgrep, ffmpeg) već prisutni u image-u, ovaj korak bi ih trebao prepoznati i preskočiti njihovo preuzimanje. Uspješnost instalacije se provjerava komandom:

```bash
hermes --version
```

### Konfiguracija LLM modela

Konfiguracija providera i modela se pokreće komandom:

```bash
hermes setup
```

U toku konfiguracije, kroz interaktivni meni (kretanje strelicama, potvrda tipkom `<Enter>`), potrebno je odabrati opciju za ručni unos prilagođenog endpointa — **Custom endpoint (enter URL manually)**. Zatim se unose sljedeće vrijednosti:

- **API base URL:** `https://195.130.59.211:11443/v1`
- **API key (token):** token koji je dodijeljen vašem timu, oblika `sk-us2026-timXX-................`
- **Model:** `qwen3.5:9b-64k`

> **Napomena:** Token je vezan za vaš tim i predstavlja pristupni ključ ML serveru. Ne dijelite ga sa drugima i ne pohranjujte ga u kod koji predajete. ML server koristi vlastiti (self-signed) certifikat koji je već ugrađen u radno okruženje, pa sigurna komunikacija radi automatski — nije potrebno (niti poželjno) isključivati provjeru certifikata.

Konfiguracija messaging platformi (Telegram, Discord) se u ovom koraku može preskočiti — vraćamo joj se kasnije.

### Pokretanje chat interfejsa

Nakon uspješne konfiguracije, razgovor sa agentom se pokreće komandom:

```bash
hermes
```

Isti razgovor se može pokrenuti i eksplicitnom komandom `hermes chat`. Moderniji tekstualni interfejs (TUI) se pokreće sa:

```bash
hermes --tui
```

Pri pokretanju, agent prikazuje model koji koristi, dostupne alate i skills. Rad sa agentom se može provjeriti jednostavnim pozdravom, npr. unosom `Zdravo, predstavi se`.

### Konfiguracija Telegram klijenta

Hermes Agent se može povezati sa messaging platformama, pa se sa agentom može komunicirati i putem Telegram-a. Za to je potrebno:

1. U Telegram aplikaciji, putem bota `@BotFather`, kreirati novog bota i pribaviti njegov token.
2. Pokrenuti konfiguraciju gateway-a:
   ```bash
   hermes gateway setup
   ```
3. Odabrati Telegram kao platformu i unijeti token bota.
4. Pokrenuti gateway:
   ```bash
   hermes gateway run
   ```

Nakon toga je moguće sa agentom razgovarati slanjem poruka botu putem Telegram-a. Detaljne upute dostupne su u dokumentaciji Hermes Agenta (sekcija o gateway-u i messaging platformama).

---

## Princip rada: sve kroz dijalog

Ključni princip ove vježbe jeste da se sve operacije nad IoT sistemom izvode kroz dijalog sa agentom, a ne direktnim izvršavanjem komandi ili ručnom izmjenom konfiguracije. Umjesto da, na primjer, sami napišete MQTT komandu za uključivanje releja, vi agentu opisujete cilj prirodnim jezikom, a agent samostalno bira i izvršava potrebne alate.

Tako npr., umjesto ručnog slanja MQTT poruke, korisnik agentu kaže:

> *Ukljuci prvi relej na uredjaju u dnevnom boravku.*

a agent na osnovu toga sam odlučuje koji alat (MCP funkciju) treba pozvati i sa kojim argumentima. Isto vrijedi i za otkrivanje uređaja, čitanje senzora i sva ostala dejstva u sistemu.

> **Hint:** Kvalitet rada agenta u velikoj mjeri zavisi od jasnoće zahtjeva. Ako agent ne uradi ono što ste očekivali, pokušajte zahtjev formulisati preciznije ili ga razložiti na manje korake. Agent takođe pamti tok razgovora, pa se možete pozivati na ranije rečeno.

---

## Zadaci

Zadaci 1 i 2 predstavljaju osnovne zadatke kroz koje studenti provjeravaju rad Hermes Agenta, MQTT komunikaciju i integraciju sa krajnjim IoT uređajima. Ovi zadaci mogu poslužiti kao osnova za konačni projekat, ali ih je potrebno proširiti vlastitim primjerima, scenarijima ili dodatnim funkcionalnostima.

Konačni projekat ne treba biti sveden samo na osnovno očitavanje senzora ili uključivanje i isključivanje aktuatora. Od svakog tima se očekuje da, na osnovu realiziranih osnovnih funkcionalnosti, osmisli vlastiti agentski scenario u kojem Hermes Agent koristi dostupne MCP funkcije, podatke iz sistema i MQTT komunikaciju za izvršavanje smislenih radnji kroz dijalog sa korisnikom.

Zadatak 3 daje prijedloge mogućih proširenja i samostalnih ideja, ali timovi mogu predložiti i vlastito rješenje, uz prethodni dogovor sa predmetnim nastavnikom ili asistentom.

### Zadatak 1 — Tasmota uređaj i otkrivanje uređaja

Realizirati Tasmota uređaj zasnovan na ESP32, na koji su priključeni:

- jedan senzor temperature i vlažnosti DHT11
- jedan modul sa dva releja

Postupak obuhvata:

1. Postavljanje (flash) Tasmota firmware-a na ESP32 (ako već nije postavljen) i osnovnu konfiguraciju uređaja (povezivanje na WiFi mrežu laboratorije i na MQTT broker).
2. Konfigurisanje priključenih komponenti u Tasmota web sučelju: dodavanje DHT11 senzora na odgovarajući GPIO i konfigurisanje dva releja na pripadajuće GPIO.
3. Provjeru da uređaj objavljuje telemetriju (očitanja DHT11) i da prihvata komande za releje putem MQTT-a.

Nakon što je uređaj funkcionalan, kroz dijalog sa agentom zatražiti da preskenira mrežu, pronađe sve Tasmota uređaje i da ih doda u svoju memoriju, kako bi ih kasnije mogao koristiti. Primjer zahtjeva agentu:

> *Preskeniraj lokalnu mrezu, pronadji sve Tasmota uredjaje i zapamti ih da ih kasnije mozemo koristiti.*

Provjeriti rad sistema kroz dijalog: zatražiti od agenta da očita temperaturu i vlažnost sa DHT11 senzora, te da uključi i isključi pojedine releje.

> **Napomena:** Više Tasmota uređaja u laboratoriji dijeli isti MQTT broker. Da biste razlikovali svoj uređaj od uređaja drugih timova, koristite jedinstveno ime uređaja (topic prefiks) prema dogovoru sa asistentom.

### Zadatak 2 — Custom uređaj na picoETF (MicroPython)

Napisati MicroPython aplikaciju za picoETF (Raspberry Pi Pico W), koja realizira krajnji uređaj sa sljedećom funkcionalnošću:

- povezivanje na WiFi mrežu i na MQTT broker
- postavljanje stanja osam LED dioda (LED1–LED8) na picoETF
- postavljanje boje RGB LED diode
- očitavanje stanja četiri tastera (T1–T4) na picoETF

Aplikacija sa sistemom komunicira putem JSON poruka preko MQTT-a. Komande za postavljanje LED dioda i boje RGB LED uređaj prima na odgovarajućem topic-u, a stanje tastera objavljuje (npr. pri promjeni stanja) na drugom topic-u. Format JSON poruka definišu studenti, uz uslov da MCP server i picoETF koriste isti format.

Nakon što je uređaj funkcionalan, kroz dijalog sa agentom (uz odgovarajuće proširenje MCP servera, ako je potrebno) omogućiti da agent:

- postavi proizvoljnu kombinaciju upaljenih LED dioda
- postavi zadanu boju RGB LED
- očita i izvijesti o trenutnom stanju tastera

> **Hint:** U radnom okruženju se nalazi kostur MCP servera (primjer `mcp_server.py`), koji već sadrži funkcije za slanje JSON komandi i čitanje JSON podataka sa custom uređaja. Ovaj kostur je polazna tačka — proširite ga funkcijama specifičnim za vaš uređaj (npr. postavljanje LED maske, postavljanje RGB boje, čitanje tastera).

> **Hint:** Prije uključivanja agenta, ispravnost MQTT komunikacije uređaja se može provjeriti "ručno", pomoću priloženih skripti `mqtt_listen.sh` (osluškivanje poruka) i `mqtt_send.sh` (slanje poruka). Ako uređaj ispravno reaguje na ručno poslane poruke, problem u radu sa agentom je tada u MCP serveru ili u dijalogu, a ne u samom uređaju.

### Zadatak 3 — Prijedlozi za samostalan rad

Sljedeći zadaci su dati kao ideje — svaki tim bira jednu (ili predlaže vlastitu) i razrađuje je. Cilj je iskoristiti agentski pristup tamo gdje on donosi stvarnu vrijednost: kombinovanje više uređaja, kontekstualno odlučivanje i interpretacija podataka, a ne puko proslijeđivanje komandi.

- **Pravila i scenariji.** Podučiti agenta pravilima ponašanja sistema, npr.: ako temperatura sa DHT11 prađe zadanu vrijednost, uključi relej (ventilator); ako padne ispod druge granice, isključi ga. Pravila se zadaju kroz dijalog, prirodnim jezikom.
- **Scene osvjetljenja.** Definisati imenovane "scene" za LED diode i RGB LED na picoETF (npr. "radni režim", "opuštanje", "alarm"), pa ih aktivirati jednostavnim zahtjevom agentu (*"Uključi scenu opuštanje"*).
- **Komandni panel na tasterima.** Iskoristiti četiri tastera (T1–T4) picoETF kao fizički komandni panel kojim se pokreću dejstva u sistemu (npr. T1 pali sve releje, T2 ih gasi, T3 traži od agenta izvještaj o stanju sistema). Agent prati stanje tastera i reaguje na promjene.
- **Izvještavanje i dnevnik.** Zatražiti od agenta da periodično bilježi očitanja senzora i da na zahtjev pripremi sažetak (npr. *"Kakva su bila kretanja temperature u proteklom periodu?"*), uz tumačenje trenda.
- **Glasovni/udaljeni pristup.** Iskoristiti Telegram gateway za upravljanje sistemom na daljinu, tako da se sva gornja dejstva mogu izvesti porukama putem Telegram-a.
- **Kombinovani scenariji.** Povezati Tasmota uređaj i picoETF u jedinstven scenario, npr.: očitanje DHT11 sa Tasmota uređaja utiče na boju RGB LED na picoETF (topliji ambijent → topliji ton boje).

> **Hint:** Pri razradi vlastite ideje, vodite računa da težište bude na onome što agent radi bolje od fiksne logike: razumijevanje zahtjeva na prirodnom jeziku, kombinovanje više izvora podataka i donošenje odluka na osnovu konteksta.

---

## Odabir teme projekta

Studenti sami formulišu konkretnu temu projekta, ali tema mora biti zasnovana na korištenju Hermes Agenta kao osnovnog načina interakcije sa sistemom. Projekat treba predstavljati agentski IoT sistem u kojem korisnik putem prirodnog jezika zadaje zahtjeve, a Hermes Agent, korištenjem odgovarajućih MCP funkcija i MQTT komunikacije, izvršava radnje nad krajnjim uređajima ili očitava njihovo stanje.

Tema projekta može obuhvatiti:

- realizaciju funkcija pametnog doma, kao što su upravljanje rasvjetom, relejima, senzorima temperature i vlažnosti ili drugim aktuatorima
- povezivanje Tasmota uređaja sa Hermes Agentom
- realizaciju custom uređaja zasnovanog na picoETF platformi i MicroPython aplikaciji
- kombinovanje više krajnjih uređaja u jedan zajednički scenario
- definisanje pravila i scenarija rada kroz dijalog sa agentom
- izvještavanje o stanju sistema na osnovu očitanih senzorskih podataka
- udaljeni pristup agentu, npr. korištenjem Telegram gateway-a
- vlastitu ideju tima, ukoliko je usklađena sa ciljevima projektnog zadatka

Projekat se može realizirati korištenjem:

- opreme dostupne u laboratoriji
- Tasmota uređaja zasnovanih na ESP32 platformi
- picoETF platforme sa Raspberry Pi Pico W mikrokontrolerom
- vlastitih senzora, aktuatora ili mikrokontrolerskih platformi, uz prethodni dogovor sa predmetnim nastavnikom ili asistentom
- kombinacije prethodno navedenih mogućnosti

Bez obzira na izabranu temu, u projektu mora biti jasno vidljiva uloga Hermes Agenta. Projekat ne treba biti sveden samo na ručno slanje MQTT poruka ili na klasičnu mikrokontrolersku aplikaciju. Težište treba biti na tome da agent razumije zahtjeve zadane prirodnim jezikom, koristi definisane alate i komunicira sa krajnjim IoT uređajima.

Prilikom ocjenjivanja posebno će se vrednovati originalnost ideje, kvalitet integracije Hermes Agenta, jasnoća MCP funkcija, stabilnost MQTT komunikacije i sposobnost tima da objasni način rada realiziranog sistema.

---

## Opšta pravila i upute

### Opšta pravila

- Izrada projekta nije obavezna.
- Projekat realiziraju timovi od po tri studenta. Studenti sami formiraju timove.
- Broj članova tima može biti manji od tri, a maksimalno četiri, uz prethodni dogovor sa predmetnim nastavnikom.
- Projekat se boduje sa maksimalno **10 bodova** po članu tima, u zavisnosti od kvaliteta predložene ideje, tehničke realizacije, integracije Hermes Agenta, dokumentacije i demonstracije rada.
- Članovi istog tima mogu dobiti različit broj bodova, u zavisnosti od individualnog doprinosa u realizaciji projekta.
- Studenti sami predlažu konkretnu temu projekta, ali tema mora biti zasnovana na korištenju Hermes Agenta kao osnovnog načina interakcije sa sistemom.
- Projekat treba uključivati krajnji IoT uređaj ili više krajnjih uređaja koji komuniciraju putem MQTT protokola.
- Ključni dio projekta nije samo realizacija IoT uređaja, nego integracija tog uređaja sa Hermes Agentom, tako da se upravljanje i očitavanje stanja sistema vrši kroz dijalog prirodnim jezikom.
- Direktno slanje MQTT komandi može se koristiti za testiranje sistema, ali konačna demonstracija projekta mora pokazati rad sistema kroz Hermes Agent i odgovarajuće MCP funkcije.
- Specifikaciju projekta, sa naznačenim nazivom projekta, članovima tima i opisom planirane realizacije, potrebno je dostaviti prije početka izrade projekta (do naznačenog roka).
- Konačna verzija projekta predaje se kao arhiva koja sadrži izvorni kod, konfiguracione fajlove, dokumentaciju, korisnička uputstva, specifikaciju projekta i link na video demonstraciju.
- Realizirane projekte je potrebno prezentirati. Tokom prezentacije članovi tima trebaju pokazati razumijevanje vlastitog dijela realizacije.

### Rokovi

| Stavka | Rok |
|--------|-----|
| Predaja specifikacije projekta | **05.06.2026. u 23:59** |
| Predaja konačne verzije projekta | **26.06.2026. u 23:59** |

Nakon isteka roka za predaju konačne verzije projekta, svaka započeta sedmica kašnjenja umanjuje maksimalni mogući broj bodova za **2 boda**.

### Minimalni uslovi za prihvatanje projekta

Da bi projekat bio prihvaćen za bodovanje, mora ispuniti sljedeće minimalne uslove:

1. Projekat mora koristiti Hermes Agent kao osnovni način interakcije sa sistemom.
2. Mora postojati barem jedan funkcionalan krajnji IoT uređaj koji komunicira putem MQTT protokola.
3. Mora postojati MCP server ili odgovarajuće MCP funkcije preko kojih Hermes Agent pristupa krajnjem uređaju.
4. Mora biti moguće demonstrirati barem jednu funkcionalnost kroz dijalog sa agentom.
5. Mora biti predata osnovna dokumentacija sa opisom pokretanja, korištenja i testiranja sistema.

Projekat koji se zasniva isključivo na ručnom slanju MQTT poruka, bez stvarne upotrebe Hermes Agenta, ne može dobiti visok broj bodova, čak i ako krajnji uređaji tehnički rade.

---

## Način bodovanja

Projekat se boduje sa maksimalno 10 bodova po članu tima.

| Stavka | Bodovi |
|--------|--------|
| Specifikacija i razrada projektne ideje | 1.0 |
| Realizacija krajnjih IoT uređaja i MQTT komunikacije | 2.0 |
| Integracija Hermes Agenta i MCP servera | 2.0 |
| Agentska logika, scenariji i kvalitet dijaloga | 2.0 |
| Testiranje, pouzdanost i obrada grešaka | 1.0 |
| Dokumentacija implementacije i korisnička uputstva | 1.0 |
| Video demonstracija i prezentacija projekta | 1.0 |
| **Ukupno** | **10.0** |

### Detaljni kriteriji bodovanja

#### 1. Specifikacija i razrada projektne ideje (1.0 bod)

Specifikacija treba sadržavati:

- naziv projekta
- imena i prezimena članova tima
- kratak opis problema ili scenarija koji se realizira
- opis korištenih krajnjih uređaja
- planirane MQTT topic-e i osnovni format poruka
- opis MCP funkcija koje će agent koristiti
- opis očekivanog načina komunikacije korisnika sa agentom
- plan demonstracije projekta

Maksimalan broj bodova dobija specifikacija koja je jasna, tehnički realna i dovoljno detaljna da se na osnovu nje može procijeniti složenost projekta.

#### 2. Realizacija krajnjih IoT uređaja i MQTT komunikacije (2.0 boda)

Posebno se boduje:

- ispravno povezivanje uređaja na WiFi mrežu
- ispravna konfiguracija MQTT komunikacije
- objavljivanje i prijem MQTT poruka na odgovarajućim topic-ima
- funkcionalnost senzora, aktuatora, LED dioda, RGB LED diode, tastera ili drugih korištenih komponenti
- korištenje jasnog i dosljednog formata poruka, posebno ako se koristi JSON
- mogućnost ručne provjere komunikacije prije uključivanja Hermes Agenta

#### 3. Integracija Hermes Agenta i MCP servera (2.0 boda)

Posebno se boduje:

- ispravno pokretanje i konfiguracija Hermes Agenta
- ispravno povezivanje agenta sa LLM modelom
- postojanje MCP servera ili proširenje postojećeg kostura MCP servera
- jasno definisane MCP funkcije koje agent može koristiti
- ispravno povezivanje MCP funkcija sa MQTT topic-ima
- razumljivi nazivi funkcija, parametara i povratnih vrijednosti
- mogućnost da agent kroz dijalog izvršava stvarne radnje na krajnjim uređajima

#### 4. Agentska logika, scenariji i kvalitet dijaloga (2.0 boda)

Posebno se boduje:

- mogućnost upravljanja sistemom prirodnim jezikom
- jasno definisani scenariji rada
- sposobnost agenta da poveže više koraka u jednu smislenu radnju
- korištenje očitanih podataka pri donošenju odluka
- kombinovanje više uređaja u jednom scenariju
- mogućnost zadavanja pravila kroz dijalog
- kvalitet formulisanih zahtjeva prema agentu i način na koji agent odgovara korisniku

#### 5. Testiranje, pouzdanost i obrada grešaka (1.0 bod)

Potrebno je dokumentovati:

- ručnu provjeru MQTT komunikacije
- testiranje rada krajnjih uređaja
- testiranje MCP funkcija
- testiranje rada kroz dijalog sa Hermes Agentom
- uočene probleme i način njihovog rješavanja
- poznata ograničenja realiziranog sistema

#### 6. Dokumentacija implementacije i korisnička uputstva (1.0 bod)

Dokumentacija treba sadržavati:

- opis arhitekture realiziranog sistema
- opis korištenih uređaja i komponenti
- opis MQTT topic-a i formata poruka
- opis MCP funkcija
- način pokretanja sistema
- način korištenja sistema kroz Hermes Agent
- kratko korisničko uputstvo pisano razumljivo i netehničkom korisniku

#### 7. Video demonstracija i prezentacija projekta (1.0 bod)

Video demonstracija treba prikazati:

- pokretanje ili već pokrenut rad sistema
- komunikaciju korisnika sa Hermes Agentom
- reakciju krajnjih IoT uređaja
- barem jedan cjelovit agentski scenario
- kratko objašnjenje šta je realizirano

---

## Način predaje projekta

Specifikacija projekta se predaje kao zaseban PDF dokument putem sistema za predaju zadataka.

Konačna verzija projekta predaje se kao jedna `.zip` arhiva koja sadrži:

- izvornu specifikaciju projekta
- izvorni kod za custom krajnje uređaje, npr. MicroPython kod za picoETF
- konfiguraciju Tasmota uređaja, ukoliko se koristi Tasmota uređaj
- izvorni kod MCP servera i eventualne dodatne skripte
- sve konfiguracione fajlove potrebne za pokretanje sistema
- dokumentaciju implementacije u PDF formatu
- korisnička uputstva
- tekstualni fajl sa linkom na video demonstraciju

Predani materijali trebaju biti dovoljni da druga osoba, uz dostupnu laboratorijsku opremu i radno okruženje, može rekonstruisati i pokrenuti realizirani sistem.

---

## Informacije/pitanja

Za sve dodatne informacije možete kontaktirati predmetnog nastavnika.

---

## Literatura

1. Nous Research, *Hermes Agent — Dokumentacija*
2. Tasmota, *Tasmota Documentation*
3. *MicroPython Documentation*
4. *MQTT — The Standard for IoT Messaging*
