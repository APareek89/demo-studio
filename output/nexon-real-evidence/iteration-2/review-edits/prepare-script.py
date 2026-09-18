"""Prepare review payloads only. Never mutates production demo data."""
import json
from pathlib import Path

HERE = Path(__file__).parent
rows = []

def line(segment, suffix, text, facts=(), image=""):
    rows.append({"id": f"{segment}-{suffix}", "text": text, "fact_ids": list(facts), "visual_ref": image})

s="intro-overview"
line(s,"L1","Let's explore the Nexon Fearless Plus P S petrol automatic.",["F019"],"im01")
line(s,"L2","We'll look at the cabin, family details and driving choices. You can steer the tour toward what matters to you.",[],"im01")
line(s,"D1","The brochure lists a length of 3,995 millimetres and a wheelbase of 2,498 millimetres.",["F012"],"im02")
line(s,"D2","A personal visit is the place to check your driving position and the space around your passengers.",[],"im04")
s="three-reminders"
line(s,"L1","Three things to explore: front-seat ventilation, a seven-speed automatic, and standard safety equipment.",["F020","F019","F003"],"im05")
line(s,"L2","We'll put each alongside what you need from your next car.",[],"im05")
line(s,"D1","This Fearless Plus P S petrol automatic has ventilated front seats; rear air vents begin at Pure Plus in the petrol and diesel range.",["F020","F021"],"im05")
line(s,"D2","Six airbags, electronic stability control and ISOFIX are standard equipment.",["F003","F004"],"im01")
s="exterior-stance"
line(s,"L1","Take in the side profile.",[],"im02")
line(s,"L2","Tata lists 208 millimetres of ground clearance, with variation by trim. Keep that figure alongside the roads and parking spaces you use.",["F013"],"im02")
line(s,"D1","The brochure lists a width of 1,804 millimetres and a height of 1,620 millimetres. Check the dimensions against your parking space.",["F012"],"im02")
line(s,"D2","Smart and Pure use 195/60 R16 tyres; Creative and Fearless use 215/60 R16.",["F017"],"im02")
s="cabin-comfort"
line(s,"L1","In this Fearless Plus P S petrol automatic, both front seats are ventilated, and rear passengers have their own air vents.",["F019","F020","F021"],"im05")
line(s,"L2","Try both rows when you visit.",[],"im05")
line(s,"D1","Front-seat ventilation is listed for Fearless Plus P S in the petrol and diesel trim list. It isn't rear-seat ventilation.",["F020"],"im05")
line(s,"D2","Rear air vents begin at Pure Plus and continue through the higher petrol and diesel trims.",["F021"],"im04")
s="boot-practicality"
line(s,"L1","Here's the boot. Petrol and diesel versions are listed at 382 litres, measured to ISO V215.",["F014"],"im06")
line(s,"L2","For a stroller or weekend bags, bring your own and check the fit with the seats in use.",[],"im06")
line(s,"D1","The CNG boot is listed at 321 litres using the same ISO V215 measurement basis. Capacity alone won't settle the fit of your luggage.",["F014"],"im06")
line(s,"D2","Creative Plus P S and Fearless Plus P S petrol and diesel trims have sixty-forty flip-and-fold rear seats, plus a rear armrest with a cup holder.",["F024"],"im04")
s="powertrain-choices"
line(s,"L1","This Fearless Plus P S pairs the turbo petrol engine with a seven-speed dual-clutch automatic.",["F019"],"im01")
line(s,"L2","For stop-and-go driving, try its response on a test drive and see how it feels to you.",[],"im01")
line(s,"D1","The 1.2-litre turbo petrol is listed at 88.2 kilowatts at 5,500 rpm, with 170 newton-metres at 1,750 to 4,000 rpm.",["F008"],"im01")
line(s,"D2","The diesel has manual and automated-manual options. CNG uses a six-speed manual; the seven-speed dual-clutch automatic is a petrol option, with availability depending on trim.",["F018","F019"],"im01")
s="safety-standards"
line(s,"L1","Six airbags, electronic stability control and ISOFIX are standard equipment.",["F003","F004"],"im01")
line(s,"L2","Tata reports a five-star Bharat NCAP rating for petrol and diesel trims active in May 2026. Extra driver-assistance features depend on the trim.",["F006"],"im01")
line(s,"D1","For your child seat, ISOFIX is a useful starting point. Check the seat's compatibility and installation instructions before fitting it.",["F004"],"im04")
line(s,"D2","Fearless Plus P S petrol DCA also lists autonomous emergency braking and lane keep assist. Those features don't establish a safety ranking against another car.",["F025"],"im01")
s="tech-convenience"
line(s,"L1","Take a closer look at the cockpit: this Fearless Plus P S has a 26.03-centimetre touchscreen and a matching-size driver display.",["F007","F009"],"im08")
line(s,"L2","On the petrol automatic, JBL audio with a subwoofer is another detail to try.",["F026"],"im04")
line(s,"D1","The touchscreen begins at Pure Plus; the matching-size driver display is listed on Fearless Plus P S in the petrol and diesel range.",["F007","F009"],"im04")
line(s,"D2","Creative adds the surround-view camera and blind-view monitor; front parking sensors start at Creative Plus P S in the petrol and diesel range.",["F022","F023"],"im04")
s="ownership-details"
line(s,"L1","For the buying decision, get a current on-road quote for your exact variant.",[],"im01")
line(s,"L2","Tata advertises a three-year, 100,000-kilometre warranty headline. Read the full written coverage and exclusions before deciding.",["F027"],"im01")
line(s,"D1","The advertised starting price is 7.39 lakh rupees ex-showroom, subject to change. It isn't a quote for this Fearless Plus P S automatic.",["F001"],"im01")
line(s,"D2","The Flexi offer advertises 6,499 rupees monthly for the first six months, with higher instalments after that. Final EMI and finance are at the financier's discretion.",["F002"],"im01")
rows.extend([
 {"id":"close-L1","text":"We've looked at the cabin, family equipment and petrol automatic. The next useful check is how the seats, visibility and gearbox feel to you.","fact_ids":["F019","F020","F003","F004"],"visual_ref":"im01"},
 {"id":"close-L2","text":"Choose Book Test Drive when you're ready, or stay here and ask another question.","fact_ids":[],"visual_ref":"im01"}
])
titles={
"intro-overview":("Tata Nexon, up close","Explore the selected petrol automatic without assuming the buyer's needs"),
"three-reminders":("Your shortlist starts here","Cabin features, driving choice and standard safety equipment"),
"exterior-stance":("Take in the stance","Published clearance with its variant qualification"),
"cabin-comfort":("Settle into the cabin","Front-seat ventilation and rear vents on the selected trim"),
"boot-practicality":("Room for your plans","Published boot capacity and a personal luggage-fit check"),
"powertrain-choices":("Find your driving rhythm","Explore the selected petrol automatic in a test drive"),
"safety-standards":("Safety starts with the details","Standard equipment and the scoped manufacturer-reported rating"),
"tech-convenience":("Your cockpit, closer","Displays and equipment tied to the selected trim"),
"ownership-details":("Make the next step count","An exact quote and written ownership terms")}
checks={
"intro-overview":"","three-reminders":"",
"exterior-stance":"Does that cover what you wanted to know about the exterior?",
"cabin-comfort":"How does that fit what you want from the cabin?",
"boot-practicality":"Does that help with the luggage checks you want to make?",
"powertrain-choices":"Is an automatic the direction you're leaning towards?",
"safety-standards":"Does that cover your main safety concerns?",
"tech-convenience":"Does that cover the cockpit features you wanted to see?",
"ownership-details":""}
out={"lines":rows,"intake_q1":"Welcome to the Tata Nexon. What matters most in your next car, or would you prefer a quick look around?","checkins":[{"segment_id":k,"text":v} for k,v in checks.items()],"segments":[{"id":k,"title":v[0],"outcome":v[1]} for k,v in titles.items()],"realign_visuals":False}
(HERE/'script-patch.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
for s in titles:
    n=sum(len(x['text'].split()) for x in rows if x['id'].startswith(s+'-L'))
    print(s,n)
