import pytest
import json
from unittest.mock import MagicMock, AsyncMock
import llm

@pytest.mark.asyncio
async def test_distill_memories_valid(mocker):
    # Mock call_flash_lite
    mock_call = mocker.patch("llm.call_flash_lite", new_callable=AsyncMock)
    mock_call.return_value = '```json\n[{"content": "likes apples", "category": "preference"}]\n```'

    messages = [{"role": "user", "content": "I like apples."}]
    results = await llm.distill_memories(messages)

    assert results == [{"content": "likes apples", "category": "preference"}]

@pytest.mark.asyncio
async def test_distill_memories_invalid_json(mocker):
    mock_call = mocker.patch("llm.call_flash_lite", new_callable=AsyncMock)
    mock_call.return_value = 'not valid json'

    messages = [{"role": "user", "content": "I like apples."}]
    results = await llm.distill_memories(messages)

    assert results == []

@pytest.mark.asyncio
async def test_distill_memories_not_list(mocker):
    mock_call = mocker.patch("llm.call_flash_lite", new_callable=AsyncMock)
    mock_call.return_value = '{"content": "likes apples", "category": "preference"}'

    messages = [{"role": "user", "content": "I like apples."}]
    results = await llm.distill_memories(messages)

    assert results == []

@pytest.mark.asyncio
async def test_call_flash_lite_tool_invocation(mocker):
    # Mock genai generative model
    mock_response_1 = MagicMock()
    mock_response_1.text = '{"tool_call": "web_search", "query": "capital of france"}'

    mock_response_2 = MagicMock()
    mock_response_2.text = "The capital of France is Paris."

    mock_model = MagicMock()
    # It gets called twice
    mock_model.generate_content.side_effect = [mock_response_1, mock_response_2]

    mocker.patch("llm._flash_lite", mock_model)

    # Mock web search
    mock_search = mocker.patch("tools.web_search.perform_search")
    mock_search.return_value = [{"title": "Paris", "url": "...", "snippet": "Paris is the capital of France."}]

    result = await llm.call_flash_lite("What is the capital of France?")

    assert result == "The capital of France is Paris."
    mock_search.assert_called_once_with("capital of france")
    assert mock_model.generate_content.call_count == 2

@pytest.mark.asyncio
async def test_call_antigravity_tool_invocation(mocker):
    # Setup ANTIGRAVITY_ACCOUNTS to have at least one account
    mocker.patch("llm.ANTIGRAVITY_ACCOUNTS", ["/tmp/account-a"])

    # Mock _run_agy
    # Call 1: returns tool call
    # Call 2: returns final answer
    mock_run_agy = mocker.patch("llm._run_agy", new_callable=AsyncMock)
    mock_run_agy.side_effect = [
        (True, '{"tool_call": "web_search", "query": "capital of france"}'),
        (True, "The capital of France is Paris.")
    ]

    # Mock web search
    mock_search = mocker.patch("tools.web_search.perform_search")
    mock_search.return_value = [{"title": "Paris", "url": "...", "snippet": "Paris is the capital of France."}]

    result = await llm.call_antigravity("What is the capital of France?")

    assert result == "The capital of France is Paris."
    mock_search.assert_called_once_with("capital of france")
    assert mock_run_agy.call_count == 2
