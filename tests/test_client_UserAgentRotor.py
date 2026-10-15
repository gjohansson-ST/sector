from custom_components.sector.client import UserAgentRotor


def test_get_user_agent_lazily_selects_an_agent() -> None:
    rotor = UserAgentRotor()

    user_agent = rotor.get_user_agent()

    assert user_agent in UserAgentRotor.USER_AGENTS
    assert rotor._current_agent == user_agent


def test_get_user_agent_returns_current_agent_until_rotated() -> None:
    rotor = UserAgentRotor()

    first_user_agent = rotor.get_user_agent()

    assert rotor.get_user_agent() == first_user_agent


def test_rotate_uses_each_user_agent_before_refilling() -> None:
    rotor = UserAgentRotor()

    selected_agents = [rotor.get_user_agent()]
    for _ in range(len(UserAgentRotor.USER_AGENTS) - 1):
        rotor.rotate()
        selected_agents.append(rotor.get_user_agent())

    assert set(selected_agents) == set(UserAgentRotor.USER_AGENTS)
    assert len(selected_agents) == len(set(selected_agents))


def test_rotate_refills_from_a_copy_of_user_agents() -> None:
    rotor = UserAgentRotor()

    for _ in UserAgentRotor.USER_AGENTS:
        rotor.rotate()

    assert rotor._agent_list == []
    rotor.rotate()

    assert rotor._current_agent in UserAgentRotor.USER_AGENTS
    assert len(rotor._agent_list) == len(UserAgentRotor.USER_AGENTS) - 1
    assert rotor._agent_list != UserAgentRotor.USER_AGENTS
