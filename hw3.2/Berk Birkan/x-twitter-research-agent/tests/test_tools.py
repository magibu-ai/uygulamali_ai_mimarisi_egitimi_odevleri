from x_research_agent.tools.definitions import TOOL_DEFINITIONS


def test_expected_tool_surface_is_explicit_and_read_only_for_x():
    names = {tool["function"]["name"] for tool in TOOL_DEFINITIONS}

    assert names == {
        "search_x_posts",
        "get_x_post",
        "save_search_results",
        "finalize_research",
        "get_saved_research",
        "list_session_research",
        "delete_research",
    }
    assert not names.intersection({"create_tweet", "send_dm", "like_post", "follow_user"})
