"""Currency paraphrases retain unit binding and independent page attribution."""
from decimal import Decimal
import os

os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0")
from server import runtime_graph as graph

checks = []
def check(name, passed):
    assert passed, name
    checks.append(name)

def decision(text, ids):
    return {"action": "answer", "answered": True,
            "sentences": [{"text": text, "kind": "fact", "fact_ids": ids}]}

page = "https://www.hyundai.com/in/en/find-a-car/creta/price"
highlights = "https://www.hyundai.com/in/en/find-a-car/creta/highlights"
fact = {"id": "Wprice", "approved": True, "provenance": "live_web",
        "claim": "Customer-selected website passage",
        "value": "Hyundai CRETA starting price: ₹10,90,700* (ex-showroom).",
        "conditions": "Attribute the retrieved page; current quote is unverified.",
        "scope": {}, "source": {"ref": page, "locator": "Starting price"}}
question = f"Use {highlights} to verify the exact on-road price in my city."

for source, spoken in (
    ("₹10,90,700", "10,90,700 rupees"),
    ("INR 1090700", "1090700 INR"),
    ("₹ 1,250.50", "1250.50 rupees"),
    ("₹1 250", "1250 rupees"),
):
    check("Adjacent currency representations match: " + source,
          graph._quantity_units(source) == graph._quantity_units(spoken))

for value in ("₹10,90,700", "INR 1090700"):
    record = {**fact, "value": f"Starting ex-showroom price {value}."}
    answer, errors = graph.validate_decision(decision(
        "According to the price page, the listed ex-showroom starting price is 10,90,700 rupees.",
        ["Wprice"]), [record], question)
    check("Actual validation accepts spoken currency from " + value,
          answer["answered"] and not errors and answer["fact_ids"] == ["Wprice"])

for text, code in (
    ("According to the price page, the starting price is 1090701 rupees.", "unsupported_quantity"),
    ("According to the price page, the fuel tank holds 1090700 litres.", "unsupported_assertion_feature"),
):
    answer, errors = graph.validate_decision(decision(text, ["Wprice"]), [fact], question)
    check("Currency cannot license a changed amount or unit: " + text,
          not answer["answered"] and code in errors)

mixed = {**fact, "value": "Price ₹500; fuel capacity 50 litres."}
answer, errors = graph.validate_decision(decision(
    "According to the price page, the price is 50 rupees.", ["Wprice"]), [mixed], question)
check("A currency symbol cannot lend its unit to another amount",
      not answer["answered"] and "unsupported_quantity_unit" in errors)
check("Unit binding retains independently stated quantities",
      graph._quantity_units("Price ₹500; fuel capacity 50 litres.") ==
      {(Decimal("500"), "currency"), (Decimal("50"), "litre")})

# Actual failed q074 wording: fixing the rupee parser must not authorize this
# attribution to highlights when only the linked price page supplies the fact.
actual = ("I could not verify an exact on-road price on the highlights page, "
          "as it only mentions ex-showroom pricing starting from 10,90,700 rupees.")
answer, errors = graph.validate_decision(decision(actual, ["Wprice"]), [fact], question)
check("Currency correction still rejects the actual wrong-page attribution",
      not answer["answered"] and "unverified_web_attribution" in errors)
for verb in ("mentions", "provides"):
    answer, errors = graph.validate_decision(decision(
        f"The supplied page {verb} an ex-showroom starting price of 10,90,700 rupees.",
        ["Wprice"]), [fact], question)
    check("Child-page evidence cannot impersonate supplied page: " + verb,
          not answer["answered"] and "unverified_web_attribution" in errors)
    exact = {**fact, "source": {**fact["source"], "ref": highlights}}
    answer, errors = graph.validate_decision(decision(
        f"The supplied page {verb} an ex-showroom starting price of 10,90,700 rupees.",
        ["Wprice"]), [exact], question)
    check("Genuine supplied-page evidence remains usable: " + verb,
          answer["answered"] and not errors)

print(f"Currency and attribution contract: {len(checks)}/{len(checks)} passed")
