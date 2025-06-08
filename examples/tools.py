from autogen_core import CancellationToken
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor
from autogen_ext.tools.code_execution import PythonCodeExecutionTool


async def main():
    # Create the tool.
    code_executor = DockerCommandLineCodeExecutor()
    await code_executor.start()
    code_execution_tool = PythonCodeExecutionTool(code_executor)
    cancellation_token = CancellationToken()

    # Use the tool directly without an agent.
    code = "print('Hello, world!')"
    result = await code_execution_tool.run_json({"code": code}, cancellation_token)
    print(code_execution_tool.return_value_as_string(result))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
