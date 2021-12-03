def find_substring(s: str, marker_1: str, marker_2: str) -> str:
    """Extracts a substring between two markers"""
    start = s.find(marker_1) + len(marker_1)
    s_temp = s[start:]
    end = s_temp.find(marker_2)
    return s_temp[:end]


def get_current_profile_from_link_header(response):
    """Gets the currently selected profile from the Link header"""
    link_header = response.headers.get("link")
    if link_header is not None:
        current_profile = ""
        types = []
        alternates = []
        for link in link_header.split(","):
            if 'rel="profile"' in link:
                current_profile = link
            elif 'rel="type"' in link:
                types.append(link)
            else:  # alternates
                alternates.append(link)
        current_profile_uri = find_substring(current_profile, "<", ">")
        for profile in types:
            if current_profile_uri in profile:
                return find_substring(profile, 'token="', '"')
    return None


def current_profile_is_alt_from_link_header(response):
    profile = get_current_profile_from_link_header(response)
    assert profile == "alt"
