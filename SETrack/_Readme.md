# Implementing UI/UX with Figma and Tkinter - Code Sinaia 2026

Ghid de lucru pentru sesiunea de azi. Linkurile către resurse (repo Tkinter Designer, fișierele Figma etc.) sunt în `links.md`.

## 0. Setup dimineața

```bash
git pull inproted main
pip install -r SETrack/requirements.txt
```
### For linux users, install Tkinter:
```bash
sudo apt install python3-tk
```

### For MAC users, install Tkinter:
```bash
brew install python-tk
```

## Steps (Phase 1)

1. Duplicate to your own account
2. Work on Login Screen
3. Work on SignUp Screen
4. Work on Main Screen

## 2. Figma → Tkinter Designer → Python
1. Open Figma file (see links.md)
2. Click on the "Share" button in the top right corner of the Figma interface.
3. In the sharing dialog, click on "Copy link" to copy the URL of the Figma file to your clipboard.
4. Open Tkinter Designer (see links.md)
5. In Tkinter Designer, paste the copied Figma file URL into the "File URL" field.
6. Click on the "Generate" button to start the conversion process. Tkinter Designer will analyze the Figma file and generate the corresponding Python code for the UI.

## 3. De la Figma la Tkinter Designer (Phase 2)
```bash
git clone <repo>          # vezi links.md
cd <repo>
pip install -r requirements.txt   # sau: install dependencies
```

Generare Figma access token:
1. Cont Figma → **Settings → Security → Personal access tokens**
2. **Generate new token** → dai un nume, alegi expirare (ex. 7 zile)
3. Bifezi scope-urile necesare (`TOATE`)
4. Copiezi tokenul (nu se mai poate vedea după ce închizi fereastra)

În Tkinter Designer:
- **Token ID** = tokenul generat mai sus
- **File URL** = link-ul către fișierul tău Figma (din `links.md`)
- **Output Path** = unde vrei să genereze `gui.py` + `assets/`
- Apeși **Generate**

## 4. Arhitectura unei aplicații desktop

Orice aplicație desktop are (cel puțin) trei responsabilități diferite. Nu le amestecăm niciodată în același loc:

| Strat | Rol | La noi |
|---|---|---|
| **UI** | Ferestre, butoane, culori — ce vede și atinge utilizatorul | Tkinter / `gui.py` |
| **Logică** | Ce se întâmplă la un click — validări, stare locală | `main.py` |
| **Rețea** | Trimite/primește date către server | `network_client.py` — **nu-l atingem azi** |

De ce contează separarea? UI-ul se poate schimba (alt design Figma) fără să atingem logica; rețeaua se poate schimba (alt server) fără să atingem UI-ul.

Azi lucrăm aproape exclusiv la UI, cu apeluri clare către Logică — fără să ne pese cum ajunge un mesaj la celălalt calculator.

## 5. MVC / MVP — separarea are un nume

Separarea UI / Logică / Rețea are un nume în literatura de specialitate: **MVC** (Model-View-Controller) sau varianta ei **MVP** (Model-View-Presenter).

- **Model** — datele și regulile aplicației (lista de prieteni, mesajele, cine e online). La noi: ce ține `conversation_store.py`.
- **View** — ce vede utilizatorul: ferestrele generate de Tkinter Designer din Figma (`gui.py`). View-ul nu ia decizii, doar afișează și raportează click-uri.
- **Controller / Presenter** — orchestratorul dintre ele: primește click-ul din View, cere/schimbă date din Model, spune View-ului ce să afișeze. La noi: `main.py`.

Nu trebuie să memorați numele — trebuie să recunoașteți *tiparul* data viitoare când vedeți un proiect organizat pe straturi.

## 6. Event loop: cum "gândește" Tkinter

Tkinter nu rulează cod "de sus în jos"; după `window.mainloop()`, controlul trece la un ciclu infinit de evenimente:

1. **Așteaptă** — un click, o tastă, un timer
2. **Identifică** — ce widget a fost atins
3. **Apelează** — callback-ul (`command=`)
4. **Actualizează** — UI-ul, apoi așteaptă din nou

De asta callback-urile trebuie să fie scurte; un callback blocat (ex. un `recv()` care așteaptă rețeaua) îngheață toată fereastra.

## 7. Cum legăm UI-ul de funcții

Tkinter Designer generează un `gui.py` cu butoane care nu fac nimic încă. Legătura se face mereu în 2 pași:

1. **Scrii funcția** care trebuie să ruleze la click (în `main.py`, nu în `gui.py`).
2. **Legi butonul de ea:** fiecare buton generat de Tkinter Designer are un atribut `.configure(command=numele_functiei)`.

**Atenție:** `command` primește *numele* funcției, nu rezultatul apelării ei; greșeala clasică e `command=functie()` (execută imediat, nu la click) — corect e `command=functie`.

Pentru câmpuri de tip Entry/Text peste canvas-ul desenat, se folosește `.place(x, y, width, height)` cu coordonatele măsurate direct din Figma.

## 8. Arhitectura My Own WhatsApp

```
login/, signup/, main/ (gui.py)   →   main.py                          →   network_client.py
Exportate direct din Figma,            Orchestratorul: leagă ecranele        socket + criptare
NU le modificăm                        de coordonate, navigare și
                                        callback-uri.
                                        TODO: aici lucrăm azi.
                                             ↑
                                        conversation_store.py
                                        cache local de mesaje, preview imagini
                                        TODO: 2 funcții de decriptare aici
```

## 9. Ce construiți azi

Porniți din `whatsapp_todo` — un schelet funcțional cu placeholdere de completat:

- [ ] **Coordonate din Figma** → 8 câmpuri de poziționat (login, search bar, listă prieteni, conversație, mesaj) în `main.py`.
- [ ] **Navigare între ecrane** — login ↔ signup ↔ main, completând ramurile lipsă de dispatch.
- [ ] **Status online/offline** — un `if` simplu care alege culoarea verde/roșu — feedback vizual = UX.
- [ ] **Legarea de criptare/decriptare** — apelați funcțiile deja scrise (`encrypt_text`/`decrypt_text`) din `network_client.py`, la momentul potrivit.

### Cum rulați

```bash
python myserver.py        # într-un terminal
python main.py            # în alt terminal, pentru fiecare user
```

## 10. Task-uri bonus

Ați terminat mai repede? 

```
Ask the instructor
```

## 11. Bonus: cum convertești .py în .exe

Folosim `auto-py-to-exe`:

```bash
pip install auto-py-to-exe
auto-py-to-exe
```

Avantaje: open-source, UI intuitiv, poți salva configurația.

---

*2026 Copyright © by INPROTED — International Professionals for Technology and Education | All Rights Reserved*