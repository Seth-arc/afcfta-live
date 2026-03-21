"""v0.1 locked countries with ISO codes and regional bloc membership."""

V01_COUNTRIES = {
    "NGA": {"name": "Nigeria", "iso2": "NG", "bloc": "ECOWAS", "language": "en"},
    "GHA": {"name": "Ghana", "iso2": "GH", "bloc": "ECOWAS", "language": "en"},
    "CIV": {"name": "Côte d'Ivoire", "iso2": "CI", "bloc": "ECOWAS", "language": "fr"},
    "SEN": {"name": "Senegal", "iso2": "SN", "bloc": "ECOWAS", "language": "fr"},
    "CMR": {"name": "Cameroon", "iso2": "CM", "bloc": "ECCAS/CEMAC", "language": "fr/en"},
}

V01_CORRIDORS = [
    ("GHA", "NGA"), ("NGA", "GHA"),
    ("CMR", "NGA"), ("NGA", "CMR"),
    ("CIV", "NGA"), ("SEN", "NGA"),
    ("GHA", "CIV"), ("CIV", "SEN"),
]