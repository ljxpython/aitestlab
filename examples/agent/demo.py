import asyncio


class AsyncIterator:
    def __init__(self, limit):
        self.limit = limit
        self.count = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.count < self.limit:
            await asyncio.sleep(1)  # 模拟异步操作
            self.count += 1
            return self.count
        else:
            raise StopAsyncIteration


async def main():
    # 方式一
    # async for i in AsyncIterator(5):
    #     print(i)
    # 方式二
    list_data = AsyncIterator(5)
    print(list_data)
    async for i in list_data:
        print(i)


# 运行异步主函数
asyncio.run(main())
