# Hisaab Portal: Asaan Manual (Roman Urdu)

Ye manual batata hai ke app kaise chalti hai: client shuru mein kya kare, roz kya kare, aur hisaab kaise banta hai.
Har baat ek chhoti si misaal se samjhai gayi hai: **1 customer, 1 supplier, 1 tractor, 1 driver, 1 mazdoor, 1 maal (ret)**.

---

## 1. App kya karti hai

Pehle sab kuch register (kaghaz) par likha jata tha: customer ka khata, supplier ka hisaab, yard ka maal, diesel,
driver ki tankhwah. Ye app wahi kaam karti hai, lekin **ek entry se sab jagah hisaab khud update ho jata hai**.

Misaal: munshi ne ek challan banaya (3 trolley ret). Is ek entry se khud ba khud:

- customer ke khata mein 3 trolley ki rakam jud gayi,
- yard mein ret 3 trolley kam ho gayi,
- driver ke khata mein 3 trip ke paise jud gaye,
- munafe ki report mein ye sale aa gayi.

Kahin dobara likhne ki zaroorat nahi.

### Do log, do darwaze

| Kaun | Kahan se login | Kya kar sakta hai |
|---|---|---|
| **Owner (malik)** | `/admin/login` | Sab kuch: entries, munafa, users, opening balance, mahina band karna, entry cancel (void) |
| **Munshi** | `/accountant/login` | Roz ki entries aur unki durusti. Munafa nahi dekh sakta, entry cancel nahi kar sakta |

Demo logins: owner `admin / admin12345`, munshi `munshi / munshi12345`.

---

## 2. Chhota demo chalayein

Ye demo sirf ek hafte ka hai, taake har number haath se check ho sake.

```bash
cd backend
source .venv/bin/activate
python -m app.seed --reset --small     # purana data mita kar chhota demo daalta hai
cd .. && ./dev.sh                     # app chalayein, phir http://127.0.0.1:5173 kholein
```

> `--reset` database ka **saara data mita deta hai**. Sirf apne computer ke test database par chalayein, asal dukaan ke data par kabhi nahi.

Bara demo (45 din, 8 customers) wapas chahiye ho to: `python -m app.seed --reset`.

---

## 3. Pehle din: client shuru mein kya kare (Owner)

App chalane se pehle teen kaam ek dafa hote hain.

### Qadam 1: Masters (cheezon ke naam)

**Masters** screen par ye sab daalein:

| Kya | Demo mein | Kyun zaroori |
|---|---|---|
| Maal (Material) | Rait (Sand), unit: trolley, bechne ka rate 3,300, khareedne ka 2,000 | Challan aur purchase mein yahi chuna jata hai |
| Customer | Ali Builders, site: Plot 12 | Is ka khata banta hai |
| Supplier | Crusher X | Is ka hisaab banta hai |
| Gaadi (Vehicle) | Tractor-1 | Har gaadi ka alag kharcha/munafa |
| Staff: driver | Aslam, mahana 15,000, **trip rate 200**, gaadi: Tractor-1 | Tankhwah aur trip ka hisaab |
| Staff: mazdoor | Raju, roz ki dihari 900 | Haazri se mazdoori |

**Ek maal ki kai types (misaal cement):** har type alag maal banayein, apne naam aur rate ke saath: "Cement - OPC", "Cement - SRC", "Cement - White". Teeno mein **Group** "Cement" likhein. Challan par list mein sirf "Cement" aata hai; chunte hi "Cement type" ka khana aata hai, aur type chunte hi us ka rate lag jata hai. Har type ka stock alag rehta hai. Naam ya rate Masters se badal sakte hain.

**Driver aur gaadi ka rishta:** ek gaadi ke saath sirf ek driver juda hota hai, aur ye sirf Masters se badalta hai.
Challan par gaadi chuno to us ka driver khud aa jata hai aur badla nahi ja sakta.
Agar wo driver us din **absent** ho, tab sirf woh drivers chune ja sakte hain jo kisi gaadi se jure nahi. Koi na ho to wahin "temporary driver" add ho sakta hai.

