# app.py
import os, json
from decimal import Decimal, getcontext

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import httpx

getcontext().prec = 40

load_dotenv()

AAVE_GQL = "https://api.v3.aave.com/graphql"

# Read env maps (lowercase chain keys recommended)
CHAINS = json.loads(os.environ["CHAINS_ADDRESS_AND_CHAINID"])
TOKENS = json.loads(os.environ["TOKENS_JSON"])

app = FastAPI()
templates = Jinja2Templates(directory="templates")


# One query: protocol APY + incentives for a reserve
GQL = """
query BorrowIncentives($request: ReserveRequest!) {
  reserve(request: $request) {
    underlyingToken { symbol address }
    borrowInfo { apy { value } }   # Protocol borrow APY (fraction)
    incentives {
      __typename
      ... on MeritBorrowIncentive {
        borrowAprDiscount { value }
      }
      ... on AaveBorrowIncentive {
        borrowAprDiscount { value }
      }
    }
  }
}
"""


def compute_rates(reserve: dict):
    # protocol APY
    protocol_apy = Decimal(reserve["borrowInfo"]["apy"]["value"])

    # sum incentive APRs -> convert to APY
    total_incentive_apr = sum(Decimal(i["borrowAprDiscount"]["value"]) for i in reserve["incentives"])
    incentives_apy = (Decimal(1) + total_incentive_apr / Decimal(365)) ** Decimal(365) - Decimal(1)

    # total APY is protocol minus incentives (floor at 0)
    total_apy = max(Decimal(0), protocol_apy - incentives_apy)

    return float(protocol_apy), float(incentives_apy), float(total_apy)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # Selected chain from query (so the chain change repopulates tokens)
    chain = (request.query_params.get("chain") or "base").lower()
    chain_tokens = TOKENS.get(chain, {})
    tokens_upper = list({k.upper(): v for k, v in chain_tokens.items()}.keys())
    token = (request.query_params.get("token") or (tokens_upper[0] if tokens_upper else "USDC")).upper()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "chains": list(CHAINS.keys()),
            "chain": chain,
            "tokens": tokens_upper,  # tokens for the selected chain
            "token": token,
            "result": None,
            "error": None,
        },
    )


@app.post("/fetch", response_class=HTMLResponse)
async def fetch(
    request: Request,
    chain: str = Form("base"),
    token: str = Form("USDC"),
):
    """
    Process the form submission, query Aave v3 GraphQL, compute APYs, and render.
    """
    chain = (chain or "base").lower().strip()
    token_symbol = (token or "USDC").strip().upper()

    # Validate chain selection
    if chain not in CHAINS:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "chains": list(CHAINS.keys()),
                "chain": "base",
                "tokens": list({k.upper(): v for k, v in TOKENS.get("base", {}).items()}.keys()),
                "token": "USDC",
                "result": None,
                "error": f"Unsupported chain: {chain}",
            },
        )

    # Resolve token address for this chain/token (case-insensitive symbol)
    chain_tokens = TOKENS.get(chain, {})
    tokens_map_upper = {k.upper(): v for k, v in chain_tokens.items()}
    token_addr = tokens_map_upper.get(token_symbol)

    if not token_addr:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "chains": list(CHAINS.keys()),
                "chain": chain,
                "tokens": list(tokens_map_upper.keys()),
                "token": token_symbol,
                "result": None,
                "error": f"Unsupported token for {chain}: {token_symbol}",
            },
        )

    variables = {
        "request": {
            "chainId": CHAINS[chain]["chainId"],
            "market": CHAINS[chain]["market"],
            "underlyingToken": token_addr.lower(),
        }
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(AAVE_GQL, json={"query": GQL, "variables": variables})

    if resp.status_code != 200:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "chains": list(CHAINS.keys()),
                "chain": chain,
                "tokens": list(tokens_map_upper.keys()),
                "token": token_symbol,
                "result": None,
                "error": f"Aave API error {resp.status_code}",
            },
        )

    data = resp.json()
    reserve = data.get("data", {}).get("reserve")
    if not reserve:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "chains": list(CHAINS.keys()),
                "chain": chain,
                "tokens": list(tokens_map_upper.keys()),
                "token": token_symbol,
                "result": None,
                "error": "No reserve data",
            },
        )

    protocol, incentive, total = compute_rates(reserve)
    result = {
        "chain": chain.title(),
        "chain_contract_address": CHAINS[chain]["market"],
        "token": reserve["underlyingToken"]["symbol"],
        "address": reserve["underlyingToken"]["address"],
        "protocol_pct": f"{protocol*100:.2f}%",
        "incentive_pct": f"{incentive*100:.2f}%",
        "total_pct": f"{total*100:.2f}%",
    }

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "chains": list(CHAINS.keys()),
            "chain": chain,
            "tokens": list(tokens_map_upper.keys()),
            "token": token_symbol,
            "result": result,
            "error": None,
        },
    )


# Run: uvicorn app:app --host 0.0.0.0 --port 8000
