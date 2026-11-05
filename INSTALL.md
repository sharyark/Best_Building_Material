# Hisaab Portal: Install Guide (Roman Urdu)

Ye guide client ke PC par Hisaab Portal chalane ke liye hai. App usi PC par chalti hai:
sirf **database** Docker mein, aur **API** aur **website** seedha PC par.

```
Browser ──► Website :5173 ──► API :8000 ──► [Docker: database]
```

---

## 1. Kya install karna hai (sirf ek dafa)

| Cheez | Kahan se | Dhyan rahe |
|---|---|---|
| **Docker Desktop** | https://www.docker.com/products/docker-desktop/ | Install ke baad PC restart. Docker Desktop khol kar "Engine running" ka intezar karein. |
| **Python 3.12** | https://www.python.org/downloads/ | Install ke pehle screen par **"Add python.exe to PATH"** zaroor tick karein. |
| **Node.js 20 LTS** | https://nodejs.org | Seedha "Next, Next" se install. |
| **Git** | https://git-scm.com | Code lene aur update karne ke liye. |

---

## 2. Code PC par rakhein

PowerShell khol kar:

```powershell
cd C:\
git clone <repo ka link> hisaab
cd hisaab
```

Aage ki saari commands isi `C:\hisaab` folder mein chalani hain.

---

## 3. Owner ka login set karein (app pehli dafa chalane se PEHLE)

1. `backend` folder mein `.env.example` ki copy banayein aur naam **`.env`** rakhein.
2. `backend\.env` Notepad mein khol kar ye lines badlein:

```
BOOTSTRAP_ADMIN_NAME=Owner ka naam
BOOTSTRAP_ADMIN_PHONE=owner ka phone ya username
BOOTSTRAP_ADMIN_PASSWORD=mazboot password
JWT_SECRET=koi bhi lambi random line (kam az kam 32 harf)
```

Ye login sirf **pehli dafa**, khaali database par banta hai. Baad mein `.env` badalne se login nahi badalta.

---

## 4. App chalayein

**`dev_without_data.bat`** par double-click.

- Pehli dafa packages install hote hain: 5 se 10 minute.
- Do nayi windows khulti hain: **"Hisaab API"** aur **"Hisaab Web"**. Inhein **khula rakhein**; band kiya to app band.
- Browser khud khulta hai: http://127.0.0.1:5173/admin/login

> Hamesha **`dev_without_data.bat`** chalayein. **`dev.bat` kabhi nahi**: woh khaali database mein demo data (nakli customer, challan) daal deta hai.

---

## 5. Pehle din (sirf ek dafa)

Owner login se:

1. **Admin > Users**: munshi ka login banayein.
2. **Masters**: maal, gaadiyan, driver/staff, customer, supplier.
3. **Admin > Opening balances**: purane register ka baqaya (cash, udhaar, yard ka maal).

Tafseel [`MANUAL.md`](MANUAL.md) ke "Pehla din" hisse mein.

---

## 6. Roz ka istemal

| Kab | Kya karein |
|---|---|
| Subah | Docker Desktop chalne dein, phir `dev_without_data.bat` par double-click |
| Din bhar | "Hisaab API" aur "Hisaab Web" windows khuli rehne dein (minimize kar sakte hain) |
| Shaam | Dono windows band karein. Data mehfooz rehta hai. |

PC restart hua ho to bhi yahi: Docker Desktop, phir `dev_without_data.bat`.

Munshi: http://127.0.0.1:5173/accountant/login (sirf isi PC se khulta hai).

---

## 7. Backup (bohat zaroori)

Backup **khud nahi** hota. **Roz shaam** kaam khatam karke **`backup.bat`** par double-click karein (app khuli ho to bhi chalega).

- Saare data ki copy (shuru se us waqt tak) `C:\hisaab\backups\hisaab-2026-11-05_1830.dump` jaisi file mein ban jati hai.
- Har backup **poori** copy hai. Phir bhi purani files kaam ki hain: koi ghalti der se pata chale to us se pehle ke din par wapas ja sakte hain.
- **28 din se purani** files khud mit jaati hain; sab se nayi **4** hamesha rehti hain.
- Hafte mein ek dafa `backups` folder ki nayi file **USB ya Google Drive** par copy karein. Sirf isi PC par rahi to PC kharab hone par backup bhi gaya.

### Backup wapas daalna (sirf zaroorat par)

1. "Hisaab API" aur "Hisaab Web" windows band karein (Docker Desktop chalta rahe).
2. **`restore.bat`** par double-click. Backup files ki list aati hai (sab se nayi upar); number likh kar Enter.
   Ya backup file ko seedha `restore.bat` par **drag** karein.
3. Woh poochti hai "Pakka?": **`haan`** likh kar Enter.
4. Phir `dev_without_data.bat` chalayein.

`restore.bat` khud:
- pehle file check karti hai (kharab ho to kuch nahi chhedti),
- **abhi ke data ka backup** `backups` mein bana leti hai (ghalat file chuni ho to usi se wapas aa sakte hain),
- daalti "sab ya kuch nahi" hai: beech mein masla aaye to database pehle jaisa rehta hai.

Database backup ke waqt par wapas chala jata hai; us ke baad ki entries hat jaati hain. **Login bhi backup wale** aate hain.

### Naye PC par purana data laana

1. Naye PC par section 1 se 4 tak sab karein (install, clone, `.env`, `dev_without_data.bat`). Database khaali banega.
2. App ki dono windows band karein.
3. Purane PC ki backup file (USB / Drive se) naye PC ke `C:\hisaab\backups` folder mein rakhein (folder na ho to bana lein).
4. `restore.bat` par double-click, file chunein, `haan`.
5. `dev_without_data.bat` chalayein aur **purane login** se andar jayein.

---

## 8. Naya update aaye to

1. "Hisaab API" aur "Hisaab Web" windows band karein.
2. Pehle `backup.bat` se backup lein (section 7).
3. `C:\hisaab` mein: `git pull`
4. `dev_without_data.bat` par double-click. Database ke naye badlaav khud lag jaate hain.

---

## 9. Kabhi na karein

| Command | Kyun nahi |
|---|---|
| `docker compose -f docker-compose.dev.yml down -v` | `-v` se **saara hisaab mit jata hai** |
| `docker volume rm ..._devdata` | Wahi: saara data mit jata hai |
| `dev.bat` | Demo data daal deta hai |

---

## 10. Masla aaye to

| Masla | Hal |
|---|---|
| "Docker is not running" | Docker Desktop kholein, "Engine running" ka intezar, phir dobara double-click |
| "Python 3.12 was not found" | Python dobara install karein, "Add python.exe to PATH" tick karke |
| Page nahi khulta | "Hisaab API" aur "Hisaab Web" windows khuli hain? Nahi to `dev_without_data.bat` dobara |
| Login nahi hota | 1 minute mein 5 se zyada ghalat koshish par app rok deti hai; 1 minute ruk kar dobara |
| Kuch aur | "Hisaab API" window ki aakhri lines ki photo developer ko bhejein |