### Qadam 2: Opening balance (purane register ka baqaya)

Jis din app shuru ho (misaal "Din 0"), us din tak purane register mein jo baqaya tha, woh **Admin > Opening balances** mein daalein:

| Kya | Demo mein | Matlab |
|---|---|---|
| Cash (galla) | 50,000 | Galle mein itne paise hain |
| Ali Builders | 20,000 (lena hai) | Customer ne purana udhaar dena hai |
| Crusher X | 10,000 (dena hai) | Hum ne supplier ko dena hai |
| Yard ka maal | Ret 5 trolley @ 2,000 = 10,000 | Yard mein pehle se para maal |

Ye sirf **ek dafa** hota hai. Galti ho to dobara daal dein; naya amount purane ki jagah le leta hai.

### Qadam 3: Munshi ka login

**Admin > Users** mein munshi ka user banayein. Ab roz ka kaam munshi karega.

---

## 4. Roz ka kaam (Munshi)

| Kaam | Screen | Kya hota hai |
|---|---|---|
| Maal bika | **Challans** | Customer ka khata barhta hai, yard ka maal ghatta hai, driver ke trip jurte hain |
| Maal aaya | **Purchases** | Supplier ka hisaab barhta hai, yard ka maal barhta hai |
| Paise mile | **Payments > New receipt (money in)** | Customer ka khata ghatta hai, cash barhta hai |
| Paise diye | **Payments > New payment (money out)** | Supplier/staff ka hisaab ghatta hai, cash ghatta hai |
| Raat ka khana | Dashboard > **Khana (food)** (ya Expenses > Khana) | Rakam likhein; galle (cash) se kat-ta hai aur "Food (khana)" ke kharche mein jata hai |
| Fuel / kharcha | **Expenses & diesel** | Cash ghatta hai (ya pump ka udhaar barhta hai), gaadi ka kharcha barhta hai |
| Haazri | **Labour & wages** | Dihari wale mazdoor ki mazdoori khud jurti hai |

### Dashboard: kisi bhi din ka hisaab

Dashboard ke "Today" wale hisse mein tareekh chunein. Us din ke **Trips, Sales, Money received, Money paid out** aa jaate hain. Har dabba click hota hai:

- **Trips / Sales** → us din ke challan.
- **Money received** → us din aaya har paisa, ek ek line (customer ki wasooli, mauqe ka cash...).
- **Money paid out** → us din gaya har paisa (supplier, diesel, tankhwah, trip money...). Neeche ka jama dabbe ke number ke barabar hota hai.

"Today" button se wapas aaj par aa jaate hain.

### Gaadi ko fuel dena

**Expenses & diesel > Fuel entry**: gaadi chunein, **litre** aur **rate per litre** likhein. Rakam khud banti hai (40 L × 280 = 11,200), aur pichla rate pehle se bhara aata hai.

- Pump se udhaar ho to "On credit (pump)" aur pump chunein. Rakam pump ke khata mein jurti hai.
- Hafte ya mahine baad pump ko ikattha paisa dein: **Payments > New payment**, pump chunein. Pump ka khata utna kam ho jata hai.
- **Reports > Fuel**: har gaadi ne kitne litre liye, kitne paise, aur average rate. "By pump" se har pump ka hisaab.

### Challan par trip kaise gine jaate hain

Trip pay har gaadi par lagta hai: tractor, dumper aur loader.

