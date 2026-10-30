from checker import clean_name, same_vendor


def test_clean_name_removes_suffixes():
    assert clean_name("TAJ TRADING CO. (PVT) LTD") == "taj trading"


def test_same_vendor_matches_different_spellings():
    assert same_vendor("TAJ TRADING CO. (PVT) LTD", "Taj Trading Co") is True


def test_same_vendor_rejects_different_companies():
    assert same_vendor("Taj Trading", "Hamza Garments") is False