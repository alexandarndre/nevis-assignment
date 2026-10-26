import argparse
import json
import sys
import urllib.error
import urllib.request

from pydantic import BaseModel, HttpUrl

from nevis_search.clients.schemas import ClientIn, ClientOut
from nevis_search.documents.schemas import DocumentIn


class SeedClient(BaseModel):
    client: ClientIn
    documents: list[DocumentIn]


SEED = [
    SeedClient(
        client=ClientIn(
            first_name="John",
            last_name="Doe",
            email="john.doe@neviswealth.com",
            description="Founder of a fintech start-up. Prefers growth portfolios with an ESG tilt.",
            social_links=[HttpUrl("https://www.linkedin.com/in/johndoe")],
        ),
        documents=[
            DocumentIn(
                title="Utility bill - British Gas, March 2024",
                content=(
                    "British Gas electricity and gas statement for the billing period 1 to 31 March 2024. "
                    "Account holder: John Doe, 12 Baker Street, London NW1 6XE. "
                    "Total amount due: 184.20 GBP, collected by direct debit on 15 April 2024."
                ),
            ),
            DocumentIn(
                title="Passport copy",
                content=(
                    "Scanned copy of the British passport of John Doe, passport number 533380006, "
                    "issued 12 June 2019 and expiring 12 June 2029. Place of birth: Manchester."
                ),
            ),
            DocumentIn(
                title="Investment policy statement 2024",
                content=(
                    "Objective: long-term capital growth over a 15-year horizon. "
                    "Risk tolerance: moderately aggressive. "
                    "Target allocation: 70% global equities with an ESG screen, 20% fixed income, 10% alternatives. "
                    "The portfolio is rebalanced quarterly and liquidity needs are low."
                ),
            ),
        ],
    ),
    SeedClient(
        client=ClientIn(
            first_name="Maria",
            last_name="Garcia",
            email="maria.garcia@example.com",
            description=(
                "Retired orthopaedic surgeon living in Lisbon. Income-focused portfolio and estate planning "
                "for her three grandchildren."
            ),
        ),
        documents=[
            DocumentIn(
                title="Bank statement - Millennium BCP, June 2024",
                content=(
                    "Current account statement addressed to Maria Garcia, Rua Augusta 100, 1100-053 Lisbon. "
                    "Pension credits of 4,200 EUR and card payments during June 2024."
                ),
            ),
            DocumentIn(
                title="Last will summary",
                content=(
                    "Maria Garcia's will names her three grandchildren as equal beneficiaries of the residuary "
                    "estate. The family home in Cascais passes to her daughter. "
                    "A separate letter of wishes covers personal items and jewellery."
                ),
            ),
            DocumentIn(
                title="Review meeting notes, 14 May 2024",
                content=(
                    "Discussed drawing down from the SIPP and moving 40% of the portfolio into short-dated gilts. "
                    "The client wants to fund private school fees for her grandchildren from 2025. "
                    "Next review in November."
                ),
            ),
        ],
    ),
    SeedClient(
        client=ClientIn(
            first_name="Liam",
            last_name="O'Connor",
            email="liam@oconnorholdings.ie",
            description="Owner of a logistics company in Dublin, preparing the sale of the business in 2027.",
        ),
        documents=[
            DocumentIn(
                title="Share purchase agreement (draft)",
                content=(
                    "Draft agreement for the sale of O'Connor Logistics Ltd to Freightline Group for 12.5m EUR, "
                    "with an earn-out of up to 2m EUR over two years. Completion is targeted for Q2 2027."
                ),
            ),
            DocumentIn(
                title="Payslip May 2024",
                content=(
                    "O'Connor Holdings payslip for Liam O'Connor. Gross salary 15,000 EUR, income tax 4,950 EUR, "
                    "social insurance 1,340 EUR, net pay 8,710 EUR."
                ),
            ),
        ],
    ),
    SeedClient(
        client=ClientIn(
            first_name="Aisha",
            last_name="Khan",
            email="aisha.khan@khanfamilyoffice.co.uk",
            description="Next-generation member of a family office, interested in private equity and impact investing.",
        ),
        documents=[
            DocumentIn(
                title="Source of wealth declaration",
                content=(
                    "The client's wealth derives from an inheritance received in 2018 after the death of her "
                    "father, founder of Khan Textiles, and from dividends paid by the family holding company."
                ),
            ),
            DocumentIn(
                title="Tenancy agreement",
                content=(
                    "Assured shorthold tenancy for Flat 4, 22 Kensington Gardens Square, London W2, between "
                    "Aisha Khan (tenant) and Hyde Estates (landlord) for 12 months from 1 September 2024. "
                    "Rent is 3,250 GBP per month."
                ),
            ),
        ],
    ),
    SeedClient(
        client=ClientIn(
            first_name="Wei",
            last_name="Chen",
            email="wei.chen@globalmail.com",
            description="Software engineer relocating from Singapore to Zurich; needs help with a pension transfer.",
        ),
        documents=[
            DocumentIn(
                title="CRS self-certification",
                content=(
                    "Chen Wei declares tax residence in Switzerland from 1 January 2025, previously tax resident "
                    "in Singapore. Swiss social security number 756.1234.5678.97."
                ),
            ),
            DocumentIn(
                title="Driving licence",
                content="Singapore driving licence of Chen Wei, class 3, valid until 2031.",
            ),
        ],
    ),
    SeedClient(
        client=ClientIn(
            first_name="Sophie",
            last_name="Martin",
            email="sophie.martin@neviswealth.com",
            description="Young professional starting to invest monthly; cautious about market swings.",
        ),
        documents=[
            DocumentIn(
                title="Risk questionnaire results",
                content=(
                    "Sophie Martin scored 3 out of 10 on the attitude-to-risk questionnaire. "
                    "She is a cautious investor who prefers capital preservation and would sell after a 10% fall."
                ),
            ),
        ],
    ),
]


def _post(url: str, body: BaseModel) -> bytes:
    request = urllib.request.Request(
        url,
        data=body.model_dump_json().encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        payload: bytes = response.read()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Load demo clients and documents through the API.")
    parser.add_argument("--base-url", default="http://localhost:8000/api/v1")
    base_url = parser.parse_args().base_url.rstrip("/")
    for entry in SEED:
        try:
            client = ClientOut.model_validate_json(_post(f"{base_url}/clients", entry.client))
        except urllib.error.HTTPError as exc:
            if exc.code == 409:
                print(f"skipped {entry.client.email}: already exists", file=sys.stderr)
                continue
            raise
        for document in entry.documents:
            _post(f"{base_url}/clients/{client.id}/documents", document)
        print(json.dumps({"client": str(client.id), "email": client.email, "documents": len(entry.documents)}))


if __name__ == "__main__":
    main()
