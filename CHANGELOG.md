# [1.1.0](https://github.com/Jota-project/jota-orchestrator/compare/v1.0.3...v1.1.0) (2026-04-05)


### Features

* QuickRequest accepts system_prompt_extra — appended to system prompt ([20b024b](https://github.com/Jota-project/jota-orchestrator/commit/20b024b6e827764caf8022c60afc4dec7afa8013))
* QuickRequest accepts system_prompt_extra ([#16](https://github.com/Jota-project/jota-orchestrator/issues/16)) ([d182e14](https://github.com/Jota-project/jota-orchestrator/commit/d182e149167b26faa8b7fbc971dba4fe7327655b))
* QuickRequest acepta system_prompt_extra ([#18](https://github.com/Jota-project/jota-orchestrator/issues/18)) ([5d1f7f2](https://github.com/Jota-project/jota-orchestrator/commit/5d1f7f2462ac44361f768a23185430d99a6760d3))

## [1.0.3](https://github.com/Jota-project/jota-orchestrator/compare/v1.0.2...v1.0.3) (2026-04-02)


### Bug Fixes

* **memory:** use real client UUID in conversations, extra_data in messages ([f948758](https://github.com/Jota-project/jota-orchestrator/commit/f948758588261934bc36bf86649d562f76296b64)), closes [#9](https://github.com/Jota-project/jota-orchestrator/issues/9)
* **memory:** use real client UUID in conversations, extra_data in messages ([#12](https://github.com/Jota-project/jota-orchestrator/issues/12)) ([2dac337](https://github.com/Jota-project/jota-orchestrator/commit/2dac337f6b87cadaa28895768cd61515f7609276))

## [1.0.2](https://github.com/Jota-project/jota-orchestrator/compare/v1.0.1...v1.0.2) (2026-03-23)


### Bug Fixes

* uppercase client_type comparison, fix log var, add strip param to tool parser ([cdaf810](https://github.com/Jota-project/jota-orchestrator/commit/cdaf8106d4d0c88521684aaf84ddd07e95d5e6ac))
* uppercase client_type, fix log var, add strip param to tool parser ([#10](https://github.com/Jota-project/jota-orchestrator/issues/10)) ([5b5620d](https://github.com/Jota-project/jota-orchestrator/commit/5b5620d88a21e6bc086b81d1d43cf5a031df96f1))

## [1.0.1](https://github.com/Jota-project/jota-orchestrator/compare/v1.0.0...v1.0.1) (2026-03-21)


### Bug Fixes

* **tests:** update unit and integration tests to match refactored InferenceClient API ([6fa0429](https://github.com/Jota-project/jota-orchestrator/commit/6fa04298b31992d8855eb79b93133028e917b33a))

# 1.0.0 (2026-03-21)


### Bug Fixes

* **ci:** add dummy env vars for Settings and .releaserc.json to skip npm plugin ([4e4affc](https://github.com/Jota-project/jota-orchestrator/commit/4e4affc4276dec54837d8a222c3d06cc7bcd0311))
* **jotadb:** Sync endpoints/payloads and enhance inference robustness ([129584c](https://github.com/Jota-project/jota-orchestrator/commit/129584c427fba262cfe0bf8aa6d2994b1b98a072))
* **tools:** register tool modules on startup, make TAVILY_API_KEY optional ([29ee267](https://github.com/Jota-project/jota-orchestrator/commit/29ee267e918771550d178ff2c88ff0b7b4bf445a))


### Features

* **api:** add dedicated REST data & config router ([17f355c](https://github.com/Jota-project/jota-orchestrator/commit/17f355c0d9b950d3c6f59e53da9ccb027471270f))
* **auth:** implement JotaDB connection heartbeat and secure memory routing ([fc9582d](https://github.com/Jota-project/jota-orchestrator/commit/fc9582d9faf52631706c3926f20ad125c44f7f6c))
* cierre del puente de modelos — endpoints + robustez ([fadcf0e](https://github.com/Jota-project/jota-orchestrator/commit/fadcf0ee468887253ce8366427331eb60ac9df90))
* conmutación de modelos segura con atomicidad y trazabilidad ([0ceadcb](https://github.com/Jota-project/jota-orchestrator/commit/0ceadcbb4a68f477247ab3450f332ca7630cc87e))
* Dockerize application with Gunicorn/Uvicorn for production ([9c21241](https://github.com/Jota-project/jota-orchestrator/commit/9c21241f87358ad68d0d2b33973d582b8a8e4d5b))
* Implement Auth/Session Inference Client and WebSocket API ([afada79](https://github.com/Jota-project/jota-orchestrator/commit/afada79e2cf8e904092969a215febefe7c73c9c3))
* implement endpoint /quick and separated logic for CHAT vs QUICK clients ([0078928](https://github.com/Jota-project/jota-orchestrator/commit/007892886a1915ec2130658e0bc2ddb8b2952944))
* Implement robust testing suite for InferenceClient ([e877904](https://github.com/Jota-project/jota-orchestrator/commit/e877904c6b13744d2ebbaa0b07090fcf17fd64cc))
* Implement streaming NDJSON responses for the `/quick` endpoint, optimized for TTS and supporting tool execution. ([707d45d](https://github.com/Jota-project/jota-orchestrator/commit/707d45d262e6c9dfbd6ee7362614be8d8e8f5cc2))
* **inference:** current_engine_model + caché TTL para list_models ([b7408b8](https://github.com/Jota-project/jota-orchestrator/commit/b7408b86fa082284914bc5154364ec7e5d109584))
* Integrate JotaDB for persistent conversation management, authentication, and message storage. ([ef25fa7](https://github.com/Jota-project/jota-orchestrator/commit/ef25fa7666066085702b7cfe0909d53cc2df0b24))
* Introduce `_pending_commands` dictionary and handle lowercase `list_models_result` and `load_model_result` message types. ([f45c735](https://github.com/Jota-project/jota-orchestrator/commit/f45c735ec5ff2d97c3c487bbe77be08a14923d22))
* **orchestrator:** dual tool detection and deprecated grammar escape hatch ([0b92e1f](https://github.com/Jota-project/jota-orchestrator/commit/0b92e1f6049192cba2718e03481491176ece1391))
* **orchestrator:** implement tool system with Tavily, MCP, and memory tracking ([ed1d8b7](https://github.com/Jota-project/jota-orchestrator/commit/ed1d8b711fb1d713cfa596eca0dd0494fbcb26c9))
* **orchestrator:** migrate tool calling from GBNF grammar to system prompt ([2accb93](https://github.com/Jota-project/jota-orchestrator/commit/2accb938b5cda03b7d79ce1ffb8c3726a1425bf9))
* **orchestrator:** recursive tool execution loop with status tokens and thinking filter ([55b5a75](https://github.com/Jota-project/jota-orchestrator/commit/55b5a75b283b2166486e8287880eaddc87e1afbe))
* propagate user_id and implement X-Client-ID header for JotaDB services ([bc74e85](https://github.com/Jota-project/jota-orchestrator/commit/bc74e85bc745930d9597e21c0cb4db1e8a68c096))
* **quick:** voice-optimized prompt, XML cleanup, dual max_tokens, tool_parser robustness, config limits ([088bca6](https://github.com/Jota-project/jota-orchestrator/commit/088bca626cbdcb0e5612b6478e2692afd62a549a))
* **utils:** add tool_parser module with extract, validate, and clean utilities ([28c2e46](https://github.com/Jota-project/jota-orchestrator/commit/28c2e469706cea1b7342b588fd5e1f370c85c2e2))
* vincular model_id a conversaciones con verificación pre-infer ([55e6297](https://github.com/Jota-project/jota-orchestrator/commit/55e62975bf63bf397f7a2d88afac689f9fbe683e))
