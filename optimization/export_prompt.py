"""Export the actual next optimizer message without running inference or trials."""
import argparse
import json
from pathlib import Path
from .engine import generation_packet, packet_messages
from .storage import Store
from .prompt_builder import snapshot
from .token_budget import plan
from workbench.domain import digest


def export(root, session_id, destination):
    root, destination = Path(root), Path(destination)
    store = Store(root)
    session = store.load(session_id)
    if not session.get('prompt_builder') and not session['attempts']:
        session['prompt_builder'] = snapshot(root, session['definition'])
    packet = generation_packet(session, session['cohort']['models'], store.observations(session), store)
    messages = packet_messages(session, packet)
    model = next(m for m in session['cohort']['models'] if m['id'] == session['generator_id'])
    allocation = plan(model, messages, session['settings']['reasoning'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    # A single message file contains only its exact content, without labels added
    # by the export tool. JSON preserves roles for callers using the API.
    destination.write_bytes((messages[0]['content'] if len(messages) == 1 else
        '\n\n'.join(m['role'].upper() + ' MESSAGE\n\n' + m['content'] for m in messages)).encode('utf-8'))
    destination.with_suffix('.messages.json').write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding='utf-8')
    metadata = {'session_id': session_id, 'next_attempt': len(session['attempts']) + 1,
        'prompt_builder': session.get('prompt_builder', {}).get('version', 'legacy'),
        'message_count': len(messages), 'message_digest': digest(messages),
        'input_bytes': sum(len(m['content'].encode('utf-8')) for m in messages),
        'unique_captured_prompts': len(packet.get('prompts', {})),
        'baseline': packet['baseline_summary'], 'automatic_token_estimate': allocation,
        'tokenizer_verification': 'Exact model tokenizer verification still occurs before generation.',
        'export_only': True, 'inference_started': False}
    destination.with_suffix('.metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--session', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    metadata = export(args.root, args.session, args.output)
    print(json.dumps({key: metadata[key] for key in ('session_id', 'next_attempt', 'message_count', 'input_bytes', 'unique_captured_prompts')}, indent=2))


if __name__ == '__main__':
    main()
