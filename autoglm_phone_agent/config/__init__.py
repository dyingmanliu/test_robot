from autoglm_phone_agent.config.prompts_zh import SYSTEM_PROMPT


def get_system_prompt(lang: str = "cn") -> str:
    if lang == "en":
        return SYSTEM_PROMPT  # extend with prompts_en if needed
    return SYSTEM_PROMPT


__all__ = ["SYSTEM_PROMPT", "get_system_prompt"]
