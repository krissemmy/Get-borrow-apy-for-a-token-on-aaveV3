# Get-borrow-apy-for-a-token-on-aaveV3

This project provides a simple Quart web app to fetch and display the borrow APY (including incentives) for a given token on Aave v3, for supported chains (e.g., Base).

## How to Run

1. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```

2. **Set up environment variables**:
   - `CHAINS_ADDRESS_AND_CHAINID`: JSON mapping of chain names to their Aave v3 market addresses and chain IDs.
   - `TOKENS_JSON`: JSON mapping of chain names to token symbol/address pairs.

   You can use a `.env` file for convenience.

3. **Start the server**:
   ```
   python get_apy_of_a_token_on_base_on_aaveV3.py
   ```
   The app will be available at [http://localhost:5002](http://localhost:5002).

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