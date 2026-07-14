import pytest

from open_webui.utils.hermes_runs import (
    HermesRun,
    HermesRunRegistry,
    hermes_run_capabilities_satisfied,
)


def _run() -> HermesRun:
    return HermesRun(
        run_id='run_1',
        chat_id='chat_1',
        message_id='message_1',
        user_id='user_1',
        model_id='expert-agent',
        base_url='http://hermes.test/v1',
        headers={'Authorization': 'Bearer hidden'},
        cookies={},
        session_id='chat_1',
    )


@pytest.mark.asyncio
async def test_approval_registry_enforces_owner_and_fifo():
    registry = HermesRunRegistry()
    await registry.register(_run())
    _, first = await registry.add_approval(
        'run_1',
        {'command': 'mkdir /tmp/a', 'description': 'write', 'choices': ['once', 'deny']},
    )
    await registry.add_approval(
        'run_1',
        {'command': 'rm /tmp/a', 'description': 'delete', 'choices': ['once', 'deny']},
    )

    with pytest.raises(LookupError):
        await registry.claim_approval('run_1', first.id, 'other_user', 'chat_1', 'once')

    pending = await registry.list_pending('user_1', 'chat_1')
    assert [item['sequence'] for item in pending] == [1, 2]

    run, claimed = await registry.claim_approval('run_1', first.id, 'user_1', 'chat_1', 'once')
    assert run.status == 'waiting_for_approval'
    assert claimed.status == 'responding'


@pytest.mark.asyncio
async def test_approval_registry_is_idempotent_after_resolution():
    registry = HermesRunRegistry()
    await registry.register(_run())
    _, approval = await registry.add_approval(
        'run_1',
        {'command': 'mkdir /tmp/a', 'description': 'write'},
    )

    await registry.claim_approval('run_1', approval.id, 'user_1', 'chat_1', 'deny')
    await registry.finish_approval('run_1', approval.id, 'deny')
    _, repeated = await registry.claim_approval('run_1', approval.id, 'user_1', 'chat_1', 'deny')

    assert repeated.status == 'denied'
    assert repeated.selected_choice == 'deny'


def test_run_capabilities_require_approval_and_rich_tool_events():
    features = {
        'run_submission': True,
        'run_events_sse': True,
        'run_approval_response': True,
        'approval_events': True,
        'run_tool_arguments': True,
        'run_tool_results': True,
    }
    assert hermes_run_capabilities_satisfied({'features': features}) is True

    features['run_tool_arguments'] = False
    assert hermes_run_capabilities_satisfied({'features': features}) is False
