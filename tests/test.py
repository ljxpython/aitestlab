import asyncio
import random
import time


async def generate_stock_data():
    stocks = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
    for i in range(10):
        stock = random.choice(stocks)
        price = round(random.uniform(100, 500), 2)
        change = round(random.uniform(-10, 10), 2)
        change_percent = round((change / price) * 100, 2)
        yield {
            "symbol": stock,
            "price": price,
            "change": change,
            "change_percent": change_percent,
            "timestamp": time.time(),
        }
        time.sleep(1)  # 每秒更新一次


async def main():
    # async for data in generate_stock_data():
    #     print(data)
    data = generate_stock_data()
    async for i in data:
        print(i)


if __name__ == "__main__":
    asyncio.run(main())
