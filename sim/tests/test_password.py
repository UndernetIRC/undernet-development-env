from sim.db import generate_password_hash, verify_password


def test_hash_length():
    h = generate_password_hash("simPass123")
    assert len(h) == 40


def test_hash_structure():
    h = generate_password_hash("simPass123")
    salt = h[:8]
    digest = h[8:]
    assert len(salt) == 8
    assert len(digest) == 32
    # digest must be valid hex
    int(digest, 16)


def test_verify_correct_password():
    h = generate_password_hash("simPass123")
    assert verify_password("simPass123", h) is True


def test_verify_wrong_password():
    h = generate_password_hash("simPass123")
    assert verify_password("wrongpass", h) is False


def test_different_hashes():
    h1 = generate_password_hash("simPass123")
    h2 = generate_password_hash("simPass123")
    # Different salts should produce different hashes
    assert h1 != h2
    # But both should verify
    assert verify_password("simPass123", h1)
    assert verify_password("simPass123", h2)
