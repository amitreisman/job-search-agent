"""One prompt in, text out, no tools. Two backends:

- ANTHROPIC_API_KEY set  -> the Anthropic API (what a hosted server uses).
- otherwise              -> the Claude Agent SDK through the local Claude Code login (what the owner's PC uses).
"""
import asyncio
import os

MODELS = {"sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-4-5-20251001"}
USE_API = bool(os.environ.get("ANTHROPIC_API_KEY"))
_client = None


async def _ask_api(system, prompt, model, max_tokens):
    global _client
    if _client is None:
        from anthropic import AsyncAnthropic
        _client = AsyncAnthropic()
    r = await _client.messages.create(model=MODELS.get(model, model), max_tokens=max_tokens, system=system,
                                      messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in r.content if b.type == "text")


async def _ask_sdk(system, prompt, model):
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
    opts = ClaudeAgentOptions(system_prompt=system, allowed_tools=[], max_turns=1, model=model)
    result = ""
    async for msg in query(prompt=prompt, options=opts):  # drain fully so the generator cleans up properly
        if isinstance(msg, ResultMessage):
            result = msg.result or ""
    return result


async def ask_async(system, prompt, model="sonnet", max_tokens=3000):
    if USE_API:
        return await _ask_api(system, prompt, model, max_tokens)
    return await _ask_sdk(system, prompt, model)


def ask(system, prompt, model="sonnet", max_tokens=3000):
    return asyncio.run(ask_async(system, prompt, model, max_tokens))
