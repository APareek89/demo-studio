# Source audit for the driver-first CRETA script

Read-only review of the 49-page supplied compilation. All page numbers below are PDF pages, which match the printed page numbers. No internet or paid calls. The source is a compilation dated 19 September 2026, not itself a Hyundai publication (page49); it reproduces official maker material. Table precedence and footnotes matter more than broad FAQ wording.

## Frozen simulation inputs

- understanding.json: 64 facts, 31 real embedded-picture references, 10 unknowns; validated against current server.schemas.Understanding. Exact source.quote strings asserted present on their cited pages.
- assets.json: PDF image occurrence, absolute extracted-byte path, fixture source ID and image ID.
- fixture-provenance.json: explicit manual Understand simulation; local fixture fact IDs are not app-generated knowledge identities. Approved=true applies only to this reviewed isolated simulation. No bounding boxes are guessed.
- all.txt and page-01.txt through page-49.txt preserve extracted evidence; seven key pages rendered and inspected; all94 image occurrences on pages1–28 inspected as contact sheets.

## What the goal gets right

- Three engines, turbo160 PS, DCT: pages16 and29. Page31 restricts turbo/DCT to King, while King ALSO supports other engine choices. Never say all Kings are turbo.
- Diesel250 Nm at1500–2750 rpm is stated page16. Petrol/manual/IVT, diesel/manual/automatic, turbo/DCT pairings are explicit pages16/31.
- Six airbags, ESC and four discs on every trim: pages19,29,32. Standard equipment is supported; identical real-world safety is not.
- Wheel trim map: pages8/35. King and Knight18-inch wheels, entry16-inch, middle17-inch. No comparative ride test appears.
- Rear vents all trims, split rear seat all trims, rear reclining from S(O): pages37/39. Cabin dimensions beyond wheelbase are not supplied.
- ADAS King/King Knight/Lounge: pages22/33–34. Surround-view and blind-spot cameras also on SX Premium. Adaptive stop-go cruise ONLY King/King Knight/Lounge automatics. Source FAQ references some obsolete trims; explicit current matrix wins.
- Ventilated front seats SX Premium upwards, dual-zone climate S(O) upwards, displays SX upwards: pages25/39/41.
- Sunroof eight of ten, starts EX(O); voice operation starts SX: page39. Bose starts SX Premium: pages25/41.
- Starting ex-showroom ₹10,90,700: page42, but same source reports conflicting structured-data headline ₹10.79 lakh. Retain conflict and confirm current dealer quote; no live validation is implied.
- Paid extended warranty up to seven years on petrol only: page49.

## Goal lines that cannot be accepted unchanged

1. overview-L1: 'one of our flagship cars ... one of the best in the market' is not stated anywhere in this PDF. Page5 has time-qualified sales ranks, which the task explicitly excludes from narration. Those do not prove the proposed superiority claim. Use sourced positioning ('for city use and longer runs', page3), or report criterion2 evidence-blocked; do not grant an uncited exception.
2. three-things-L1/runtime: 'King is the quick one' may sound like an acceleration comparison. PDF calls turbo the most powerful (page44), but there is no acceleration test. 'Turbo King' is also essential because King has other engines (page31).
3. powertrain-L1: 'real punch when you overtake' is not a reported overtaking result. Page16 contains manufacturer descriptions of responsive handling and smooth acceleration. Keep those attributed/described as marketing, not a demonstrated guarantee.
4. powertrain-L2: 'loaded car on a long climb never feels strained' is not in the PDF and cannot be deduced from torque. Diesel torque/ordinary engine-use explanation may be stated without guaranteed loaded performance.
5. powertrain-L3: 'from S(O) up' with 'automatics' is mostly usable only alongside the current engine table: SX has no automatic, S(O) Knight carries starred features but no current auto pairing. Exact named availability is S(O), S(O) Knight, SX Premium, King, King Knight, Lounge, automatic only for modes. Auto hold is standard on King/King Knight/Lounge and automatic-only S(O)/S(O)Knight/SXPremium (page39).
6. stance-L1: height with roof rails does not prove driver eye position or seeing over traffic. Tyre sidewall ratios do not establish 'suits broken roads' or ride comfort. Neither outcome is evidenced here.
7. space-L1: equal wheelbase does not establish equal rear legroom or that the seat 'doesn't shrink'. Use directly stated split seat, vents, recline and storage functions.
8. space-D2/ownership-L1: 'Hyundai doesn't publish' is broader than evidence. This PDF does not give boot litres or fuel-economy figures. A test drive cannot settle certified mileage, and no absent number should be invented.
9. safety-L1/closing-L1: 'what protects you doesn't move with price' / 'safety doesn't change' are overbroad: extra driver assistance demonstrably DOES vary by trim. Say the listed airbags/disc brakes are standard and separately scope ADAS.
10. safety-L2: 'brakes on its own if it must' reads as guaranteed autonomous intervention. Source says assistance; page49 explicitly says no substitute for safe attentive driving. Describe collision warning/avoidance capability with limits, not certainty.
11. safety-D2: adaptive stop-go is not for every automatic. It is King/KingKnight/Lounge automatic only, even though SXPremium also has surround view (pages22/33).
12. cabin-L1: the screens are10.25 inches, not ten. 'Bearable fast' invents an unmeasured cooling time. Ventilation moves air through seat cushions, not necessarily refrigerated air. Page24 explicitly describes remote start with Alexa; page45 says Bluelink controls key functions but does not explicitly name phone-app engine start. Avoid inferring phone start from these two different statements.
13. cabin-D2: wireless mirroring EX+ is true, but SX+ needs the wired-to-wireless adapter and device compatibility (pages25/41). Do not omit the meaningful condition.
14. delighters-L1: puddle lights need scope: driver side SX+, both sides King/KingKnight/Lounge (page33). The goal leaves them ungated.
15. delighters-D2: fifty-litre tank is sourced (pages3/29/43). 'Fewer stops' is manufacturer marketing on page43, not a measured range claim; cannot estimate any range.
16. closing-L1: recommending diesel as 'sensible' merely from necessity of driving adds an unsupported customer preference and economics judgment. No total ownership cost or personal usage is known.
17. closing-L2: named CTA is not a supplied URL. Page49 gives source URLs but no explicit test-drive booking endpoint. Use only an actually configured/source-discovered CTA; do not fabricate a destination or successful booking.

