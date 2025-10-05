# Get-borrow-apy-for-a-token-on-aaveV3

This project provides a simple Quart web app to fetch and display the borrow APY (including incentives) for a given token on Aave v3, for supported chains (Ethereum, Sonic, Base).

## How to Run

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables**:
   Copy `env.example` to `.env` and configure the following variables:
   - `CHAINS_ADDRESS_AND_CHAINID`: JSON mapping of chain names to their Aave v3 market addresses and chain IDs
   - `TOKENS_JSON`: JSON mapping of chain names to token symbol/address pairs

   Example `.env` file:
   ```bash
   CHAINS_ADDRESS_AND_CHAINID='{"base": {"chainId": 8453, "market": "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"}}'
   TOKENS_JSON='{"base": {"USDC": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"}}'
   ```

3. **Start the server**:
   ```bash
   python get_apy_of_a_token_on_base_on_aaveV3.py
   ```
   The web app will be available at [http://localhost:5002](http://localhost:5002).

## Supported Chains and Tokens

- **Base**: USDC, EURC, GHO, USDbc, AAVE, WETH
- **Ethereum**: USDC, EURC, WETH  
- **Sonic**: USDC, wS

## Calculation Logic

- The script queries the Aave v3 GraphQL API for the selected token and chain.
- It retrieves:
  - The protocol variable borrow APY.
  - Any borrow incentive APRs (discounts).
- The total borrow APY is calculated as:
  - **Total APY = Protocol APY - Incentive APY**
  - Incentive APRs are summed and converted to APY using compounding:  
    `incentive_apy = (1 + total_incentive_apr/365) ** 365 - 1`
  - All rates are displayed as percentages.

## Links

- [Aave v3 Markets Data Documentation](https://aave.com/docs/developers/aave-v3/markets/data): Reference for the API and data model.
- [Aave App (Base Market)](https://app.aave.com/?marketName=proto_base_v3): For manual exploration and verification of rates.