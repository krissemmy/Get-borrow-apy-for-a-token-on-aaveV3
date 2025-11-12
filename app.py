import os, json, requests
from decimal import Decimal, getcontext
from quart import Quart, request, render_template
import httpx

getcontext().prec = 40
app = Quart(__name__)
app.config.setdefault("PROVIDE_AUTOMATIC_OPTIONS", True)
AAVE_GQL = "https://api.v3.aave.com/graphql"

from dotenv import load_dotenv
load_dotenv()

# Read env maps (lowercase chain keys recommended)
CHAINS = json.loads(os.environ["CHAINS_ADDRESS_AND_CHAINID"])
TOKENS = json.loads(os.environ["TOKENS_JSON"])

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

def compute_rates(reserve):
    # protocol APY
    protocol_apy = Decimal(reserve['borrowInfo']['apy']['value'])

    # sum incentive APRs -> convert to APY
    total_incentive_apr = sum([Decimal(i['borrowAprDiscount']['value']) for i in reserve['incentives']])
    incentives_apy = (Decimal(1) + total_incentive_apr/Decimal(365))**Decimal(365) - Decimal(1)
    total_apy = max(0, (protocol_apy - incentives_apy))

    return float(protocol_apy), float(incentives_apy), float(total_apy)

@app.get("/")
async def index():
    # Selected chain from query (so the chain change repopulates tokens)
    chain = (request.args.get("chain") or "base").lower()
    chain_tokens = TOKENS.get(chain, {})
    tokens_upper = list({k.upper(): v for k, v in chain_tokens.items()}.keys())
    # default token for this chain
    token = (request.args.get("token") or (tokens_upper[0] if tokens_upper else "USDC")).upper()

    return await render_template(
        "index.html",
        chains=list(CHAINS.keys()),
        chain=chain,
        tokens=tokens_upper,    # tokens for the selected chain
        token=token,
        result=None,
        error=None,
    )

@app.post("/fetch")
async def fetch():
    """
    Handle POST requests to the /fetch endpoint.

    This endpoint processes form data submitted by the user, validates the selected chain and token,
    queries the Aave v3 GraphQL API for the borrow APY and incentives for the selected reserve,
    computes the protocol APY, incentive APY, and total APY, and renders the results in the template.

    Returns:
        Rendered HTML template with the result or an error message.
    """
    # Parse form data: get chain and token symbol from user input
    form = await request.form
    chain = (form.get("chain") or "base").lower().strip()
    token_symbol = (form.get("token") or "USDC").strip().upper()
    
    # Validate chain selection
    if chain not in CHAINS:
        # If chain is not supported, show error and default to base tokens
        return await render_template(
            "index.html",
            chains=CHAINS.keys(),
            tokens=TOKENS.get("base", {}).keys(),
            result=None,
            error=f"Unsupported chain: {chain}"
        )

    # Validate token selection for the chosen chain
    # Resolve address for this chain/token (case-insensitive symbol)
    chain_tokens = TOKENS.get(chain, {})
    tokens_map_upper = {k.upper(): v for k, v in chain_tokens.items()}
    token_addr = tokens_map_upper.get(token_symbol)

    # Prepare GraphQL variables for the Aave API request
    variables = {
        "request": {
            "chainId": CHAINS[chain]["chainId"],
            "market": CHAINS[chain]["market"],
            "underlyingToken": token_addr.lower(),
        }
    }
    
    # Make the POST request to the Aave v3 GraphQL API
    # response = requests.post(AAVE_GQL, json={"query": GQL, "variables": variables}, timeout=30)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(AAVE_GQL, json={"query": GQL, "variables": variables})
    if response.status_code != 200:
        # If API call fails, show error and list tokens for that chain
        return await render_template("index.html", chains=CHAINS.keys(), tokens=TOKENS.get(chain, {}).keys(), result=None, error=f"Aave API error {response.status_code}")

    # Parse the API response JSON
    data = response.json()
    reserve = data.get("data", {}).get("reserve")
    if not reserve:
        # If no reserve data is returned, show error
        return await render_template(
            "index.html",
            chains=list(CHAINS.keys()),
            chain=chain,
            tokens=list(tokens_map_upper.keys()),
            token=token_symbol,
            result=None,
            error="No reserve data"
        )

    # Compute protocol APY, incentive APY, and total APY using the reserve data
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

    # Render the template with the results
    return await render_template(
        "index.html",
        chains=list(CHAINS.keys()),
        chain=chain,
        tokens=list(tokens_map_upper.keys()),
        token=token_symbol,
        result=result,
        error=None,
    )

if __name__ == "__main__":
    # http://127.0.0.1:8000
    app.run(host="0.0.0.0", port=8000, debug=False)
    