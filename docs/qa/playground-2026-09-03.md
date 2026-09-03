# Playground QA — 2026-09-03 20:11

Existing demos only; no demo was created or rebuilt. Same routes the Playground tab calls.

## QA images +hi-IN 17:51 (`dm_f79d9170`) — status ready, v1

- cost panel before: $2.531 over 132 rows; stages ['author', 'plan', 'rehearsal', 'runtime', 'translate', 'understand', 'voice']; per-session None
- ask `What is the battery warranty?` → 5.4s · answered=True · facts=['F034', 'F035'] · callback=False · clarifier=False
  > The battery is covered for three years or fifty thousand kilometres, whichever comes first — that's the written warranty term. The vehicle itself also has a three-year warranty.
- ask `How much does a home charger cost?` → 17.8s · answered=False · facts=['F025', 'F026'] · callback=True · clarifier=False
  > Honestly, I don't have the charger price in the material I have with me, so I won't guess. What I can tell you is that the portable charger plugs into a normal household plug point — the same kind of socket your geyser u
- evals (3 typed) → 24.2s · coverage 0.33 · id ev_1788446553
  - ❌ What is the on-road price in Pune? → facts [] · I'm not sure about that from the material I've been given, so I won't guess. I can have a salesperson call you about it 
  - ✅ Is the battery waterproof? → facts ['F033'] · Yes — the battery packs are sealed against water and dust, and they sit in a strong aluminium casing. That's what the sp
  - ❌ Can I get a test ride this weekend? → facts [] · I'm not sure about weekend slots from the material I have, so I won't guess on timings. What I can do is put you down fo
- eval runs listed: 1 (latest ev_1788446553)
- cost panel after: $2.706 (+$0.174 for this QA) · runtime rows 8

## QA video 18:15 (`dm_78890026`) — status ready, v2

- cost panel before: $2.316 over 98 rows; stages ['author', 'plan', 'rehearsal', 'runtime', 'understand', 'voice']; per-session None
- ask `What is the battery warranty?` → 3.8s · answered=True · facts=['F024', 'F025'] · callback=False · clarifier=False
  > The battery is covered for three years or fifty thousand kilometres, whichever comes first — that's the written warranty term. The vehicle itself also carries a three-year warranty.
- ask `How much does a home charger cost?` → 25.6s · answered=False · facts=[] · callback=True · clarifier=False
  > I'm not sure about that from the material I've been given, so I won't guess. I can have a salesperson call you about it — if you'd like that, just tell me your number, or we can carry on.
- evals (3 typed) → 17.9s · coverage 0.33 · id ev_1788446600
  - ❌ What is the on-road price in Pune? → facts [] · Honestly, I don't have the Pune on-road figure in the material I have, and I won't guess — the taxes and registration pa
  - ✅ Is the battery waterproof? → facts ['F023'] · The battery packs are sealed against water and dust, and they sit in a strong aluminium casing — so normal rain and pudd
  - ❌ Can I get a test ride this weekend? → facts [] · I can't confirm weekend slots from what I have here — that depends on the dealership's own calendar, and I won't guess. 
- eval runs listed: 1 (latest ev_1788446600)
- cost panel after: $2.506 (+$0.190 for this QA) · runtime rows 21

## TVS iQube (`dm_d5675e7f`) — status ready, v1

- cost panel before: $0.111 over 7 rows; stages ['runtime']; per-session None
- ask `What is the battery warranty?` → 8.3s · answered=True · facts=['F027', 'F028', 'F029'] · callback=False · clarifier=False
  > The battery carries a three year or fifty thousand kilometre warranty, whichever comes first — that's the written term. And the quoted on-road price also includes a three year warranty along with free roadside assistance
- ask `How much does a home charger cost?` → 11.1s · answered=True · facts=['F032', 'F047'] · callback=False · clarifier=False
  > Good news — a portable charger comes with the scooter itself; it plugs into a normal household socket, the same kind of plug point your geyser uses. The sample price on the page is quoted as including the charger. What I
- evals (3 typed) → 18.1s · coverage 0.33 · id ev_1788446638
  - ❌ What is the on-road price in Pune? → facts [] · Pune's on-road price I honestly don't have in the material with me, and I won't guess — it changes by state, colour and 
  - ✅ Is the battery waterproof? → facts ['F024', 'F025'] · The battery packs are sealed against water and dust, so normal rain and puddles are not a worry, and they sit in a stron
  - ❌ Can I get a test ride this weekend? → facts [] · That one I don't have — I can't see slot availability or dates from the material I have, so I won't guess. I can put in 
- eval runs listed: 1 (latest ev_1788446638)
- cost panel after: $0.290 (+$0.179 for this QA) · runtime rows 9

## Not exercised

- Refine (POST /feedback) — it hands the message to the align agent, which may rewrite the script and rebuild the demo; not run on your demos without asking.

