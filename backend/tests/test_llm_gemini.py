def test_llm_status_gemini_unconfigured(app_ctx):
    from app.services import llm

    app_ctx.config["LLM_PROVIDER"] = "gemini"
    app_ctx.config["GEMINI_API_KEY"] = ""
    st = llm.llm_status()
    assert st["provider"] == "gemini"
    assert st["configured"] is False


def test_llm_status_gemini_configured(app_ctx):
    from app.services import llm

    app_ctx.config["LLM_PROVIDER"] = "gemini"
    app_ctx.config["GEMINI_API_KEY"] = "test-key"
    assert llm.llm_configured() is True
