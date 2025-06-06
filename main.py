import os
import sys

import uvicorn
from uvicorn.config import LOGGING_CONFIG

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    # print(os.path.dirname(os.path.abspath(__file__)))
    # 修改默认日志配置
    LOGGING_CONFIG["formatters"]["default"][
        "fmt"
    ] = "%(asctime)s - %(levelname)s - %(message)s"
    LOGGING_CONFIG["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    LOGGING_CONFIG["formatters"]["access"][
        "fmt"
    ] = '%(asctime)s - %(levelname)s - %(client_addr)s - "%(request_line)s" %(status_code)s'
    LOGGING_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"

    uvicorn.run(
        "backend:app", host="0.0.0.0", port=8000, reload=True, log_config=LOGGING_CONFIG
    )
