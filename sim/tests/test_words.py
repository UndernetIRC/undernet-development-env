from sim.words import generate_message


def test_returns_non_empty_string():
    msg = generate_message()
    assert isinstance(msg, str)
    assert len(msg) > 0


def test_varied_output():
    messages = {generate_message() for _ in range(10)}
    assert len(messages) >= 5


def test_no_template_placeholders():
    for _ in range(50):
        msg = generate_message()
        assert "{w" not in msg
