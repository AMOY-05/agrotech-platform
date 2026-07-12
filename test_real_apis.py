import httpx
import asyncio
import pandas as pd
import io


async def explore_wfp_prices():
    """Download and explore real Nigerian food price data."""
    print("Downloading WFP Nigerian price data...")

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        try:
            response = await client.get(
                "https://data.humdata.org/dataset/42db041f-7aaf-4ab4-961f-2a12096861e7"
                "/resource/12b51155-0cd3-4806-9924-61ede4077591/download/wfp_food_prices_nga.csv",
                headers={"User-Agent": "Mozilla/5.0 AgroTech-Research/1.0"}
            )

            print(f"Status: {response.status_code}")
            print(f"Content length: {len(response.content)} bytes")

            if response.status_code == 200:
                # Read only first 500 lines to explore structure
                lines = response.text.split("\n")[:500]
                sample_csv = "\n".join(lines)

                df = pd.read_csv(io.StringIO(sample_csv))
                print(f"\nColumns: {list(df.columns)}")
                print(f"\nFirst 5 rows:\n{df.head().to_string()}")
                print(f"\nUnique commodities in sample: {df['commodity'].unique() if 'commodity' in df.columns else 'no commodity column'}")
                print(f"\nDate range in sample: {df['date'].min() if 'date' in df.columns else 'no date column'} to {df['date'].max() if 'date' in df.columns else ''}")
            else:
                print(f"Failed: {response.text[:200]}")

        except Exception as e:
            print(f"Error: {e}")

            # Try alternative — get just the markets file (smaller, 5KB)
            print("\nTrying markets file instead (smaller)...")
            response2 = await client.get(
                "https://data.humdata.org/dataset/42db041f-7aaf-4ab4-961f-2a12096861e7"
                "/resource/5329e772-0b74-4f65-8cc0-37a0915cc7e4/download/wfp_markets_nga.csv"
            )
            print(f"Markets file status: {response2.status_code}")
            if response2.status_code == 200:
                print(f"Markets content:\n{response2.text[:1000]}")


asyncio.run(explore_wfp_prices())