- **Challan (khula maal):** jitni trolley, dumper ya loader bucket, utne trip. 3 trolley = 3 trip. Half load bhi ek trip.
- **Challan (bags ya blocks):** poora challan 1 trip, chahe 50 bags hon.
- **Purchase (apni gaadi supplier se maal laye):** jitni trolley laye, utne trip.
- **Rental (machine kiraye par):** "per trip" ho to jitne trip, warna (ghante ya din) 1.
- **Trip pay** = trip × driver ka rate (3 × 200 = 600). Ye khud bhar jata hai; munshi chahe to badal sakta hai.
- **Jis kaam ke trip ke paise nahi bante,** munshi trip pay **0** rakh de. Koi rakam nahi judegi.

### Khata ke alfaaz

| Khata | Columns | Baqaya |
|---|---|---|
| Customer | **Bill** (maal diya) · **Wasool** (paise mile) | "14,900 **lena**" = customer ne dena hai |
| Supplier / pump | **Pay** (paise diye) · **Bill** (maal liya) | "10,000 **dena**" = hum ne dena hai |
| Staff | **Pay** (diya / advance) · **Kamai** (tankhwah, trip) | lena = advance zyada, dena = un ka baqi |

---

## 5. Misaal: ek hafte ka poora hisaab

Demo mein ye entries hain. Har din ke saath dekhein ke kis ka hisaab kaise badla.

| Din | Entry | Customer (Ali) | Supplier (Crusher X) | Cash | Yard (ret) |
|---|---|---|---|---|---|
| 0 | Opening balance | 20,000 lena | 10,000 dena | 50,000 | 5 trolley |
| 1 | Purchase: 10 trolley @ 2,000, udhaar | | +20,000 → 30,000 dena | | +10 → 15 |
| 1 | Raju haazir (900) | | | | |
| 2 | Challan: 3 trolley @ 3,300 = 9,900, udhaar | +9,900 → 29,900 | | | −3 → 12 |
| 2 | Diesel Tractor-1, cash | | | −3,000 → 47,000 | |
| 2 | Raju haazir (900) | | | | |
| 3 | Challan: 2 trolley = 6,600, **mauqe par cash** | +6,600 −6,600 → 29,900 | | +6,600 → 53,600 | −2 → 10 |
| 3 | Aslam ko advance | | | −5,000 → 48,600 | |
| 4 | Ali Builders ne diye | −15,000 → **14,900** | | +15,000 → 63,600 | |
| 4 | Crusher X ko diye | | −20,000 → **10,000** | −20,000 → 43,600 | |
| 5 | Aslam ko hafte ke trip ke paise | | | −1,000 → 42,600 | |
| 5 | Raju ko 2 din ki mazdoori | | | −1,800 → **40,800** | |

### Hafte ke aakhir mein

| Kis ka | Baqaya | App mein kahan dekhein |
|---|---|---|
| Ali Builders | **14,900** humein lene hain | Reports > Party khata |
| Crusher X | **10,000** humein dene hain | Reports > Party khata |
| Cash (galla) | **40,800** | Reports > Cash book / bank book |
| Yard | **10 trolley ret**, qeemat 20,000 | Yard stock (ya Reports > Yard stock) |

Dashboard par bhi yahi numbers aate hain: cash 40,800, lena 14,900, dena 10,000, stock 20,000.

---

## 6. Driver ka hisaab: tankhwah alag, trip alag

Aslam ki mahana tankhwah 15,000 hai, aur har trip ke 200 alag milte hain. Poora khata: **Reports > Labour / driver khata**.
Client trip ke paise **har hafte** deta hai aur tankhwah **mahine ke aakhir**. Isliye khata mein dono hisaab alag rakhe jaate hain.

**Trip ka hisaab (is hafte):**

| | Rs |
|---|---|
| Din 2: 3 trolley = 3 trip × 200 | 600 |
| Din 3: 2 trolley = 2 trip × 200 | 400 |
| **Kul trip ke paise** | **1,000** |
| Din 5: hafte ke trip ke paise diye | −1,000 |
| **Trip ka baqaya** | **0** |

**Tankhwah ka hisaab (is mahine):**

