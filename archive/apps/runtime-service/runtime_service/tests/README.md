




runtime_service/tests/model_use.py
当你验证某个模型是否可用时，你可以使用这个测试文件。直接修改 `require_model_spec` 函数中的模型 id 即可。
模型的配置咋在 `runtime_service/conf/settings.yaml` 中。
`


runtime_service/tests/multimodal_selfcheck.py
当你想直接测试多模态模型时，你可以使用这个测试文件。
```shell
cd apps/runtime-service

  uv run python runtime_service/tests/multimodal_selfcheck.py \
    --file runtime_service/test_data/11a1f536fbf8a56a69ffa6b298b2408d.jpeg

  uv run python runtime_service/tests/multimodal_selfcheck.py \
    --file "runtime_service/test_data/12-多轮对话中让AI保持长期记忆的8种优化方式篇.pdf"

  uv run python runtime_service/tests/multimodal_selfcheck.py \
    --file "runtime_service/test_data/12-多轮对话中让AI保持长期记忆的8种优化方式篇.pdf" \
    --prepare-only
    
  uv run python runtime_service/tests/multimodal_selfcheck.py --file runtime_service/test_data/旅行日记2.pdf 

```


