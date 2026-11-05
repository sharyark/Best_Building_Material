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

Is tareeqe mein backup **khud nahi** hota. Har hafte (ya roz shaam) haath se lein. App chal rahi ho to bhi le sakte hain.
`C:\hisaab` folder mein PowerShell:

```powershell
docker compose -f docker-compose.dev.yml exec -T db pg_dump -U hisaab -Fc -f /tmp/hisaab-backup.dump hisaab
docker compose -f docker-compose.dev.yml cp db:/tmp/hisaab-backup.dump .\backup-2026-11-05.dump
```

File ke naam mein us din ki tareekh likhein. Ye file **USB ya Google Drive** par bhi copy karein; sirf isi PC par rahi to PC kharab hone par backup bhi gaya.

### Backup wapas daalna (sirf zaroorat par)

Pehle "Hisaab API" window band karein. Phir:

```powershell
docker compose -f docker-compose.dev.yml cp .\backup-2026-11-05.dump db:/tmp/restore.dump
docker compose -f docker-compose.dev.yml exec -T db pg_restore -U hisaab -d hisaab --clean --if-exists --no-owner /tmp/restore.dump
```

Phir `dev_without_data.bat` dobara chalayein. Is se database **backup wale din par wapas** chala jata hai; us ke baad ki entries chali jati hain.

---

## 8. Naya update aaye to

1. "Hisaab API" aur "Hisaab Web" windows band karein.
2. Pehle backup lein (section 7).
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