| | Rs |
|---|---|
| Mahana tankhwah | 15,000 |
| Din 3: advance liya | −5,000 |
| **Mahine ke aakhir dena hai** | **10,000** |

Trip ke paise de dene se tankhwah wala hissa nahi badalta. Woh 10,000 hi rehta hai.

**Payment karte waqt purpose sahi chunein:**

| Purpose | Kab |
|---|---|
| Advance | Mahine ke beech udhaar (tankhwah se katega) |
| Trip money | Hafte ke trip ke paise |
| Salary / wage payout | Tankhwah ya mazdoori ki adaigi |

**Mahine ke aakhir:** **Labour & wages > Wage settlement** se driver ka mahina settle karein. Tab 15,000 tankhwah khata mein judti hai, aur baqi 10,000 de dein (purpose: Salary).

**Advance hamesha Payments mein darj karein** (Purpose: Advance). Settlement khud wahi advance uthata hai; wahan advance likhne ka khana nahi. Settlement ke baad diya gaya advance naye settlement ke baghair seedha khata mein kat-ta hai. Ek din ka settlement do baar nahi banta; galti ho to Owner purana settlement void karke dobara banaye.

**Tankhwah se katoti (chutti, jurmana...):** settle karte waqt "Katoti" ki rakam ke saath **wajah** chunni zaroori hai: Chutti (absent din), Jurmana, Nuqsan ya Other, aur detail (misaal "2 din"). "Chutti" chunne par mahana staff ki katoti khud ban jati hai: absent din × (tankhwah ÷ 30). Wajah staff khata mein likhi aati hai: "katoti 1,000.00: Chutti: 2 din".

**Raju (dihari wala):** har din "haazir" lagane se 900 khud jurte hain. 2 din = 1,800. Din 5 ko de diye, to baqaya 0.

---

## 7. Munafa kaise nikla (sirf Owner)

**Reports > Profit & loss** (is hafte):

| | Rs |
|---|---|
| Ret bechi (5 trolley × 3,300) | 16,500 |
| Ret ki laagat (5 trolley × 2,000) | −10,000 |
| Diesel | −3,000 |
| Raju ki mazdoori | −1,800 |
| Aslam ke trip | −1,000 |
| **Munafa** | **700** |

Aslam ki 15,000 tankhwah abhi is mein nahi, kyunki woh mahine ke aakhir settle hone par judti hai.

**Gaadi ka hisaab (Reports > Vehicle P&L):** Tractor-1 ke 5 trip, kharcha diesel 3,000 + trip 1,000 = 4,000.
Bhara (freight) nahi liya, isliye gaadi ki apni kamai 0 aur nuqsan 4,000 dikhta hai.
Maal ki bikri gaadi ki kamai nahi ginti. Gaadi ki kamai sirf bhara aur kiraya hai.

---

## 8. Galti ho jaye to

- **Edit:** entry kholein, theek karein, aur **wajah** likhein. Purana hisaab khud ulta hota hai aur naya lagta hai; dono record mein rehte hain.
- **Void (cancel):** sirf Owner kar sakta hai, aur wajah likhna zaroori hai. Entry mitti nahi, "void" ho jati hai, aur us ka hisaab wapas ho jata hai.
- **Delete ka button nahi hai.** Paison ka record kabhi gayab nahi hota.
- **Mahina band (Admin > Month lock):** Owner purana mahina band kar de to us mahine mein koi entry ya badlaav nahi ho sakta.

---

## 9. Yaad rakhne ki baatein

1. **Pehle Masters, phir Opening balance, phir roz ki entries.**
2. Har cheez ki **ek hi entry** karein. Baqi sab app khud karti hai.
3. Trip ke paise dete waqt purpose **"Trip money"** chunein, warna woh tankhwah se kat jayenge.
4. Har shaam **Dashboard** dekh lein: galle ka cash, aaj ke trip, aur kis se paise lene hain.