## Marketing versus measurement

Page16 repeats Hyundai's 'smooth acceleration', 'responsive handling', diesel torque/efficiency and everyday comfort descriptions. Those may be stored as kind=claim, truth=stated with explicit manufacturer-marketing conditions; they are not observed/certified results. The same page even says petrol/diesel mileage brings fewer 'charging' stops, an obvious source-copy mismatch that must not be carried forward. Page44's FAQ also says turbo1497cc, conflicting with the1482cc technical table. Prefer the scoped technical table; retain conflicts when relevant. No acceleration time, certified mileage, boot litres, ground clearance measurement, top speed or crash rating appears.

## Visual availability and limits

- Moving/front three-quarter hero exists page15 image1 (fixtureim01).
- Side profile pages7image4/im02 and27image3/im03.
- Actual engine images page16: turbo image2/im04, diesel image1/im05, petrol image3/im06. Each embeds printed specs; these show engines, not steering paddles or a gear selector.
- Paddle close-up page17image4/im08; manual console page17image2/im07; drive display page17image3/im09; terrain-mode diagram with selector inset page24image2/im10; auto hold page19image1/im11.
- Wheel close-up page8image6/im12. It illustrates the wheel, not comparative ride quality.
- Rear folded seats page13image7/im13; whole panorama page12image2/im14 (rear vents visible bottom-centre on inspection); boot with luggage page13image1/im15. No legroom measurement image exists.
- Airbag illustration page19image4/im16; stability diagram page20image3/im17; collision-assist diagram page21image7/im18; cyclist assist page21image5/im19; lane warning page21image2/im20. They do not prove crash rating or guaranteed avoidance.
- Ventilated front seats page12image1/im21; dashboard/two screens page12image3/im22; dual climate page25image5/im23; seat memory page14image6/im24.
- Bose diagram page24image3/im25; roof exterior page25image3/im26; roof from cabin page11image1/im27; puddle lamp page8image3/im28; phone charging page25image6/im29.
- Rear table page14image2/im30; armrest storage page13image3/im31.
- There is no ownership-price or warranty photograph. A neutral whole-car image can orient an ownership discussion but cannot literally prove a price. Do not claim 'every line literally pictured' when it is a policy, price, or abstract promise.

## Goal's internal quantitative mismatches

Whitespace counts: twelve main lines have32,33,31,32,31,31,32,26,30,32,32,31 words. Closing has33 and15. Main plus closing421 words =187.95 seconds at2.24 words/second; actual TTS is not measured. Runtime overview is29 words, exceeding required23–28. The exact160 PS text is in powertrain-L1, not overview as the task's final note says, and repeats in deeper. The target is a narrative example, not self-passing acceptance data. Main budget fields sum375 while actual main narration373; closing is separate. The task's stated26–33 words at2.24 wps corresponds to11.6–14.7 seconds, not exactly12–15. Existing selected-duration gate must stay intact; three-minute certification needs measured audio, which this no-paid simulation cannot provide.
