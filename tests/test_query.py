import re
import unittest

from nmah_military_collection_mcp.query import build_branch_filter


class BranchFilterTests(unittest.TestCase):
    def test_alias_boundaries_and_case(self):
        for branch, alias in [
            ("Army", "USA"),
            ("Navy", "USN"),
            ("Air Force", "USAF"),
            ("Air Force", "USAAF"),
            ("Marine Corps", "USMC"),
            ("Coast Guard", "USCG"),
            ("Army", "WAC"),
            ("Army", "WAAC"),
            ("Navy", "U.S.N."),
            ("Navy", "USNR"),
            ("Coast Guard", "U.S.C.G."),
            ("Marine Corps", "U.S.M.C."),
        ]:
            pattern = (
                build_branch_filter(branch)
                .split("title:/", 1)[1]
                .split("/ OR object_type:", 1)[0]
            )
            for text in [alias, alias.lower(), f"({alias})", f"{alias},"]:
                assert re.fullmatch(pattern, text), (branch, text)
            for text in [f"x{alias}", f"{alias}x", f"{alias}1", f"{alias}_"]:
                assert not re.fullmatch(pattern, text), (branch, text)
        for branch, text in [
            ("Navy", "UxSxNx"),
            ("Coast Guard", "UxSxCxGx"),
            ("Marine Corps", "UxSxMxCx"),
        ]:
            pattern = (
                build_branch_filter(branch)
                .split("title:/", 1)[1]
                .split("/ OR object_type:", 1)[0]
            )
            assert not re.fullmatch(pattern, text), text
        marine_pattern = (
            build_branch_filter("Marine Corps")
            .split("title:/", 1)[1]
            .split("/ OR object_type:", 1)[0]
        )
        for text in [
            "Marine",
            "marine",
            "MARINE",
            "Insignia; Marine; Epaulette",
            "(Marine)",
        ]:
            assert re.fullmatch(marine_pattern, text), text
        for text in ["Submarine", "Marine1", "Marine_", "xMarine", "Marinex"]:
            assert not re.fullmatch(marine_pattern, text), text
        for text in ["Marines", "xMarinesx", "Marine Corps", "USMC"]:
            assert re.fullmatch(marine_pattern, text), text
