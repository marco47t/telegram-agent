import pytest
import router

def test_classify_trivial():
    assert router.classify_trivial("hi") == "greeting"
    assert router.classify_trivial("Hello!") == "greeting"
    assert router.classify_trivial("  yo  ") == "greeting"

    assert router.classify_trivial("thanks") == "thanks"
    assert router.classify_trivial("thank you!") == "thanks"

    assert router.classify_trivial("bye") == "farewell"
    assert router.classify_trivial("goodnight") == "farewell"

    assert router.classify_trivial("how are you?") is None
    assert router.classify_trivial("what is 2+2?") is None

def test_is_command():
    assert router.is_command("/start") is True
    assert router.is_command(" /remind") is True
    assert router.is_command("hello") is False
