"""Timing badge colours, independent triggers, deduplication and tooltip evidence."""
import os
from pathlib import Path
import tempfile
from playwright.sync_api import sync_playwright
from reporting.report import build_report, write_report
from tests.test_reporting import fixture


def main():
    records, specs = fixture()
    with tempfile.TemporaryDirectory() as temporary:
        path = write_report(build_report(records, specs), Path(temporary) / 'timing.html')
        with sync_playwright() as playwright:
            executable = os.environ.get('REPORT_BROWSER_EXECUTABLE')
            browser = playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
            page = browser.new_page(); errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(path.as_uri())
            results = page.evaluate('''() => {
                const records = StatisticsReport.Data.matrix.records;
                const base = { elapsed_seconds: 10, expected_seconds: 20, peer_median_seconds: 15,
                    relative_threshold_seconds: 30, peer_models: 4, current_timeout_seconds: 120,
                    saved_timeout_seconds: 300, timed_out: false };
                const make = (id, changes, outcome = "pass") => {
                    records[id] = {outcome, timing: {...base, ...changes}, metadata: {}};
                    return {ids: [id], primary_ids: [id], reference_ids: []};
                };
                const normal = make("timing-normal", {});
                const boundary = make("timing-boundary", {elapsed_seconds: 20});
                const green = make("timing-green", {elapsed_seconds: 20.01});
                const amber = make("timing-amber", {elapsed_seconds: 120});
                const relative = make("timing-relative", {elapsed_seconds: 25, expected_seconds: 90, peer_median_seconds: 10, relative_threshold_seconds: 20});
                const timeout = make("timing-timeout", {elapsed_seconds: 300, timed_out: true, current_timeout_seconds: 900}, "fail");
                const missing = make("timing-missing", {elapsed_seconds: null});
                const failed = make("timing-failed", {elapsed_seconds: 50}, "fail");
                const error = make("timing-error", {elapsed_seconds: 90}, "error");
                const sample = cells => {
                    const row = document.createElement("tr");
                    ResultsMatrix.Cell(row, cells, "Timing smoke");
                    const cell = row.lastChild;
                    const marker = cell.querySelector("[data-timing-marker]");
                    return {text: cell.textContent, marker: marker?.dataset.timingMarker || null,
                        colour: marker?.style.borderTopColor || null, title: cell.title};
                };
                const values = {normal: sample([normal]), boundary: sample([boundary]), green: sample([green]),
                    amber: sample([amber]), relative: sample([relative]), timeout: sample([timeout]),
                    missing: sample([missing]), failed: sample([failed]), error: sample([error]),
                    aggregate: sample([normal, amber, timeout, timeout])};
                for (const id of Object.keys(records).filter(id => id.startsWith("timing-"))) delete records[id];
                return values;
            }''')
            for name in ('normal', 'boundary', 'missing', 'error'):
                assert results[name]['marker'] is None, (name, results[name])
            assert results['green']['marker'] == 'slow'
            assert results['green']['colour'] != results['amber']['colour']
            assert results['timeout']['colour'] == 'rgb(255, 0, 0)'
            assert results['aggregate']['colour'] == 'rgb(255, 0, 0)'
            assert results['timeout']['text'] == '0%'
            assert 'over expected time' in results['green']['title']
            assert 'slow compared with other models' in results['relative']['title']
            assert 'over expected time' not in results['relative']['title']
            assert 'Current timeout: 900.0s' in results['timeout']['title']
            assert 'Saved run timeout: 300.0s' in results['timeout']['title']
            assert 'across 3 unique observations' in results['aggregate']['title']
            assert '1 actual timeouts' in results['aggregate']['title']
            assert results['failed']['marker'] == 'slow' and results['failed']['text'] == '0%'
            assert not errors, errors
            browser.close()
    print('Timing badge browser smoke passed (synthetic evidence only)')


if __name__ == '__main__':
    main()
